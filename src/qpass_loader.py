"""Load one QPASS workbook into a standardized long DataFrame.

QPASS workbooks come in three layouts (see docs for details):

- Format A (2018-2019): "wide" weekly sheets. Each sheet holds one week; each
  day is a block of four time columns. Header spread over several rows.
- Format B (2024-2025 to Fall 2025-2026): "long" sheets named
  "QPASS Data Entry (Week N)", one row per location x space type x day.
- Format C (Spring 2025-2026 onward): one long "Data Entry" sheet for the
  whole quarter, with a "Week #" column.

load_qpass() detects the format, reads only the raw-data sheets, and returns
the same columns for every format. Values are kept raw (no renaming of
locations or types); cleaning happens in a later step.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from pathlib import Path

import pandas as pd

from src.qpass_inventory import HEADER_SEARCH_ROWS, clean_column_name, parse_qpass_filename

logger = logging.getLogger(__name__)

FORMAT_A = "A_wide_weekly"
FORMAT_B = "B_long_weekly"
FORMAT_C = "C_long_single"

# Format C keeps all data in one sheet with exactly this name.
FORMAT_C_SHEET = "Data Entry"
# Format B data sheets start with this prefix, e.g. "QPASS Data Entry (Week 1)".
FORMAT_B_SHEET_PREFIX = "QPASS Data Entry"

# Format A workbooks also contain formatted copies of the data (summaries,
# oversubscription views, re-sorted copies). Sheets whose names contain any of
# these words are not raw data and are skipped.
FORMAT_A_EXCLUDED_SHEET_WORDS = ("oversubscription", "summary", "sorted", "copy of", "current week")

# In Format A, the first column of the label row reads "Structure".
FORMAT_A_LABEL = "Structure"
FORMAT_A_LEVEL_PREFIX = "Level"
# Text in the header row below the labels ("Available", "Available Spaces").
FORMAT_A_HEADER_ROW_TEXT = "Available"

# Bottom-of-sheet aggregate rows in some Format A sheets (e.g. Summer 2018).
# They hold totals across lots, not observations, so they are dropped.
FORMAT_A_SUMMARY_ROW_LABELS = {"Vacancy", "Physical Capacity", "Occupancy", "Oversubscription"}

# QPASS counts open spaces at four times of day.
SURVEY_TIMES = {
    dt.time(8, 0): "open_8am",
    dt.time(10, 0): "open_10am",
    dt.time(12, 0): "open_12pm",
    dt.time(14, 0): "open_2pm",
}
OPEN_COLUMNS = list(SURVEY_TIMES.values())

# Raw header text (after clean_column_name) -> standardized column name,
# for Formats B and C. Only the first column with each header is used; later
# duplicates (e.g. a second "Day") are Excel-calculated helper columns.
LONG_FORMAT_COLUMNS = {
    "Date": "date",
    "Day": "day",
    "Week #": "week",
    "Zone": "zone",
    "Report Area": "report_area",
    "Neighborhood": "neighborhood",
    "Lot / Structure": "lot_or_structure",
    "Location": "location",
    "Type": "type",
    "Sub Type": "sub_type",
    "Report Type": "report_type",
    "Total Stall Count": "total_stall_count",
    "Open Spaces 8am": "open_8am",
    "Open Spaces 10am": "open_10am",
    "Open Spaces 12pm": "open_12pm",
    "Open Spaces 2pm": "open_2pm",
}

# The header row of Format B/C data sheets starts with this cell.
LONG_FORMAT_HEADER_START = "Date"

# Columns a Format B/C data sheet must have. If a future workbook renames one,
# loading fails loudly instead of returning blank values.
LONG_FORMAT_REQUIRED_HEADERS = (
    "Date", "Location", "Type", "Total Stall Count",
    "Open Spaces 8am", "Open Spaces 10am", "Open Spaces 12pm", "Open Spaces 2pm",
)

# Raw Format A label -> standardized column name.
FORMAT_A_COLUMNS = {
    "Structure": "raw_structure",
    "Lot": "raw_lot",
    "Type": "type",
    "Total Spaces": "total_stall_count",
}

# Every DataFrame returned by load_qpass has exactly these columns, in order.
OUTPUT_COLUMNS = [
    "source_file", "sheet_name", "format_version",
    "academic_year", "quarter", "quarter_number",
    "date", "day", "week",
    "location", "lot_or_structure", "level",
    "zone", "report_area", "neighborhood",
    "type", "sub_type", "report_type",
    "total_stall_count", *OPEN_COLUMNS,
    "raw_structure", "raw_lot",
]

# Matches "Week 1" / "Week #2" / a standalone "W2". "W19" (= Winter 2019 in
# old sheet names) is not a week, so the short form allows one digit only.
WEEK_NUMBER_PATTERN = re.compile(r"Week\s*#?\s*(\d+)|\bW(\d)\b", re.IGNORECASE)


class UnsupportedQPASSFormatError(ValueError):
    """Raised when a workbook does not match any known QPASS layout."""


def load_qpass(path: str | Path) -> pd.DataFrame:
    """Load one QPASS workbook into a standardized long DataFrame.

    Each row is one location x space type x survey date, with open-space
    counts at 8am, 10am, 12pm and 2pm. academic_year, quarter and
    source_file come from the filename and are always filled.

    Nothing is dropped silently. Both of these are logged and stored on the
    returned DataFrame:

    - ``attrs["skipped_sheets"]``: list of (sheet name, reason) for sheets
      that were not read (non-data or empty).
    - ``attrs["dropped_rows"]``: {sheet name: count} of non-blank rows inside
      data sheets that were not kept (no date, no counts, or summary rows).

    Args:
        path: Path to a QPASS .xlsx or .xlsm workbook.

    Returns:
        DataFrame with columns OUTPUT_COLUMNS.

    Raises:
        FileNotFoundError: If the file does not exist.
        UnsupportedQPASSFormatError: If the filename does not follow the
            "QPASS {year}-{N} {Quarter}" pattern, no known data layout is
            found in the workbook, or a data sheet is missing a required
            column.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(path)

    file_info = parse_qpass_filename(path.name)
    if file_info["academic_year"] is None:
        raise UnsupportedQPASSFormatError(
            f"{path.name}: filename does not match 'QPASS YYYY-YYYY-N Quarter'"
        )
    if not file_info["name_matches_number"]:
        raise UnsupportedQPASSFormatError(
            f"{path.name}: quarter number {file_info['quarter_number']} does not match "
            f"quarter name {file_info['quarter_name']!r}"
        )

    sheets = pd.read_excel(path, sheet_name=None, header=None)
    format_version = detect_format(sheets)
    if format_version is None:
        raise UnsupportedQPASSFormatError(
            f"{path.name}: no '{FORMAT_C_SHEET}' sheet, no '{FORMAT_B_SHEET_PREFIX}...' "
            f"sheets, and no sheet with a '{FORMAT_A_LABEL}' label row"
        )

    frames, skipped, dropped = [], [], {}
    for sheet_name, sheet in sheets.items():
        try:
            if format_version == FORMAT_A:
                parsed, reason, n_dropped = _parse_format_a_sheet(sheet_name, sheet)
            else:
                parsed, reason, n_dropped = _parse_long_sheet(sheet_name, sheet, format_version)
        except UnsupportedQPASSFormatError as error:
            raise UnsupportedQPASSFormatError(f"{path.name}: {error}") from error
        if parsed is None:
            skipped.append((sheet_name, reason))
            logger.info("%s: skipped sheet %r (%s)", path.name, sheet_name, reason)
            continue
        if n_dropped:
            dropped[sheet_name] = n_dropped
            logger.info("%s: dropped %d non-blank rows without data in sheet %r",
                        path.name, n_dropped, sheet_name)
        parsed["sheet_name"] = sheet_name
        frames.append(parsed)

    if not frames:
        raise UnsupportedQPASSFormatError(
            f"{path.name}: detected {format_version} but no sheet contained data rows"
        )

    result = pd.concat(frames, ignore_index=True)
    result["source_file"] = path.name
    result["format_version"] = format_version
    result["academic_year"] = file_info["academic_year"]
    result["quarter"] = file_info["quarter_name"]
    result["quarter_number"] = file_info["quarter_number"]
    result = result.reindex(columns=OUTPUT_COLUMNS)
    _warn_on_dates_outside_academic_year(result, path.name)
    result.attrs["skipped_sheets"] = skipped
    result.attrs["dropped_rows"] = dropped
    return result


def detect_format(sheets: dict[str, pd.DataFrame]) -> str | None:
    """Decide which QPASS layout a workbook uses, based on its sheets.

    Args:
        sheets: Mapping of sheet name to sheet contents (read with header=None).

    Returns:
        FORMAT_A, FORMAT_B, FORMAT_C, or None if no layout matches.
    """
    names = [name.strip() for name in sheets]
    if FORMAT_C_SHEET in names:
        return FORMAT_C
    if any(name.startswith(FORMAT_B_SHEET_PREFIX) for name in names):
        return FORMAT_B
    if any(_is_format_a_data_sheet(name, sheet) for name, sheet in sheets.items()):
        return FORMAT_A
    return None


def _find_row(sheet: pd.DataFrame, first_cell: str) -> int | None:
    """Return the first row (within HEADER_SEARCH_ROWS) whose first cell equals first_cell."""
    for row_index in range(min(HEADER_SEARCH_ROWS, len(sheet))):
        if clean_column_name(sheet.iat[row_index, 0]) == first_cell:
            return row_index
    return None


def _week_from_sheet_name(sheet_name: str) -> int | None:
    """Read a week number from names like "QPASS Data Entry (Week 1)" or "... W2"."""
    match = WEEK_NUMBER_PATTERN.search(sheet_name)
    if match is None:
        return None
    return int(match.group(1) or match.group(2))


def _parse_long_sheet(sheet_name: str, sheet: pd.DataFrame, format_version: str) -> tuple:
    """Parse a Format B or C data sheet.

    Returns:
        (DataFrame, None, n_dropped) on success, or (None, reason, 0) if the
        sheet is not a data sheet for this format or has no dated rows.
        n_dropped counts non-blank rows that had no valid date.

    Raises:
        UnsupportedQPASSFormatError: If a required column is missing.
    """
    name = sheet_name.strip()
    if format_version == FORMAT_C:
        is_data_sheet = name == FORMAT_C_SHEET
    else:
        is_data_sheet = name.startswith(FORMAT_B_SHEET_PREFIX)
    if not is_data_sheet:
        return None, "not a data sheet", 0

    header_row = _find_row(sheet, LONG_FORMAT_HEADER_START)
    if header_row is None:
        return None, f"no '{LONG_FORMAT_HEADER_START}' header row found", 0

    headers = [clean_column_name(value) for value in sheet.iloc[header_row]]
    positions = {}
    for position, header in enumerate(headers):
        if header in LONG_FORMAT_COLUMNS and header not in positions:
            positions[header] = position
    _require_columns(sheet_name, positions, LONG_FORMAT_REQUIRED_HEADERS)

    body = sheet.iloc[header_row + 1:]
    data = pd.DataFrame({
        LONG_FORMAT_COLUMNS[header]: body.iloc[:, position].to_numpy()
        for header, position in positions.items()
    })
    is_non_blank = data.notna().any(axis=1)
    data["date"] = pd.to_datetime(data["date"], errors="coerce")
    has_date = data["date"].notna()
    n_dropped = int((is_non_blank & ~has_date).sum())
    data = data[has_date].reset_index(drop=True)
    if data.empty:
        return None, "no rows with a date (empty template sheet)", 0

    if "week" in data:
        data["week"] = data["week"].map(_parse_week_value)
    else:
        data["week"] = _week_from_sheet_name(name)
    return data, None, n_dropped


def _require_columns(sheet_name: str, found: dict, required: tuple) -> None:
    """Raise UnsupportedQPASSFormatError if any required header is missing.

    Args:
        sheet_name: Sheet being parsed, used in the error message.
        found: Headers found in the sheet (only the keys are used).
        required: Headers the sheet must contain.
    """
    missing = [header for header in required if header not in found]
    if missing:
        raise UnsupportedQPASSFormatError(
            f"sheet {sheet_name!r} is missing required column(s): {', '.join(missing)}"
        )


def _parse_week_value(value) -> int | None:
    """Turn a "Week #" cell ("Week 0", 1, "1") into an int, or None if blank."""
    if pd.isna(value):
        return None
    digits = re.search(r"\d+", str(value))
    return int(digits.group()) if digits else None


def _is_format_a_data_sheet(sheet_name: str, sheet: pd.DataFrame) -> bool:
    """True if a sheet is a raw Format A weekly data sheet."""
    lowered = sheet_name.lower()
    if any(word in lowered for word in FORMAT_A_EXCLUDED_SHEET_WORDS):
        return False
    label_row = _find_row(sheet, FORMAT_A_LABEL)
    return label_row is not None and bool(_format_a_column_dates(sheet, label_row))


def _format_a_column_dates(sheet: pd.DataFrame, label_row: int) -> dict[int, tuple]:
    """Map each count column of a Format A sheet to its (date, survey time).

    The header block above the data has a row of dates (one per day block)
    and a row of times (one per column). A column's date is the nearest date
    at or to its left, because each date sits above the first of its four
    time columns.

    Returns:
        {column_index: (date, open_column_name)} for every survey-time column.
    """
    header_block = sheet.iloc[: label_row + 1]
    column_dates = {}
    current_date = None
    for column in range(sheet.shape[1]):
        cells = header_block.iloc[:, column].tolist()
        for cell in cells:
            if isinstance(cell, (dt.datetime, pd.Timestamp)):
                current_date = pd.Timestamp(cell).normalize()
        survey_time = next((cell for cell in cells if isinstance(cell, dt.time)), None)
        if current_date is not None and survey_time in SURVEY_TIMES:
            column_dates[column] = (current_date, SURVEY_TIMES[survey_time])
    return column_dates


def _parse_format_a_sheet(sheet_name: str, sheet: pd.DataFrame) -> tuple:
    """Parse one Format A weekly sheet into long rows (one per row x date).

    Structure and Lot cells are often blank, meaning "same as the row above".
    Lot is filled down, but never past a row that names a new Structure.
    Structure is filled down only for level rows ("Level 2") and for structure
    rows with no lot at all; surface lots ("P002") with a blank Structure do
    not belong to the structure above them.

    Returns:
        (DataFrame, None, n_dropped) on success, or (None, reason, 0) if not a
        data sheet. n_dropped counts non-blank rows that were not kept
        (section headings, closed-lot lists, summary rows).

    Raises:
        UnsupportedQPASSFormatError: If a required label is missing.
    """
    if not _is_format_a_data_sheet(sheet_name, sheet):
        return None, "not a data sheet", 0

    label_row = _find_row(sheet, FORMAT_A_LABEL)
    labels = [clean_column_name(value) for value in sheet.iloc[label_row]]
    label_positions = {label: labels.index(label) for label in FORMAT_A_COLUMNS if label in labels}
    _require_columns(sheet_name, label_positions, tuple(FORMAT_A_COLUMNS))
    column_dates = _format_a_column_dates(sheet, label_row)

    body = sheet.iloc[label_row + 1:].reset_index(drop=True)
    # Some sheets have an "Available Available ..." row under the labels. It
    # is part of the header, so remove it before counting dropped rows.
    is_header_row = body.apply(
        lambda row: row.dropna().astype(str).str.startswith(FORMAT_A_HEADER_ROW_TEXT).all()
        and row.notna().any(),
        axis=1,
    )
    body = body[~is_header_row].reset_index(drop=True)
    info = pd.DataFrame({
        FORMAT_A_COLUMNS[label]: body.iloc[:, position].to_numpy()
        for label, position in label_positions.items()
    })

    counts = body.iloc[:, list(column_dates)].apply(pd.to_numeric, errors="coerce")
    has_total = pd.to_numeric(info["total_stall_count"], errors="coerce").notna()
    has_data = counts.notna().any(axis=1) | has_total
    is_summary = info["raw_lot"].map(clean_column_name).isin(FORMAT_A_SUMMARY_ROW_LABELS)

    structure = info["raw_structure"].map(clean_column_name).replace("", None)
    filled_structure = structure.ffill()
    # Each non-blank Structure cell starts a new group. Lot is filled down only
    # within its group, so a structure listed with a blank Lot (e.g. "Gilman")
    # does not inherit the surface lot above it (e.g. "P010").
    structure_group = structure.notna().cumsum()
    lot = info["raw_lot"].map(clean_column_name).replace("", None).groupby(structure_group).ffill()
    is_level = lot.fillna("").str.startswith(FORMAT_A_LEVEL_PREFIX)
    is_whole_structure = lot.isna()  # structure row with no lot or level given
    info["location"] = filled_structure.where(is_level | is_whole_structure, lot)
    info["level"] = lot.where(is_level)
    info["lot_or_structure"] = (is_level | is_whole_structure).map({True: "Structure", False: "Lot"})

    keep = has_data & ~is_summary
    n_dropped = int((body.notna().any(axis=1) & ~keep).sum())
    info, body = info[keep], body[keep]
    if info.empty:
        return None, "no data rows below the header", 0

    records = []
    dates = sorted({date for date, _ in column_dates.values()})
    for date in dates:
        day_frame = info.copy()
        day_frame["date"] = date
        day_frame["day"] = date.day_name()
        for column, (column_date, open_name) in column_dates.items():
            if column_date == date:
                day_frame[open_name] = body.iloc[:, column].to_numpy()
        records.append(day_frame)
    data = pd.concat(records, ignore_index=True)
    data["week"] = _week_from_sheet_name(sheet_name)
    return data, None, n_dropped


def _warn_on_dates_outside_academic_year(data: pd.DataFrame, filename: str) -> None:
    """Log a warning if any row's date falls outside the file's academic year.

    An academic year "2024-2025" spans calendar years 2024 and 2025.
    """
    start_year, end_year = (int(year) for year in data["academic_year"].iloc[0].split("-"))
    outside = ~data["date"].dt.year.between(start_year, end_year)
    if outside.any():
        logger.warning(
            "%s: %d rows have dates outside academic year %d-%d",
            filename, int(outside.sum()), start_year, end_year,
        )
