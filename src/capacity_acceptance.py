"""Accept corroborated legacy lot capacities only on their audited snapshot date."""

import re

import pandas as pd


KEYS = ["academic_year", "quarter", "facility", "category"]
QUARTERS = {"Summer": (1, "July", 7), "Fall": (2, "October", 10),
            "Winter": (3, "January", 1), "Spring": (4, "April", 4)}


def legacy_snapshot_date(row):
    """Validate an audited legacy lot report's period and return its snapshot date.

    Accept only the known quarterly filenames and their matching table titles.
    Modern workbooks and arbitrary filenames require separate dated evidence.
    """
    year = str(row["academic_year"])
    years = re.fullmatch(r"(\d{4})-(\d{4})", year)
    quarter = row["quarter"]
    if not years or int(years[2]) != int(years[1]) + 1 or quarter not in QUARTERS:
        return pd.NaT
    number, month_name, month = QUARTERS[quarter]
    calendar_year = int(years[1]) + (quarter in {"Winter", "Spring"})
    expected_file = f"Inventory {year}-{number} {month_name} 1.xlsx"
    if row["inventory_source_file"] != expected_file:
        return pd.NaT
    if row["inventory_source_sheet"] != "5A By Lot":
        return pd.NaT
    if row["inventory_facility_granularity"] != "lot":
        return pd.NaT
    if not re.search(rf"\b{quarter}\s*,?\s*{calendar_year}\b",
                     str(row["inventory_report_title_raw"])):
        return pd.NaT
    return pd.Timestamp(calendar_year, month, 1)


def apply_capacity_acceptance(results):
    """Return observations with supported snapshot matches and explicit reasons.

    Same-period, positive, unique Inventory counts must equal the reported QPASS
    total. Both sources must have unqualified lot/category scope. Observations
    must occur on the snapshot date, not before or after it. Any scope/count
    conflict for that key and date blocks acceptance for the whole key/date.
    This policy does not establish capacity on unsurveyed dates or modern files.
    """
    result = results.copy()
    result["matched_capacity"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["capacity_acceptance_status"] = "unresolved"
    result["capacity_acceptance_reason"] = "dated_inventory_evidence_required"
    result["capacity_acceptance_basis"] = ""
    result["inventory_snapshot_date"] = pd.NaT
    required = [*KEYS, "inventory_source_file", "inventory_source_sheet",
                "inventory_facility_granularity", "inventory_report_title_raw",
                "inventory_subtype_raw", "inventory_time_limit_raw",
                "inventory_single_capacity_status", "candidate_capacity",
                "inventory_group_count", "qpass_capacity_raw", "qpass_level_raw",
                "qpass_subtype_raw", "observation_date", "open_spaces_raw",
                "exclusion_reason", "_merge"]
    if not all(name in result for name in required) or result.empty:
        return result

    snapshots = result.apply(legacy_snapshot_date, axis=1)
    result["inventory_snapshot_date"] = pd.to_datetime(snapshots)
    dates = pd.to_datetime(result["observation_date"], errors="coerce").dt.normalize()
    valid_period = snapshots.notna()
    same_day = valid_period & dates.eq(snapshots)
    result.loc[valid_period & ~same_day, "capacity_acceptance_reason"] = "outside_inventory_snapshot_date"

    capacity = pd.to_numeric(result["candidate_capacity"], errors="coerce")
    reported = pd.to_numeric(result["qpass_capacity_raw"], errors="coerce")
    opened = pd.to_numeric(result["open_spaces_raw"], errors="coerce")
    blank = lambda name: result[name].fillna("").astype(str).str.strip().eq("")
    unqualified = (blank("qpass_level_raw") & blank("qpass_subtype_raw")
                   & blank("inventory_subtype_raw") & blank("inventory_time_limit_raw"))
    good_count = (capacity.gt(0) & capacity.lt(float("inf")) & capacity.mod(1).eq(0)
                  & reported.eq(capacity) & opened.ge(0) & opened.le(capacity)
                  & opened.mod(1).eq(0))
    good_source = (result["inventory_group_count"].eq(1)
                   & result["inventory_single_capacity_status"].eq("positive_unverified")
                   & result["_merge"].eq("both")
                   & result["facility"].astype(str).str.fullmatch(r"P\d+[A-Za-z]?")
                   & ~blank("category"))

    # A conflict in another survey slot must not disappear in an agreeing slot.
    group_frame = result[KEYS].copy()
    group_frame["date"] = dates
    group_frame["blocked"] = ~unqualified | ~good_count | ~good_source
    group_blocked = group_frame.groupby(KEYS + ["date"], dropna=False)["blocked"].transform("any")
    result.loc[same_day & group_blocked, "capacity_acceptance_reason"] = "scope_or_capacity_conflict"
    eligible = result["exclusion_reason"].eq("")
    result.loc[~eligible, "capacity_acceptance_reason"] = "excluded_observation"
    accepted = same_day & good_source & good_count & unqualified & ~group_blocked & eligible
    result.loc[accepted, "matched_capacity"] = capacity.loc[accepted].astype("Int64")
    result.loc[accepted, "capacity_acceptance_status"] = "accepted"
    result.loc[accepted, "capacity_acceptance_reason"] = ""
    result.loc[accepted, "capacity_acceptance_basis"] = "same_day_legacy_inventory_and_qpass_agreement"
    return result
