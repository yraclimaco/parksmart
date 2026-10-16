"""Compare representative QPASS records with Inventory candidates."""

import argparse
from pathlib import Path

import pandas as pd
from src.qpass_loader import load_qpass


KEYS = ["academic_year", "quarter", "facility", "category"]


def compare_capacities(inventory_path, qpass_path):
    """Compare a cleaned Inventory CSV with a QPASS workbook.

    Args:
        inventory_path: Path to the extracted Inventory capacity CSV.
        qpass_path: Path to the QPASS workbook.

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
    inventory["facility"] = inventory["facility_raw"]
    inventory["category"] = inventory["category_raw"]

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
        record["candidate_capacity"] = (
            group["capacity"].iloc[0] if len(group) == 1 else pd.NA
        )
        candidates.append(record)

    candidates = pd.DataFrame(candidates)
    qpass = load_qpass(qpass_path)

    # Save the loader's audit information before transforming its output.
    import json

    audit_dir = Path("results/capacity_matching")
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
                "facility": str(row["location"]),
                "category": str(row["type"]),
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

    missing_observation = results["open_spaces_raw"].isna()
    results.loc[
        missing_observation & ~invalid_identifier,
        "exclusion_reason",
    ] = "missing_open_spaces"

    eligible_for_summary = results.loc[
        results["exclusion_reason"].eq("")
    ].copy()
    summary = eligible_for_summary.groupby(
        ["academic_year", "quarter"]
    ).agg(
        observation_slots=("exact_key_found", "size"),
        exact_key_candidates=("exact_key_found", "sum"),
    )
    summary["exact_key_candidate_rate"] = (
        summary["exact_key_candidates"] / summary["observation_slots"]
    )
    summary["verified_capacity_match_rate"] = 0.0

    output_dir = Path("results/capacity_matching")
    output_dir.mkdir(parents=True, exist_ok=True)
    results.to_csv(output_dir / "capacity_comparison.csv", index=False)
    summary.to_csv(output_dir / "quarter_summary.csv")

    print(f"Observation slots inspected: {len(results)}")
    print("\nComparison statuses:")
    print(results["comparison_status"].value_counts().to_string())
    print("\nQuarter summary:")
    print(summary.to_string())
    print(f"\nReports saved in: {output_dir}")
    print("Candidate rates are not verified capacity match rates.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--qpass", required=True, type=Path)
    args = parser.parse_args()

    compare_capacities(args.inventory, args.qpass)