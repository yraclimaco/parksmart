"""Compare representative QPASS records with Inventory candidates."""

import argparse
import math
from pathlib import Path

import pandas as pd
from src.qpass_loader import load_qpass
from src.capacity_scope import apply_scope_review


KEYS = ["academic_year", "quarter", "facility", "category"]


def _numeric_status(value):
    """Classify a raw count without treating missing or zero as verified."""
    if pd.isna(value) or str(value).strip() == "":
        return "missing"
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return "invalid_numeric"
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        return "invalid_capacity"
    if number == 0:
        return "zero_review"
    return "positive_unverified"


def audit_reported_capacities(results):
    """Compare reported totals with unambiguous Inventory candidates.

    Args:
        results: Joined observations containing qpass_capacity_raw,
            candidate_capacity, inventory_group_count, and _merge columns.

    Returns:
        A copy with numeric totals, validity flags, a comparison flag, and
        QPASS-minus-Inventory differences. Agreement does not verify history
        or establish that category scopes are equivalent.
    """
    results = results.copy()
    results["qpass_capacity_status"] = results["qpass_capacity_raw"].map(
        _numeric_status
    )
    results["qpass_capacity_numeric"] = pd.to_numeric(
        results["qpass_capacity_raw"], errors="coerce"
    )
    inventory_status = results["candidate_capacity"].map(_numeric_status)
    comparable = (
        results["_merge"].eq("both")
        & results["inventory_group_count"].eq(1)
        & inventory_status.eq("positive_unverified")
        & results["qpass_capacity_status"].eq("positive_unverified")
    )
    results["reported_capacity_comparison"] = "not_comparable"
    difference = (
        results["qpass_capacity_numeric"] - results["candidate_capacity"]
    )
    results["capacity_difference"] = difference.where(comparable)
    results.loc[
        comparable & difference.eq(0), "reported_capacity_comparison"
    ] = "agree_unverified"
    results.loc[
        comparable & difference.ne(0), "reported_capacity_comparison"
    ] = "conflict"
    return results


def compare_capacities(
    inventory_path,
    qpass_path,
    output_dir=Path("results/capacity_matching"),
):
    """Compare a cleaned Inventory CSV with a QPASS workbook.

    Args:
        inventory_path: Path to the extracted Inventory capacity CSV.
        qpass_path: Path to the QPASS workbook.
        output_dir: Directory for reports; existing reports are overwritten.

    Returns:
        None. Writes comparison reports and prints the summary.
    """
    inventory_path = Path(inventory_path)
    qpass_path = Path(qpass_path)

    inventory = pd.read_csv(
        inventory_path,
        dtype={"facility_raw": "string", "category_raw": "string"},
        keep_default_na=False,
    )
    inventory["facility"] = inventory["facility_raw"].str.strip()
    inventory["category"] = inventory["category_raw"].str.strip()

    # Multiple subtypes/time limits require an explicit mapping decision.
    candidates = []
    for keys, group in inventory.groupby(KEYS, dropna=False):
        record = dict(zip(KEYS, keys))
        record["inventory_group_count"] = len(group)
        record["inventory_source_file"] = ";".join(
            group["source_file"].unique()
        )
        record["inventory_source_rows"] = ";".join(
            group["source_rows"].astype(str)
        )
        # Lists retain all contributing raw labels and capacity values.
        record["inventory_facility_raw_values"] = group[
            "facility_raw"
        ].tolist()
        record["inventory_category_raw_values"] = group[
            "category_raw"
        ].tolist()
        record["inventory_capacity_raw_values"] = (
            group["capacity_raw_values"].tolist()
            if "capacity_raw_values" in group else group["capacity"].tolist()
        )
        record["inventory_capacity_statuses"] = (
            group["capacity_status"].tolist() if "capacity_status" in group else []
        )
        record["candidate_capacity"] = (
            group["capacity"].iloc[0] if len(group) == 1 else pd.NA
        )
        candidates.append(record)

    candidates = pd.DataFrame(candidates)
    qpass = load_qpass(qpass_path)

    # Save the loader's audit information before transforming its output.
    import json

    audit_dir = Path(output_dir)
    audit_dir.mkdir(parents=True, exist_ok=True)
    with (audit_dir / "qpass_loader_audit.json").open(
        "w", encoding="utf-8"
    ) as handle:
        json.dump(qpass.attrs, handle, indent=2, default=str)

    observations = []
    time_columns = {
        "8am": "open_8am",
        "10am": "open_10am",
        "12pm": "open_12pm",
        "2pm": "open_2pm",
    }

    for _, row in qpass.iterrows():
        for time, column in time_columns.items():
            observations.append({
                "academic_year": row["academic_year"],
                "quarter": row["quarter"],
                "facility": str(row["location"]).strip(),
                "category": str(row["type"]).strip(),
                "qpass_facility_raw": row["location"],
                "qpass_category_raw": row["type"],
                "qpass_subtype_raw": row["sub_type"],
                "qpass_level_raw": row["level"],
                "observation_date": row["date"],
                "observation_time": time,
                "open_spaces_raw": row[column],
                "qpass_capacity_raw": row["total_stall_count"],
                "qpass_source_file": row["source_file"],
                "qpass_source_sheet": row["sheet_name"],
                "qpass_source_row": row["source_row"],
            })


    results = pd.DataFrame(observations).merge(
        candidates,
        on=KEYS,
        how="left",
        validate="many_to_one",
        indicator=True,
    )

    results["candidate_capacity"] = pd.to_numeric(
        results["candidate_capacity"], errors="coerce"
    )
    results = audit_reported_capacities(results)
    opened = pd.to_numeric(results["open_spaces_raw"], errors="coerce")
    capacity = results["candidate_capacity"]

    results["comparison_status"] = "historical_verification_required"
    results.loc[capacity.isna(), "comparison_status"] = (
        "missing_or_invalid_capacity"
    )
    results.loc[capacity.eq(0), "comparison_status"] = "zero_capacity_review"
    results.loc[
        opened.gt(capacity), "comparison_status"
    ] = "open_spaces_exceed_candidate"
    results.loc[
        results["inventory_group_count"].gt(1), "comparison_status"
    ] = "subtype_mapping_required"
    results.loc[
        results["_merge"].eq("left_only"), "comparison_status"
    ] = "no_exact_inventory_key"

    results["open_spaces_exceed_candidate"] = opened.gt(capacity)
    results = apply_scope_review(results)

    # No candidate is accepted as historically verified yet.
    results["matched_capacity"] = pd.NA
    results["recommended_next_step"] = (
        "Verify historical capacity and category scope; "
        "use teammate mappings for unresolved identifiers."
    )

    results["exact_key_found"] = results["_merge"].eq("both")
    results["exclusion_reason"] = ""

    invalid_identifier = (
        results["facility"].eq("0")
        | results["category"].eq("0")
    )
    results.loc[
        invalid_identifier, "exclusion_reason"
    ] = "invalid_facility_or_category"

    missing_observation = (
        results["open_spaces_raw"].isna()
        | results["open_spaces_raw"].astype("string").str.strip().eq("")
    )
    results.loc[
        missing_observation & ~invalid_identifier,
        "exclusion_reason",
    ] = "missing_open_spaces"

    invalid_observation = (
        opened.isna() | opened.lt(0) | opened.ge(float("inf"))
        | opened.mod(1).ne(0)
    )
    results.loc[
        invalid_observation & ~missing_observation & ~invalid_identifier,
        "exclusion_reason",
    ] = "invalid_open_spaces"

    next_steps = {
        "level_scope_review": (
            "Verify the Inventory lot/category corresponding to the QPASS "
            "level before using a whole-facility capacity."
        ),
        "historical_verification_required":
            "Verify workbook timing and category scope before accepting capacity.",
        "missing_or_invalid_capacity":
            "Inspect the Inventory source rows and formula caches; verify capacity.",
        "zero_capacity_review":
            "Verify whether zero represents a closure, placeholder, or true capacity.",
        "open_spaces_exceed_candidate":
            "Check survey timing, category scope, and Inventory source rows.",
        "subtype_mapping_required":
            "Obtain a verified subtype/time-limit mapping; do not sum groups blindly.",
        "no_exact_inventory_key":
            "Check same-quarter coverage and verified facility/category mappings.",
    }
    results["recommended_next_step"] = results["comparison_status"].map(next_steps)
    results["unresolved_reason"] = (
        results["comparison_status"]
        + "; qpass_capacity=" + results["qpass_capacity_status"]
        + "; reported_totals=" + results["reported_capacity_comparison"]
    )
    excluded = results["exclusion_reason"].ne("")
    results.loc[excluded, "unresolved_reason"] += (
        "; observation=" + results.loc[excluded, "exclusion_reason"]
    )
    conflict = results["reported_capacity_comparison"].eq("conflict")
    results.loc[conflict, "recommended_next_step"] += (
        " Resolve the QPASS/Inventory total disagreement using dated source evidence."
    )
    results["verified_capacity_found"] = results["matched_capacity"].notna()

    eligible_for_summary = results.loc[
        results["exclusion_reason"].eq("")
    ].copy()
    summary = eligible_for_summary.groupby(
        ["academic_year", "quarter"]
    ).agg(
        observation_slots=("exact_key_found", "size"),
        exact_key_candidates=("exact_key_found", "sum"),
        verified_capacity_matches=("verified_capacity_found", "sum"),
    )
    summary["exact_key_candidate_rate"] = (
        summary["exact_key_candidates"] / summary["observation_slots"]
    )
    summary["verified_capacity_match_rate"] = (
        summary["verified_capacity_matches"] / summary["observation_slots"]
    )
    eligible_count = len(eligible_for_summary)
    overall = pd.DataFrame([{
        "observation_slots": len(results),
        "eligible_observation_slots": eligible_count,
        "excluded_observation_slots": len(results) - eligible_count,
        "exact_key_candidates": int(eligible_for_summary["exact_key_found"].sum()),
        "exact_key_candidate_rate": (
            eligible_for_summary["exact_key_found"].mean()
            if eligible_count else float("nan")
        ),
        "verified_capacity_matches": int(
            eligible_for_summary["verified_capacity_found"].sum()
        ),
        "verified_capacity_match_rate": (
            eligible_for_summary["verified_capacity_found"].mean()
            if eligible_count else float("nan")
        ),
    }])

    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_dir / "capacity_comparison.csv", index=False)
    summary.to_csv(output_dir / "quarter_summary.csv")
    overall.to_csv(output_dir / "overall_summary.csv", index=False)
    results.loc[results["matched_capacity"].isna()].to_csv(
        output_dir / "unresolved_cases.csv", index=False
    )
    results.loc[results["_merge"].eq("left_only")].to_csv(
        output_dir / "unmatched_records.csv", index=False
    )
    results.loc[
        results["reported_capacity_comparison"].eq("conflict")
        | results["open_spaces_exceed_candidate"]
    ].to_csv(output_dir / "conflicting_records.csv", index=False)


    print(f"Observation slots inspected: {len(results)}")
    print("\nComparison statuses:")
    print(results["comparison_status"].value_counts().to_string())
    print("\nReported capacity comparisons (all inspected slots):")
    print(results["reported_capacity_comparison"].value_counts().to_string())
    print("\nOverall summary for this invocation:")
    print(overall.to_string(index=False))
    print("\nQuarter summary:")
    print(summary.to_string())
    print(f"\nReports saved in: {output_dir}")
    print("Candidate rates are not verified capacity match rates.")
    print("Historical verification is pending; matched_capacity remains empty.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--qpass", required=True, type=Path)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/capacity_matching"),
    )
    args = parser.parse_args()

    compare_capacities(args.inventory, args.qpass, args.output_dir)