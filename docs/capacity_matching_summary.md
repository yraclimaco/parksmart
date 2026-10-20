# Capacity selection results

Generated from the real source files supplied to the pipeline; validation passed.
Inspected 93,712 slots across 15 QPASS quarters and
reviewed 14 available Inventory workbooks. Eligible: 88,025;
excluded: 5,687. Excluded records remain in reports.

- Exact standardized Inventory key candidates: 65,115 (73.97%).
- Accepted QPASS capacities: 69,577 (79.04%).
- Assumed same-quarter Inventory fallbacks: 2,932 (3.33%).
- All accepted capacities: 72,509 (82.37%).
- Unresolved slots: 21,203. Conflicting slots: 8,024.

Candidate rates describe Inventory key coverage, not accepted capacity coverage.
All rates use eligible slots; overall rates divide summed counts.

| Academic year | Quarter | Total | Eligible | QPASS | Inventory fallback | Accepted rate |
|---|---|---:|---:|---:|---:|---:|
| 2018-2019 | Summer | 10620 | 9670 | 8466 | 0 | 87.55% |
| 2018-2019 | Fall | 10784 | 10117 | 9550 | 0 | 94.40% |
| 2018-2019 | Winter | 5760 | 5584 | 5251 | 0 | 94.04% |
| 2018-2019 | Spring | 4240 | 4087 | 3351 | 0 | 81.99% |
| 2019-2020 | Summer | 4480 | 3719 | 3303 | 0 | 88.81% |
| 2019-2020 | Fall | 4720 | 4643 | 3716 | 0 | 80.03% |
| 2024-2025 | Summer | 4360 | 3912 | 3460 | 0 | 88.45% |
| 2024-2025 | Fall | 5376 | 5276 | 4568 | 0 | 86.58% |
| 2024-2025 | Winter | 4360 | 4301 | 3948 | 0 | 91.79% |
| 2024-2025 | Spring | 5600 | 5600 | 4712 | 0 | 84.14% |
| 2025-2026 | Summer | 5440 | 4380 | 3877 | 0 | 88.52% |
| 2025-2026 | Fall | 6676 | 6520 | 0 | 2932 | 44.97% |
| 2025-2026 | Spring | 6400 | 6112 | 4043 | 0 | 66.15% |
| 2026-2027 | Summer | 6880 | 6120 | 3396 | 0 | 55.49% |
| 2026-2027 | Fall | 8016 | 7984 | 7936 | 0 | 99.40% |

## Remaining unresolved types

- scope_conflict: 6,063.
- invalid_observation: 5,411.
- capacity_conflict: 5,153.
- source_data_problem: 3,312.
- mapping_review: 464.
- inventory_capacity_review: 424.
- invalid_identifier: 276.
- inventory_key_unmatched: 64.
- period_metadata_conflict: 36.


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
