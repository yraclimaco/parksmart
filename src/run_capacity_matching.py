"""Run all manifest quarters, including those without an Inventory workbook."""

import argparse
import csv
import json
import re
from pathlib import Path

import pandas as pd

from src.compare_capacities import compare_capacities
from src.capacity_labels import label_inventory
from src.clean_inventory_legacy import clean_legacy_inventory
from src.clean_inventory_modern import clean_modern_inventory


KEYS = ["academic_year", "quarter", "facility", "category"]
AVAILABLE = {"downloaded", "already_present"}
REPORTS = ["capacity_comparison", "matched_records", "unresolved_cases",
           "unmatched_records", "conflicting_records"]
EMPTY_GROUP_COLUMNS = [*KEYS, "facility_raw", "category_raw", "capacity",
                       "capacity_status", "source_file", "source_rows"]
CLEANED_COLUMNS = [*KEYS, "facility_raw", "category_raw", "capacity",
                   "capacity_status", "source_file", "inventory_group_count",
                   "source_groups_json"]


def build_inventory_dataset(groups):
    """Produce one row per period/facility/category without summing ambiguous groups.

    Preserve every contributing source row and raw value in source_groups_json.
    Join labels use Issue #3 decisions; every input group remains in
    source_groups_json.

    Args:
        groups: Extracted Inventory group DataFrame with period, raw labels,
        capacity/status and source_file.

    Returns:
        Cleaned DataFrame with unique KEYS and lossless source_groups_json; empty
        input retains the output schema.
    """
    groups = groups.copy()
    groups["_source_record_json"] = [json.dumps(row, default=str)
                                      for row in groups.to_dict("records")]
    groups = label_inventory(groups)
    output = []
    for key, group in groups.groupby(KEYS, dropna=False, sort=False):
        row = dict(zip(KEYS, key))
        row.update({
            "facility_raw": group["facility_raw"].iloc[0],
            "category_raw": group["category_raw"].iloc[0],
            "capacity": group["capacity"].iloc[0] if len(group) == 1 else pd.NA,
            "capacity_status": group["capacity_status"].iloc[0] if len(group) == 1
                else "multiple_inventory_groups_review",
            "source_file": ";".join(group["source_file"].unique()),
            "inventory_group_count": len(group),
            "source_groups_json": "[" + ",".join(group["_source_record_json"]) + "]",
        })
        output.append(row)
    return pd.DataFrame(output, columns=CLEANED_COLUMNS)


def combine_rates(quarters):
    """Sum quarter counts and calculate rates using eligible observations.

    Args:
        quarters: Quarter-summary DataFrame containing observation and source-
        specific accepted counts.

    Returns:
        Dictionary of summed counts and weighted rates; zero denominator gives
        None.
    """
    count_columns = ["total_observation_slots", "eligible_observation_slots",
                     "excluded_observation_slots", "exact_key_candidates",
                     "accepted_qpass_capacities", "accepted_inventory_capacities",
                     "accepted_capacity_matches"]
    total = {name: int(quarters[name].sum()) for name in count_columns}
    total["qpass_quarters"] = len(quarters)
    denominator = total["eligible_observation_slots"]
    for rate, count in {
        "exact_key_candidate_rate": "exact_key_candidates",
        "accepted_qpass_capacity_rate": "accepted_qpass_capacities",
        "accepted_inventory_capacity_rate": "accepted_inventory_capacities",
        "accepted_capacity_match_rate": "accepted_capacity_matches",
    }.items():
        total[rate] = total[count] / denominator if denominator else None
    return total


def run_capacity_matching(manifest=Path("results/capacity_matching/inventory_sources.csv"),
                          qpass_dir=Path("data/raw/QPASS"),
                          inventory_dir=Path("data/interim/inventory"),
                          output_dir=Path("results/capacity_matching/batch"),
                          rebuild_inventory=False):
    """Run every manifest quarter and write combined evidence-preserving reports.

    Source workbooks and cleaned group inputs are not modified. Quarter folders
    inside output_dir and combined outputs are regenerated. Empty Inventory is
    represented by a header-only CSV, so missing quarters remain in denominators.

    Args:
        manifest: Source manifest CSV path. qpass_dir: Original QPASS folder.
        inventory_dir: Extracted groups folder. output_dir: Regenerated reports
        folder. rebuild_inventory: Whether to reread original workbooks.

    Returns:
        Tuple of quarter DataFrame and overall count/rate dictionary. Writes
        reports, groups and audits; originals remain unchanged. Raises for invalid
        manifest or unavailable required inputs.
    """
    manifest, qpass_dir, inventory_dir, output_dir = map(
        Path, (manifest, qpass_dir, inventory_dir, output_dir)
    )
    with manifest.open(newline="", encoding="utf-8") as handle:
        records = list(csv.DictReader(handle))
    if not records:
        raise ValueError("Inventory source manifest is empty")
    periods = [(r["academic_year"], r["quarter"]) for r in records]
    if len(periods) != len(set(periods)):
        raise ValueError("Manifest contains repeated quarters; resolve duplicate sources first")
    for record in records:
        if not re.fullmatch(r"\d{4}-\d{4}", record["academic_year"]):
            raise ValueError("Manifest contains an invalid academic year")
        if record["quarter"] not in {"Summer", "Fall", "Winter", "Spring"}:
            raise ValueError("Manifest contains an invalid quarter")
        if Path(record["qpass_file"]).name != record["qpass_file"]:
            raise ValueError("QPASS manifest entry must be a filename")
        qpass = qpass_dir / record["qpass_file"]
        if not qpass.is_file():
            raise FileNotFoundError(qpass)
        if record["download_status"] in AVAILABLE:
            inventory = inventory_dir / (Path(record["inventory_path"]).stem + "_capacity_groups.csv")
            required = Path(record["inventory_path"]) if rebuild_inventory else inventory
            if not required.is_file():
                raise FileNotFoundError(required)

    output_dir.mkdir(parents=True, exist_ok=True)
    empty_inventory = output_dir / "empty_inventory.csv"
    pd.DataFrame(columns=["academic_year", "quarter", "facility_raw", "category_raw",
                          "capacity", "capacity_status", "source_file", "source_rows"]
                 ).to_csv(empty_inventory, index=False)
    combined_dir = output_dir / "combined"
    combined_dir.mkdir(exist_ok=True)
    for report in REPORTS:
        (combined_dir / f"{report}.csv").unlink(missing_ok=True)
    quarter_summaries, inventory_groups, coverage = [], [], []
    for record in records:
        year, quarter = record["academic_year"], record["quarter"]
        available = record["download_status"] in AVAILABLE
        inventory = inventory_dir / (Path(record["inventory_path"]).stem + "_capacity_groups.csv") if available else empty_inventory
        if available and rebuild_inventory:
            cleaner = (clean_legacy_inventory if int(year[:4]) < 2024
                       else clean_modern_inventory)
            inventory = cleaner(Path(record["inventory_path"]), year, quarter, inventory_dir)
        quarter_dir = output_dir / f"{year}_{quarter.lower()}"
        print(f"\n=== {year} {quarter} ===", flush=True)
        compare_capacities(inventory, qpass_dir / record["qpass_file"], quarter_dir)
        quarter_summary = pd.read_csv(quarter_dir / "quarter_summary.csv")
        quarter_summary["inventory_coverage_status"] = record["download_status"]
        quarter_summaries.append(quarter_summary)
        coverage.append({"academic_year": year, "quarter": quarter,
                         "qpass_file": record["qpass_file"],
                         "inventory_coverage_status": record["download_status"],
                         "source_manifest_reason": record.get("reason", "")})
        if available:
            inventory_groups.append(pd.read_csv(inventory, dtype=str, keep_default_na=False))
        for report in REPORTS:
            path = quarter_dir / f"{report}.csv"
            frame = pd.read_csv(path, dtype=str, keep_default_na=False)
            frame["inventory_coverage_status"] = record["download_status"]
            if not available and not frame.empty:
                unresolved = frame["selected_capacity"].eq("")
                # Missing Inventory never invalidates an accepted QPASS capacity.
                missing = unresolved & frame["unresolved_type"].isin(
                    ["inventory_key_unmatched", "inventory_capacity_review"]
                )
                frame.loc[missing, "unresolved_type"] = "missing_inventory"
                frame.loc[missing, "unresolved_reason"] += "; inventory_workbook_unavailable"
                frame.loc[missing, "recommended_next_step"] = (
                    "Locate this quarter's Inventory; do not substitute another period."
                )
            destination = combined_dir / f"{report}.csv"
            frame.to_csv(destination, mode="a", header=not destination.exists(), index=False)

    quarters = pd.concat(quarter_summaries, ignore_index=True)
    quarters.to_csv(output_dir / "quarter_summary.csv", index=False)
    pd.DataFrame(coverage).to_csv(output_dir / "inventory_coverage.csv", index=False)
    total = combine_rates(quarters)
    pd.DataFrame([total]).to_csv(output_dir / "overall_summary.csv", index=False)
    if inventory_groups:
        groups = pd.concat(inventory_groups, ignore_index=True).fillna("")
    else:
        # Replace prior-run files even when this manifest has no Inventory.
        groups = pd.DataFrame(columns=EMPTY_GROUP_COLUMNS)
    groups.to_csv(output_dir / "inventory_capacity_groups.csv", index=False)
    build_inventory_dataset(groups).to_csv(output_dir / "inventory_cleaned.csv", index=False)
    print("\nBatch overall summary:")
    print(pd.DataFrame([total]).to_string(index=False))
    print(f"\nCombined reports saved in {output_dir}")
    return quarters, total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rebuild-inventory", action="store_true",
                        help="Re-extract every available original workbook before matching")
    parser.add_argument("--manifest", type=Path, default=Path("results/capacity_matching/inventory_sources.csv"))
    parser.add_argument("--qpass-dir", type=Path, default=Path("data/raw/QPASS"))
    parser.add_argument("--inventory-dir", type=Path, default=Path("data/interim/inventory"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/capacity_matching/batch"))
    args = parser.parse_args()
    run_capacity_matching(args.manifest, args.qpass_dir, args.inventory_dir,
                          args.output_dir, args.rebuild_inventory)
