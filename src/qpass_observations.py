"""Reshape the shared QPASS loader output and retain a complete quality audit."""

import numpy as np
import pandas as pd

from src.qpass_loader import FORMAT_A, OPEN_COLUMNS, OUTPUT_COLUMNS

TIME_COLUMNS = dict(zip(OPEN_COLUMNS, ["08:00", "10:00", "12:00", "14:00"]))
REQUIRED = ["observation_datetime", "location", "type",
            "total_stall_count", "open_spaces"]
IDENTITY_COLUMNS = ["observation_datetime", "location", "type", "sub_type", "level"]


def _blank(values: pd.Series) -> pd.Series:
    """Recognize actual missing values and whitespace-only readings."""
    return values.isna() | values.astype("string").str.strip().eq("").fillna(False)


def _value_token(raw: pd.Series, numeric: pd.Series) -> pd.Series:
    """Build comparable payload tokens without equating text and blank values."""
    tokens = pd.Series("blank:", index=raw.index, dtype="string")
    text = ~_blank(raw) & numeric.isna()
    tokens.loc[text] = "text:" + raw.loc[text].astype("string").str.strip()
    number = numeric.notna()
    tokens.loc[number] = "number:" + numeric.loc[number].astype("string")
    return tokens


def reshape_loaded_observations(table: pd.DataFrame) -> pd.DataFrame:
    """Turn each shared-loader row into four timed observations.

    Args:
        table: Output of load_qpass() or load_all_qpass(), with OUTPUT_COLUMNS.
            Dates must already be decoded by that loader.

    Returns:
        A new table retaining shared identity/provenance columns and original
        values in raw_* fields. Four wide open_* columns become open_spaces,
        raw_open_spaces, observation_time, and source_time_column. Counts use
        nullable Float64; date/datetime are parsed local wall times. Optional
        report_type/sub_type status distinguishes format absence from blanks.
        Empty input yields the same output schema with no observations.

    Raises:
        ValueError: Shared-loader columns are missing or duplicated.
    """
    if table.columns.duplicated().any():
        raise ValueError("Duplicate loader columns")
    missing = [c for c in OUTPUT_COLUMNS if c not in table]
    if missing:
        raise ValueError(f"Missing loader columns: {missing}")
    wide = table.copy()
    wide["loader_row_id"] = np.arange(len(wide))
    result = wide.melt(
        id_vars=[c for c in wide if c not in TIME_COLUMNS],
        value_vars=list(TIME_COLUMNS),
        var_name="source_time_column", value_name="raw_open_spaces",
    )
    for column in ["date", "location", "type", "sub_type", "report_type",
                   "level", "total_stall_count"]:
        result[f"raw_{column}"] = result[column]
    dates = pd.to_datetime(result["date"], errors="coerce", format="mixed")
    # Reject undecoded Excel serials rather than interpreting nanoseconds.
    numeric_dates = result["date"].map(
        lambda value: isinstance(value, (int, float, np.number))
    ).astype(bool)
    result["date"] = dates.mask(numeric_dates).dt.normalize()
    result["observation_time"] = result["source_time_column"].map(TIME_COLUMNS)
    result["observation_datetime"] = result["date"] + pd.to_timedelta(
        result["observation_time"] + ":00"
    )
    for column, raw in [("total_stall_count", "raw_total_stall_count"),
                        ("open_spaces", "raw_open_spaces")]:
        result[column] = pd.to_numeric(result[raw], errors="coerce").astype("Float64")
    for column in ["report_type", "sub_type"]:
        result[f"{column}_status"] = pd.Series(
            np.where(_blank(result[column]), "blank_or_unavailable", "present"),
            index=result.index, dtype="string",
        )
        # Format A's raw layout has neither Report Type nor Sub Type.
        absent = result["format_version"].eq(FORMAT_A) & _blank(result[column])
        result.loc[absent, f"{column}_status"] = "not_in_format"
    result.attrs = table.attrs.copy()
    return result


def validate_observations(
    observations: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Flag quality failures without removing or combining observations.

    Args:
        observations: Output of reshape_loaded_observations(). Counts must be
            numeric and raw_* values must still be present. Run on the combined
            dataset to detect repeats across sheets/files.

    Returns:
        Audited table and per-check failed/passed counts (including any_check).
        Exact repeats share identity and count/capacity payload. Conflicts share
        identity but contain different payloads; both flags can apply to a row.
        Optional subtype/level blanks participate in identity as equal blanks;
        report_type is auxiliary metadata, not a required category. Identity
        groups and every source row are preserved. Empty input gives zero counts.

    Raises:
        ValueError: Required columns for validation are absent.
    """
    expected = [*REQUIRED, "sub_type", "level", "raw_total_stall_count",
                "raw_open_spaces"]
    missing = [c for c in expected if c not in observations]
    if missing:
        raise ValueError(f"Missing observation columns: {missing}")
    result = observations.copy()
    flags = pd.DataFrame(index=result.index)
    for column in ["observation_datetime", "location", "type"]:
        flags[f"missing_{column}"] = _blank(result[column])
    for column, raw in [("total_stall_count", "raw_total_stall_count"),
                        ("open_spaces", "raw_open_spaces")]:
        values = result[column]
        flags[f"missing_{column}"] = _blank(result[raw])
        flags[f"unexpected_text_{column}"] = ~_blank(result[raw]) & values.isna()
        flags[f"negative_{column}"] = values.lt(0).fillna(False)
        flags[f"nonfinite_{column}"] = (
            values.notna() & ~np.isfinite(values)
        ).fillna(False)
        flags[f"fractional_{column}"] = (
            np.isfinite(values) & values.mod(1).ne(0)
        ).fillna(False)
    flags["zero_capacity"] = result["total_stall_count"].eq(0).fillna(False)
    flags["open_exceeds_capacity"] = result["open_spaces"].gt(
        result["total_stall_count"]
    ).fillna(False)

    # Compare cleaned identity only; source labels themselves remain untouched.
    identity = result[IDENTITY_COLUMNS].copy()
    for column in ["location", "type", "sub_type", "level"]:
        identity[column] = identity[column].astype("string").str.strip()
        identity[column] = identity[column].mask(_blank(identity[column]))
    complete = ~flags[["missing_observation_datetime", "missing_location",
                       "missing_type"]].any(axis=1)
    identity["capacity_payload"] = _value_token(
        result["raw_total_stall_count"], result["total_stall_count"]
    )
    identity["open_payload"] = _value_token(
        result["raw_open_spaces"], result["open_spaces"]
    )
    payload_columns = ["capacity_payload", "open_payload"]
    flags["exact_repeated_record"] = identity.duplicated(
        IDENTITY_COLUMNS + payload_columns, keep=False
    ) & complete
    groups = identity.groupby(IDENTITY_COLUMNS, dropna=False, sort=False)
    variants = groups[payload_columns].transform("nunique")
    flags["conflicting_observation"] = variants.gt(1).any(axis=1) & complete
    result["observation_group"] = (groups.ngroup() + 1).astype("Int64").mask(~complete)
    result["quality_flag"] = pd.Series(index=result.index, dtype="string")
    if not result.empty:
        result["quality_flag"] = flags.apply(
            lambda row: "|".join(row.index[row]) or "pass", axis=1
        ).astype("string")
    result["quality_pass"] = ~flags.any(axis=1)
    summary = pd.DataFrame({
        "check": flags.columns, "failed": flags.sum().to_numpy(),
        "passed": (~flags).sum().to_numpy(),
    })
    summary.loc[len(summary)] = [
        "any_check", int((~result["quality_pass"]).sum()),
        int(result["quality_pass"].sum()),
    ]
    return result, summary
