"""Run all manifest quarters, including those without an Inventory workbook."""

import argparse
import csv
import json
import re
from pathlib import Path

import pandas as pd

from src.compare_capacities import compare_capacities


KEYS = ["academic_year", "quarter", "facility", "category"]
AVAILABLE = {"downloaded", "already_present"}
REPORTS = ["capacity_comparison", "matched_records", "unresolved_cases",
           "unmatched_records", "conflicting_records"]


def build_inventory_dataset(groups):
    """Produce one row per period/facility/category without summing ambiguous groups.

    Preserve every contributing source row and raw value in source_groups_json.
    Join labels are exact source labels with surrounding whitespace removed;
    teammate identifier mappings have not been applied.
    """
    groups = groups.copy()
    groups["_source_record_json"] = [json.dumps(row, default=str)
                                      for row in groups.to_dict("records")]
    groups["facility"] = groups["facility_raw"].astype(str).str.strip()
    groups["category"] = groups["category_raw"].astype(str).str.strip()
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
    return pd.DataFrame(output)


def combine_rates(quarters):
    """Calculate weighted overall rates using counts rather than averaging rates."""
    eligible = int(quarters["observation_slots"].sum())
    exact = int(quarters["exact_key_candidates"].sum())
    accepted = int(quarters["verified_capacity_matches"].sum())
    return {
        "qpass_quarters": len(quarters), "eligible_observation_slots": eligible,
        "exact_key_candidates": exact,
        "exact_key_candidate_rate": exact / eligible if eligible else None,
        "verified_capacity_matches": accepted,
        "verified_capacity_match_rate": accepted / eligible if eligible else None,
    }


def run_capacity_matching(manifest=Path("results/capacity_matching/inventory_sources.csv"),
                          qpass_dir=Path("data/raw/QPASS"),
                          inventory_dir=Path("data/interim/inventory"),
                          output_dir=Path("results/capacity_matching/batch")):
    """Run every manifest quarter and write combined evidence-preserving reports.

    Source workbooks and cleaned group inputs are not modified. Quarter folders
    inside output_dir and combined outputs are regenerated. Empty Inventory is
    represented by a header-only CSV, so missing quarters remain in denominators.
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
            if not inventory.is_file():
                raise FileNotFoundError(inventory)

    output_dir.mkdir(parents=True, exist_ok=True)
    empty_inventory = output_dir / "empty_inventory.csv"
    pd.DataFrame(columns=["academic_year", "quarter", "facility_raw", "category_raw",
                          "capacity", "capacity_status", "source_file", "source_rows"]
                 ).to_csv(empty_inventory, index=False)
    combined_dir = output_dir / "combined"
    combined_dir.mkdir(exist_ok=True)
    for report in REPORTS:
        (combined_dir / f"{report}.csv").unlink(missing_ok=True)
    quarter_summaries, overall_counts, inventory_groups, coverage = [], [], [], []
    for record in records:
        year, quarter = record["academic_year"], record["quarter"]
        available = record["download_status"] in AVAILABLE
        inventory = inventory_dir / (Path(record["inventory_path"]).stem + "_capacity_groups.csv") if available else empty_inventory
        quarter_dir = output_dir / f"{year}_{quarter.lower()}"
        print(f"\n=== {year} {quarter} ===", flush=True)
        compare_capacities(inventory, qpass_dir / record["qpass_file"], quarter_dir)
        quarter_summary = pd.read_csv(quarter_dir / "quarter_summary.csv")
        if quarter_summary.empty:
            quarter_summary = pd.DataFrame([{
                "academic_year": year, "quarter": quarter, "observation_slots": 0,
                "exact_key_candidates": 0, "verified_capacity_matches": 0,
                "exact_key_candidate_rate": float("nan"),
                "verified_capacity_match_rate": float("nan"),
            }])
        quarter_summary["inventory_coverage_status"] = record["download_status"]
        quarter_summaries.append(quarter_summary)
        overall_counts.append(pd.read_csv(quarter_dir / "overall_summary.csv"))
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
                frame["comparison_status"] = "inventory_workbook_unavailable"
                frame["unresolved_reason"] = (
                    "inventory_workbook_unavailable; " + record["download_status"]
                    + "; " + frame["capacity_acceptance_reason"]
                )
                frame["recommended_next_step"] = (
                    "Locate and verify this quarter's Inventory workbook; do not substitute another quarter."
                )
            destination = combined_dir / f"{report}.csv"
            frame.to_csv(destination, mode="a", header=not destination.exists(), index=False)

    quarters = pd.concat(quarter_summaries, ignore_index=True)
    quarters.to_csv(output_dir / "quarter_summary.csv", index=False)
    pd.DataFrame(coverage).to_csv(output_dir / "inventory_coverage.csv", index=False)
    total = combine_rates(quarters)
    counts = pd.concat(overall_counts, ignore_index=True)
    total["observation_slots"] = int(counts["observation_slots"].sum())
    total["excluded_observation_slots"] = int(counts["excluded_observation_slots"].sum())
    pd.DataFrame([total]).to_csv(output_dir / "overall_summary.csv", index=False)
    if inventory_groups:
        groups = pd.concat(inventory_groups, ignore_index=True).fillna("")
        groups.to_csv(output_dir / "inventory_capacity_groups.csv", index=False)
        build_inventory_dataset(groups).to_csv(output_dir / "inventory_cleaned.csv", index=False)
    print("\nBatch overall summary:")
    print(pd.DataFrame([total]).to_string(index=False))
    print(f"\nCombined reports saved in {output_dir}")
    return quarters, total


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=Path("results/capacity_matching/inventory_sources.csv"))
    parser.add_argument("--qpass-dir", type=Path, default=Path("data/raw/QPASS"))
    parser.add_argument("--inventory-dir", type=Path, default=Path("data/interim/inventory"))
    parser.add_argument("--output-dir", type=Path, default=Path("results/capacity_matching/batch"))
    args = parser.parse_args()
    run_capacity_matching(args.manifest, args.qpass_dir, args.inventory_dir, args.output_dir)
