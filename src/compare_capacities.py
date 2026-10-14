"""Compare representative QPASS records with Inventory candidates."""

from pathlib import Path

import pandas as pd


KEYS = ["academic_year", "quarter", "facility", "category"]


def compare_capacities():
    inventory_path = Path(
        "data/interim/inventory/"
        "Inventory_2025-2026_Fall_capacity_groups.csv"
    )
    qpass_path = Path(
        "data/raw/qpass/QPASS 2025-2026-2 Fall.xlsm"
    )

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
    observations = []

    with pd.ExcelFile(qpass_path, engine="openpyxl") as workbook:
        for sheet in workbook.sheet_names:
            if not sheet.startswith("QPASS Data Entry (Week "):
                continue

            data = pd.read_excel(workbook, sheet_name=sheet, header=1)

            # Only actual Excel date values identify dated source records.
            dated = data["Date"].map(
                lambda value: isinstance(value, pd.Timestamp)
            )
            data = data.loc[
                dated & data["Location"].notna() & data["Type"].notna()
            ].copy()

            for index, row in data.iterrows():
                for time in ["8am", "10am", "12pm", "2pm"]:
                    observations.append({
                        "academic_year": "2025-2026",
                        "quarter": "Fall",
                        "facility": str(row["Location"]),
                        "category": str(row["Type"]),
                        "observation_date": row["Date"],
                        "observation_time": time,
                        "open_spaces_raw": row[f"Open Spaces {time}"],
                        "qpass_capacity_raw": row["Total\nStall\nCount"],
                        "qpass_source_file": qpass_path.name,
                        "qpass_source_sheet": sheet,
                        "qpass_source_row": index + 3,
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
    compare_capacities()