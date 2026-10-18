"""Validate generated ParkSmart outputs and prepare compact PR deliverables."""

import csv
import gzip
import json
import shutil
from collections import Counter
from pathlib import Path

import pandas as pd


root = Path.cwd()
batch = root / "results/capacity_matching/batch"
destination = root / "results/capacity_matching/deliverables"
overall = pd.read_csv(batch / "overall_summary.csv").iloc[0]
quarters = pd.read_csv(batch / "quarter_summary.csv")
coverage = pd.read_csv(batch / "inventory_coverage.csv", keep_default_na=False)
groups = pd.read_csv(batch / "inventory_capacity_groups.csv", dtype=str, keep_default_na=False)
inventory = pd.read_csv(batch / "inventory_cleaned.csv", dtype=str, keep_default_na=False)
keys = ["academic_year", "quarter", "facility", "category"]
assert not inventory.duplicated(keys).any(), "Duplicate cleaned Inventory keys"
assert not quarters.duplicated(["academic_year", "quarter"]).any(), "Duplicate quarter summaries"
assert len(quarters) == len(coverage) == int(overall.qpass_quarters), "Quarter coverage count mismatch"

# Compare every raw source group, including fields differing between schemas.
encode = lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False)
original_groups = Counter(encode(row) for row in groups.to_dict("records"))
preserved_groups = Counter(
    encode(row) for value in inventory.source_groups_json for row in json.loads(value)
)
assert original_groups == preserved_groups, "Raw source group preservation failed"

fields = [*keys, "matched_capacity", "candidate_capacity", "qpass_capacity_raw",
          "observation_date", "inventory_snapshot_date", "open_spaces_raw",
          "qpass_level_raw", "qpass_subtype_raw", "exclusion_reason", "exact_key_found",
          "capacity_acceptance_basis", "comparison_status", "unresolved_reason",
          "recommended_next_step"]
observations = pd.read_csv(batch / "combined/capacity_comparison.csv",
                           usecols=fields, dtype=str, keep_default_na=False)
accepted = observations.matched_capacity.ne("")
eligible = observations.exclusion_reason.eq("")
assert len(observations) == int(overall.observation_slots), "Inspected count mismatch"
assert int(eligible.sum()) == int(overall.eligible_observation_slots), "Eligible count mismatch"
assert int((~eligible).sum()) == int(overall.excluded_observation_slots), "Excluded count mismatch"
assert int(accepted.sum()) == int(overall.verified_capacity_matches), "Accepted count mismatch"
assert int((eligible & observations.exact_key_found.eq("True")).sum()) == int(overall.exact_key_candidates), "Candidate count mismatch"
assert observations.loc[accepted, "exclusion_reason"].eq("").all(), "Excluded observation accepted"
matched = observations.loc[accepted]
capacity = pd.to_numeric(matched.matched_capacity)
assert capacity.gt(0).all() and capacity.mod(1).eq(0).all(), "Invalid accepted capacity"
assert capacity.eq(pd.to_numeric(matched.qpass_capacity_raw)).all(), "Reported totals disagree"
assert capacity.eq(pd.to_numeric(matched.candidate_capacity)).all(), "Inventory totals disagree"
opened = pd.to_numeric(matched.open_spaces_raw)
assert opened.ge(0).all() and opened.le(capacity).all(), "Open counts exceed accepted capacity"
assert pd.to_datetime(matched.observation_date).eq(pd.to_datetime(matched.inventory_snapshot_date)).all(), "Accepted outside snapshot date"
assert matched.qpass_level_raw.str.strip().eq("").all(), "Unverified level accepted"
assert matched.qpass_subtype_raw.str.strip().eq("").all(), "Unverified subtype accepted"
assert matched.capacity_acceptance_basis.ne("").all(), "Acceptance evidence missing"
unresolved = observations.loc[~accepted]
assert unresolved.unresolved_reason.ne("").all(), "Unresolved reason missing"
assert unresolved.recommended_next_step.ne("").all(), "Recommended next step missing"

for _, quarter in quarters.iterrows():
    selected = observations.academic_year.eq(quarter.academic_year) & observations.quarter.eq(quarter.quarter)
    assert int((selected & eligible).sum()) == int(quarter.observation_slots), "Quarter denominator mismatch"
    assert int((selected & accepted).sum()) == int(quarter.verified_capacity_matches), "Quarter accepted count mismatch"

report_names = ["capacity_comparison", "matched_records", "unresolved_cases", "unmatched_records", "conflicting_records"]
report_counts = {}
for name in report_names:
    with (batch / "combined" / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
        reader = csv.reader(handle)
        next(reader)
        report_counts[name] = sum(1 for _ in reader)
assert report_counts["matched_records"] == int(accepted.sum())
assert report_counts["unresolved_cases"] == len(observations) - int(accepted.sum())

# Only create delivery copies after validation succeeds.
destination.mkdir(parents=True, exist_ok=True)
for name in ["overall_summary.csv", "quarter_summary.csv", "inventory_coverage.csv"]:
    shutil.copyfile(batch / name, destination / name)
for source in [batch / "inventory_cleaned.csv", batch / "inventory_capacity_groups.csv",
               *[batch / "combined" / f"{name}.csv" for name in report_names]]:
    with source.open("rb") as handle, (destination / f"{source.name}.gz").open("wb") as output:
        with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
            shutil.copyfileobj(handle, compressed)

for name in ["inventory_sources.csv", "inventory_schema_audit.json", "modern_inventory_audits.json"]:
    source = root / "results/capacity_matching" / name
    if source.exists():
        shutil.copyfile(source, destination / name)
with (root / "results/capacity_matching/inventory_sources.csv").open(newline="", encoding="utf-8") as handle:
    sources = list(csv.DictReader(handle))
audits = []
for source in sources:
    if source["download_status"] not in {"downloaded", "already_present"}:
        continue
    stem = Path(source["inventory_path"]).stem
    candidates = [root / "data/interim/inventory" / f"{stem}_{kind}_audit.json" for kind in ("legacy", "modern")]
    existing = [p for p in candidates if p.exists()]
    if len(existing) != 1:
        raise SystemExit(f"Expected one audit for {stem}; inspect data/interim/inventory")
    audits.append(json.loads(existing[0].read_text()))
(destination / "inventory_workbook_audits.json").write_text(json.dumps(audits, indent=2, default=str))

validation = {
    "checks_passed": True, "qpass_quarters": len(quarters),
    "inventory_workbooks": len(audits), "inventory_source_groups": len(groups),
    "unique_inventory_keys": len(inventory), "report_counts": report_counts,
    "accepted_capacity_policy": "same_day_legacy_inventory_and_qpass_agreement",
}
(destination / "validation.json").write_text(json.dumps(validation, indent=2))

text = f"""# Inventory capacity matching summary

The pipeline inspected {len(observations):,} observation slots across {len(quarters)} QPASS quarters.
Inventory was available for {len(audits)} quarters. The cleaned dataset contains {len(inventory):,}
unique academic-year/quarter/facility/category keys, preserving all {len(groups):,} source groups.

- Eligible observation slots: {int(eligible.sum()):,}.
- Excluded observation slots: {int((~eligible).sum()):,}; these remain in detailed reports.
- Exact-key candidates: {int(overall.exact_key_candidates):,} ({overall.exact_key_candidate_rate:.2%}).
- Accepted capacities: {int(accepted.sum()):,} ({overall.verified_capacity_match_rate:.2%} of eligible slots).
- Unresolved inspected slots: {len(unresolved):,}, including excluded slots.
- Conflicting inspected slots: {report_counts['conflicting_records']:,}.

Candidate rates count matching keys even when capacity is invalid or blocked. Accepted rates
use the documented snapshot policy. Overall rates divide summed counts, not quarterly rates.

| Academic year | Quarter | Eligible slots | Candidates | Accepted | Accepted rate |
|---|---|---:|---:|---:|---:|
"""
for _, row in quarters.iterrows():
    text += f"| {row.academic_year} | {row.quarter} | {int(row.observation_slots):,} | {int(row.exact_key_candidates):,} | {int(row.verified_capacity_matches):,} | {row.verified_capacity_match_rate:.2%} |\n"
text += """
## Acceptance and unresolved cases

Acceptance currently supports audited legacy lot reports on their snapshot date only. The filename,
table title, year and quarter must agree. A unique positive Inventory capacity must equal the QPASS
total, with no level/subtype/time-limit qualification or conflicting key/date observations.
The dated report is assumed to represent capacity on its snapshot day. No capacity is carried to
another day, another quarter, or another facility/category. This is a conservative acceptance policy,
not an independent certification of all source counts. Most observations remain unresolved.

Modern observations need additional dated evidence before acceptance. Winter 2024-2025 has
conflicting metadata: the cover says Winter, while the data selector says Spring 2025. Its
627 groups remain blocked. Fall 2026-2027 Inventory was not listed in the archive at download
time and its QPASS records remain unmatched. Teammate facility/category aliases have not
been applied; current joins use exact raw labels with surrounding whitespace removed.
Blank, zero, construction-closure, duplicate-group and invalid counts retain review flags.
Lot and structure totals overlap and are never summed together.

Each unresolved/conflicting row preserves QPASS source file, sheet, row, date/time, raw facility,
category and reported capacity, Inventory candidates and source rows, reason and recommended action.
Inspect these rows and obtain dated capacity or verified scope/name mappings before accepting more.

## Reproduce the outputs

From the repository root with the virtual environment activated and dependencies installed:

```bash
python -m src.download_inventory
```

This downloads Inventory files for locally available QPASS periods without replacing originals.
For each available source, use its verified year and quarter from inventory_sources.csv:

```bash
python -m src.clean_inventory_legacy "data/raw/inventory/WORKBOOK.xlsx" --academic-year YYYY-YYYY --quarter QUARTER
python -m src.clean_inventory_modern "data/raw/inventory/WORKBOOK.xlsm" --academic-year YYYY-YYYY --quarter QUARTER
```

Use the legacy cleaner for the 2018-2019/2019-2020 summary-table files and the modern cleaner
for newer layouts. These commands produce group CSVs and workbook audits. Then run:

```bash
python -m src.run_capacity_matching
python -m pytest
```

Batch outputs are in results/capacity_matching/batch. The latest full test run passed 186 tests.
Delivery copies are in results/capacity_matching/deliverables. Compressed CSVs preserve all columns
and records and can be opened with pandas.read_csv("FILE.csv.gz"). Original raw workbooks are not
included in the deliverables. See docs/inventory_audit.md for schema notes and further assumptions.
"""
(root / "docs/capacity_matching_summary.md").write_text(text, encoding="utf-8")
(destination / "README.md").write_text(text, encoding="utf-8")
print("Validation passed. Prepared delivery files:")
for path in sorted(destination.iterdir()):
    print(f"{path.name}: {path.stat().st_size / 1024 / 1024:.2f} MB")
print("Saved docs/capacity_matching_summary.md")
print("No files have been staged or committed.")
