"""Reshape representative QPASS tables and flag data-quality problems.

The notebook imports these functions; tests exercise them independently.
The representative reader supports the 2026 Summer Data Entry layout.
"""

from pathlib import Path

import numpy as np
import pandas as pd

# Representative Data Entry layout: title on row 1, headers on row 2.
FIRST_DATA_EXCEL_ROW = 3

TIME_COLUMNS = {f"Open Spaces {label}": time for label, time in
                [("8am", "08:00"), ("10am", "10:00"),
                 ("12pm", "12:00"), ("2pm", "14:00")]}
REQUIRED = ["observation_datetime", "facility_name", "parking_category",
            "parking_subtype", "capacity", "open_spaces"]


def reshape_observations(table: pd.DataFrame, *, source_file: str,
                         academic_year: str, quarter: str,
                         source_sheet: str = "Data Entry") -> pd.DataFrame:
    """Convert a wide Data Entry table into four rows per source row.

    Accepts a representative sheet's original Excel headers. Header whitespace is
    normalized; Excel dates must already be decoded by the workbook loader.
    Raw values and row identity are retained. No data records are dropped.

    Args:
        table: Wide table with Date, Location, Type, Report Type, Total Stall
            Count and the four TIME_COLUMNS. Dates must be decoded datetimes
            or parseable strings. Supply source_row for nonstandard layouts.
        source_file: Original workbook filename.
        academic_year: Source academic year label.
        quarter: Source quarter label.
        source_sheet: Original worksheet name.

    Returns:
        Four rows per input row with standardized dates, times, nullable
        Float64 counts, raw values and provenance. Invalid values become
        missing for subsequent validation; the input table is unchanged.

    Raises:
        ValueError: Required headers are missing or normalized headers repeat.
    """
    wide = table.copy()
    wide.columns = [" ".join(str(c).split()) for c in wide.columns]
    if wide.columns.duplicated().any():
        raise ValueError("Duplicate headers after whitespace normalization")
    needed = ["Date", "Location", "Type", "Report Type", "Total Stall Count",
              *TIME_COLUMNS]
    missing = [c for c in needed if c not in wide]
    if missing:
        raise ValueError(f"Missing input columns: {missing}")
    if "source_row" not in wide:
        wide["source_row"] = np.arange(len(wide)) + FIRST_DATA_EXCEL_ROW
    long = wide.melt(id_vars=[c for c in wide if c not in TIME_COLUMNS],
                     value_vars=list(TIME_COLUMNS), var_name="raw_time_column",
                     value_name="raw_open_spaces")
    for raw, original in [("raw_date", "Date"), ("raw_facility_name", "Location"),
                          ("raw_parking_subtype", "Type"),
                          ("raw_parking_category", "Report Type"),
                          ("raw_capacity", "Total Stall Count")]:
        long[raw] = long[original]
    for dest, original in [("facility_name", "Location"),
                           ("parking_category", "Report Type"),
                           ("parking_subtype", "Type")]:
        long[dest] = long[original].astype("string").str.strip().replace("", pd.NA)
    dates = pd.to_datetime(long["raw_date"], errors="coerce", format="mixed")
    # Do not interpret undecoded Excel serials as nanoseconds since 1970.
    numeric_dates = long["raw_date"].map(
        lambda v: isinstance(v, (int, float, np.number)))
    dates = dates.mask(numeric_dates)
    long["observation_date"] = dates.dt.normalize()
    long["observation_time"] = (
        long["raw_time_column"].map(TIME_COLUMNS).astype("string")
    )
    long["observation_datetime"] = long["observation_date"] + pd.to_timedelta(
        long["observation_time"] + ":00")
    for dest, raw in [("capacity", "raw_capacity"), ("open_spaces", "raw_open_spaces")]:
        long[dest] = pd.to_numeric(long[raw], errors="coerce").astype("Float64")
    long["source_file"] = source_file
    long["source_sheet"] = source_sheet
    long["academic_year"] = academic_year
    long["quarter"] = quarter
    return long


def reshape_loaded_observations(table: pd.DataFrame) -> pd.DataFrame:
    """Reshape task #1's combined loader output, preserving provenance and audits.

    Args:
        table: DataFrame returned by load_qpass() or load_all_qpass().

    Returns:
        Four observation rows per loader row. Loader audit metadata remains in
        attrs. Absent report categories stay missing rather than being guessed.
    """
    column_map = {
        "date": "Date", "location": "Location", "type": "Type",
        "report_type": "Report Type", "total_stall_count": "Total Stall Count",
        "open_8am": "Open Spaces 8am", "open_10am": "Open Spaces 10am",
        "open_12pm": "Open Spaces 12pm", "open_2pm": "Open Spaces 2pm",
    }
    provenance = ["source_file", "sheet_name", "source_row", "academic_year", "quarter"]
    missing = [c for c in [*column_map, *provenance] if c not in table]
    if missing:
        raise ValueError(f"Missing loader columns: {missing}")
    # Let the existing reshape function handle conversion, preserving metadata
    # separately for each file/sheet/quarter instead of assigning one file to all.
    groups = ["source_file", "sheet_name", "academic_year", "quarter"]
    frames = []
    for metadata, group in table.groupby(groups, dropna=False, sort=False):
        filename, sheet, year, quarter = metadata
        frame = reshape_observations(
            group.rename(columns=column_map), source_file=filename,
            source_sheet=sheet, academic_year=year, quarter=quarter,
        )
        frame.attrs = {}
        frames.append(frame)
    if not frames:
        raise ValueError("Loader returned no observation rows")
    result = pd.concat(frames, ignore_index=True)
    result.attrs = table.attrs.copy()
    return result


def validate_observations(
    observations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flag every failed check and summarize pass/fail counts without dropping rows.

    Run once after concatenating quarters to detect cross-file duplicates.
    Duplicate identity includes subtype, preventing distinct allocations from
    being mistaken for repeated observations. Flags may overlap.

    Args:
        observations: Reshaped table containing REQUIRED fields. Count columns
            must be numeric; observation_datetime must already be parsed.
            Optional level and sub_type fields extend duplicate identity.

    Returns:
        A copy of observations with quality_flag and quality_pass, plus a
        summary with check, failed and passed columns. Empty input returns
        an empty audited table and zero counts for every check. Input rows
        and values are never deleted or corrected.

    Raises:
        ValueError: A required observation column is absent.
    """
    result = observations.copy()
    missing = [c for c in REQUIRED if c not in result]
    if missing:
        raise ValueError(f"Missing observation columns: {missing}")
    flags = pd.DataFrame(index=result.index)
    for col in REQUIRED:
        blank = result[col].astype("string").str.strip().eq("").fillna(False)
        flags[f"missing_{col}"] = result[col].isna() | blank
    for col in ["capacity", "open_spaces"]:
        vals = result[col]
        flags[f"negative_{col}"] = vals.lt(0).fillna(False)
        flags[f"nonfinite_{col}"] = (vals.notna() & ~np.isfinite(vals)).fillna(False)
        flags[f"fractional_{col}"] = (
            np.isfinite(vals) & vals.mod(1).ne(0)
        ).fillna(False)
    flags["zero_capacity"] = result["capacity"].eq(0).fillna(False)
    flags["open_exceeds_capacity"] = (
        result["open_spaces"].gt(result["capacity"]).fillna(False)
    )
    key = [
        "observation_datetime", "facility_name",
        "parking_category", "parking_subtype",
    ]
    # Old workbooks distinguish structure levels; some also have Sub Type.
    # Keep those allocations distinct without requiring optional fields.
    duplicate_key = key + [c for c in ("level", "sub_type") if c in result]
    flags["duplicate_observation"] = (
        result.duplicated(duplicate_key, keep=False)
        & result[key].notna().all(axis=1)
    )
    if result.empty:
        result["quality_flag"] = pd.Series(index=result.index, dtype="string")
    else:
        result["quality_flag"] = flags.apply(
            lambda row: "|".join(row.index[row]) or "pass", axis=1
        )
    result["quality_pass"] = ~flags.any(axis=1)
    summary = pd.DataFrame({"check": flags.columns,
                            "failed": flags.sum().to_numpy(),
                            "passed": (~flags).sum().to_numpy()})
    summary.loc[len(summary)] = ["any_check", int((~result["quality_pass"]).sum()),
                                int(result["quality_pass"].sum())]
    return result, summary

def load_representative_workbook(path: Path, *, academic_year: str,
                                 quarter: str) -> pd.DataFrame:
    """Read the observed Summer Data Entry layout; not a general workbook loader.

    Issue #1 owns broader schema support. Excel macros are never executed.
    Fully blank source rows are counted as layout padding, not observations.

    Args:
        path: Workbook with a Data Entry sheet, headers on Excel row 2 and
            first data on row 3 (the 2026 Summer representative layout).
        academic_year: Label to attach to each output observation.
        quarter: Quarter label to attach to each output observation.

    Returns:
        Reshaped observations, with blank_padding_rows recorded in attrs.
        Partially filled rows are preserved. Use task #1's loader and
        reshape_loaded_observations() for the full set of workbook layouts.

    Raises:
        ValueError: Required representative headers or worksheet are missing.
        FileNotFoundError: The workbook does not exist.
    """
    table = pd.read_excel(path, sheet_name="Data Entry", header=1, engine="openpyxl")
    cols = [
        "Date", "Location", "Type", "Report Type",
        "Total\nStall\nCount", *TIME_COLUMNS,
    ]
    missing = [c for c in cols if c not in table]
    if missing:
        raise ValueError(f"Unsupported Data Entry headers in {path.name}: {missing}")
    table["source_row"] = np.arange(len(table)) + FIRST_DATA_EXCEL_ROW
    padding = table[cols].isna().all(axis=1)
    long = reshape_observations(table.loc[~padding], source_file=path.name,
                                academic_year=academic_year, quarter=quarter)
    long.attrs["blank_padding_rows"] = int(padding.sum())
    return long
