"""Validate current capacity-selection outputs and prepare compact PR artifacts."""

import argparse
from collections import Counter
import csv
import gzip
import json
from pathlib import Path
import shutil

import pandas as pd


REPORTS = ["capacity_comparison", "matched_records", "unresolved_cases",
           "unmatched_records", "conflicting_records"]


def prepare(root=Path(".")):
    """Validate real generated results before copying deterministic deliverables.

    This validates the documented selection policy, not independent source truth.
    Raise on inconsistent counts, source selection, scope, or raw preservation.
    """
    root = Path(root)
    batch = root / "results/capacity_matching/batch"
    destination = root / "results/capacity_matching/deliverables"
    overall = pd.read_csv(batch / "overall_summary.csv").iloc[0]
    quarters = pd.read_csv(batch / "quarter_summary.csv")
    coverage = pd.read_csv(batch / "inventory_coverage.csv", keep_default_na=False)
    groups = pd.read_csv(batch / "inventory_capacity_groups.csv", dtype=str, keep_default_na=False)
    inventory = pd.read_csv(batch / "inventory_cleaned.csv", dtype=str, keep_default_na=False)
    observations = pd.read_csv(batch / "combined/capacity_comparison.csv", dtype=str,
                               keep_default_na=False)
    keys = ["academic_year", "quarter", "facility", "category"]

    def check(condition, message):
        if not condition:
            raise ValueError(message)

    encode = lambda row: json.dumps(row, sort_keys=True, ensure_ascii=False)
    check(not inventory.duplicated(keys).any(), "Duplicate cleaned Inventory keys")
    check(not quarters.duplicated(keys[:2]).any(), "Duplicate quarter summaries")
    check(len(quarters) == len(coverage) == int(overall.qpass_quarters), "Coverage mismatch")
    check(Counter(encode(row) for row in groups.to_dict("records")) == Counter(
        encode(row) for value in inventory.source_groups_json for row in json.loads(value)
    ), "Raw Inventory group preservation failed")
    eligible = observations.exclusion_reason.eq("")
    accepted = observations.selected_capacity.ne("")
    qpass = accepted & observations.capacity_source.eq("qpass")
    fallback = accepted & observations.capacity_source.eq("inventory_same_quarter")
    counted = {
        "total_observation_slots": len(observations),
        "eligible_observation_slots": int(eligible.sum()),
        "excluded_observation_slots": int((~eligible).sum()),
        "exact_key_candidates": int((eligible & observations.exact_key_found.eq("True")).sum()),
        "accepted_qpass_capacities": int(qpass.sum()),
        "accepted_inventory_capacities": int(fallback.sum()),
        "accepted_capacity_matches": int(accepted.sum()),
    }
    for name, value in counted.items():
        check(value == int(overall[name]) == int(quarters[name].sum()), f"Count mismatch: {name}")
    check((qpass | fallback).eq(accepted).all(), "Unknown selected source")
    check(not (accepted & ~eligible).any(), "Excluded observation accepted")
    selected = pd.to_numeric(observations.loc[accepted, "selected_capacity"])
    opened = pd.to_numeric(observations.loc[accepted, "open_spaces_raw"])
    check((selected.gt(0) & selected.lt(float("inf")) & selected.mod(1).eq(0)).all(),
          "Invalid selected capacity")
    check((opened.ge(0) & opened.le(selected) & opened.mod(1).eq(0)).all(), "Invalid selected reading")
    check(observations.loc[qpass, "selected_capacity"].astype(float).eq(
        observations.loc[qpass, "qpass_capacity_raw"].astype(float)).all(), "QPASS source changed")
    check(observations.loc[fallback, "selected_capacity"].astype(float).eq(
        observations.loc[fallback, "candidate_capacity"].astype(float)).all(), "Fallback changed")
    check(observations.loc[fallback, "inventory_scope_compatible"].eq("True").all(), "Unsafe fallback scope")
    check(observations.loc[fallback, "inventory_group_count"].astype(float).eq(1).all(), "Ambiguous fallback")
    check(observations.loc[fallback, "inventory_single_capacity_status"].eq(
        "positive_unverified").all(), "Invalid Inventory accepted")
    check(observations.loc[fallback, "qpass_level_raw"].str.strip().eq("").all(), "Broad total used for level")
    check(observations.loc[fallback, "capacity_assumption"].ne("").all(), "Fallback assumption missing")
    check(observations.loc[accepted, "capacity_acceptance_reason"].ne("").all(), "Acceptance reason missing")
    check(observations.loc[~accepted, "unresolved_reason"].ne("").all(), "Unresolved reason missing")
    check(observations.loc[~accepted, "recommended_next_step"].ne("").all(), "Next step missing")
    for _, quarter in quarters.iterrows():
        mask = observations.academic_year.eq(quarter.academic_year) & observations.quarter.eq(quarter.quarter)
        check(int(mask.sum()) == int(quarter.total_observation_slots), "Quarter total mismatch")
        check(int((mask & eligible).sum()) == int(quarter.eligible_observation_slots), "Quarter eligible mismatch")
        check(int((mask & qpass).sum()) == int(quarter.accepted_qpass_capacities), "Quarter QPASS mismatch")
        check(int((mask & fallback).sum()) == int(quarter.accepted_inventory_capacities), "Quarter fallback mismatch")
        denominator = int(quarter.eligible_observation_slots)
        for rate, count in [("accepted_capacity_match_rate", "accepted_capacity_matches"),
                            ("accepted_qpass_capacity_rate", "accepted_qpass_capacities"),
                            ("accepted_inventory_capacity_rate", "accepted_inventory_capacities"),
                            ("exact_key_candidate_rate", "exact_key_candidates")]:
            check((pd.isna(quarter[rate]) if denominator == 0 else
                   abs(quarter[rate] - quarter[count] / denominator) < 1e-12), "Quarter rate mismatch")
    report_counts = {}
    for name in REPORTS:
        with (batch / "combined" / f"{name}.csv").open(newline="", encoding="utf-8") as handle:
            reader = csv.reader(handle)
            next(reader)
            report_counts[name] = sum(1 for _ in reader)
    check(report_counts["matched_records"] == int(accepted.sum()), "Matched report mismatch")
    check(report_counts["unresolved_cases"] == int((~accepted).sum()), "Unresolved report mismatch")
    manifest = root / "results/capacity_matching/inventory_sources.csv"
    with manifest.open(newline="", encoding="utf-8") as handle:
        sources = list(csv.DictReader(handle))
    audits = []
    for source in sources:
        if source["download_status"] not in {"downloaded", "already_present"}:
            continue
        stem = Path(source["inventory_path"]).stem
        paths = [root / "data/interim/inventory" / f"{stem}_{kind}_audit.json"
                 for kind in ("legacy", "modern")]
        existing = [path for path in paths if path.exists()]
        check(len(existing) == 1, f"Expected one regenerated workbook audit: {stem}")
        audits.append(json.loads(existing[0].read_text()))

    destination.mkdir(parents=True, exist_ok=True)
    for name in ["overall_summary.csv", "quarter_summary.csv", "inventory_coverage.csv"]:
        shutil.copyfile(batch / name, destination / name)
    for source in [batch / "inventory_cleaned.csv", batch / "inventory_capacity_groups.csv",
                   *[batch / "combined" / f"{name}.csv" for name in REPORTS]]:
        with source.open("rb") as handle, (destination / f"{source.name}.gz").open("wb") as output:
            with gzip.GzipFile(filename="", mode="wb", fileobj=output, mtime=0) as compressed:
                shutil.copyfileobj(handle, compressed)
    # Normalize record terminators so CSV output does not trigger Git CRLF warnings.
    (destination / manifest.name).write_bytes(manifest.read_bytes().replace(b"\r\n", b"\n"))
    (destination / "inventory_workbook_audits.json").write_text(json.dumps(audits, indent=2, default=str))
    # Older aggregate audits are superseded by current per-workbook audits.
    for name in ("inventory_schema_audit.json", "modern_inventory_audits.json"):
        (destination / name).unlink(missing_ok=True)
    validation = dict(checks_passed=True, policy="qpass_first_same_quarter_fallback",
                      counts=counted, report_counts=report_counts,
                      inventory_workbooks=len(audits), qpass_quarters=len(quarters))
    (destination / "validation.json").write_text(json.dumps(validation, indent=2))
    text = f"""# Capacity selection results

Generated from the real source files supplied to the pipeline; validation passed.
Inspected {len(observations):,} slots across {len(quarters)} QPASS quarters and
reviewed {len(audits)} available Inventory workbooks. Eligible: {int(eligible.sum()):,};
excluded: {int((~eligible).sum()):,}. Excluded records remain in reports.

- Exact standardized Inventory key candidates: {int(overall.exact_key_candidates):,} ({overall.exact_key_candidate_rate:.2%}).
- Accepted QPASS capacities: {int(qpass.sum()):,} ({overall.accepted_qpass_capacity_rate:.2%}).
- Assumed same-quarter Inventory fallbacks: {int(fallback.sum()):,} ({overall.accepted_inventory_capacity_rate:.2%}).
- All accepted capacities: {int(accepted.sum()):,} ({overall.accepted_capacity_match_rate:.2%}).
- Unresolved slots: {int((~accepted).sum()):,}. Conflicting slots: {report_counts['conflicting_records']:,}.

Candidate rates describe Inventory key coverage, not accepted capacity coverage.
All rates use eligible slots; overall rates divide summed counts.

| Academic year | Quarter | Total | Eligible | QPASS | Inventory fallback | Accepted rate |
|---|---|---:|---:|---:|---:|---:|
"""
    for _, row in quarters.iterrows():
        text += (f"| {row.academic_year} | {row.quarter} | {int(row.total_observation_slots)} "
                 f"| {int(row.eligible_observation_slots)} | {int(row.accepted_qpass_capacities)} "
                 f"| {int(row.accepted_inventory_capacities)} | {row.accepted_capacity_match_rate:.2%} |\n")
    text += "\n## Remaining unresolved types\n\n"
    for name, count in observations.loc[~accepted, "unresolved_type"].value_counts().items():
        text += f"- {name}: {count:,}.\n"
    text += """

## Policy, assumptions and source limitations

QPASS's own positive integer capacity is preferred for its exact source group.
Known errors, ambiguous groups, and comparable contradictory evidence block it.
Missing or demonstrably broken QPASS counts may use one positive, scope-compatible
same-quarter Inventory group. This fallback is an assumption, not proof of capacity
on each survey day. Unknown zeros alone do not justify fallback. Raw values, formulas'
cached values, source rows, labels and Issue #3 restriction decisions are preserved.
No fuzzy aliases, cross-quarter capacity carry, whole-structure-to-level substitution,
or broad-category-to-subtype substitution is allowed. Time-limit mappings that are
not explicitly established remain unresolved. Valid QPASS capacities do not require
Inventory coverage; missing Inventory does not invalidate their own row-specific total.

Fall 2025–2026's documented zero-capacity formula error remains a source-data flag,
even where Inventory fallback is accepted. Two known copied non-observations are
excluded if their exact provenance matches the documented row. Winter 2024–2025
Inventory period metadata conflicts block Inventory fallback, not an otherwise valid
QPASS capacity. Missing Inventory quarters and still-unresolved label decisions remain
separate from scope and count conflicts. Selected capacities are historical source-based
values, not a guarantee of live availability or permit eligibility.

Reproduce from the repository root:

```bash
python -m src.download_inventory
python -m src.run_capacity_matching --rebuild-inventory
python scripts/prepare_capacity_deliverables.py
python -m pytest -q
```

See docs/inventory_audit.md for setup and schema details. Deliverables are in
results/capacity_matching/deliverables; pandas.read_csv supports .csv.gz directly.
The real-workbook run and tests are separate validation steps; this report does not
claim a test count. Raw workbooks are unchanged and are not included in Git.
"""
    (root / "docs/capacity_matching_summary.md").write_text(text, encoding="utf-8")
    (destination / "README.md").write_text(text, encoding="utf-8")
    print("Validation passed. Prepared deliverables:")
    for path in sorted(destination.iterdir()):
        print(f"{path.name}: {path.stat().st_size / 1024**2:.2f} MB")
    return validation


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    prepare(parser.parse_args().root)
