# Inventory capacity matching summary

The pipeline inspected 93,712 observation slots across 15 QPASS quarters.
Inventory was available for 14 quarters. The cleaned dataset contains 16,554
unique academic-year/quarter/facility/category keys, preserving all 17,368 source groups.

- Eligible observation slots: 88,267.
- Excluded observation slots: 5,445; these remain in detailed reports.
- Exact-key candidates: 62,106 (70.36%).
- Accepted capacities: 604 (0.68% of eligible slots).
- Unresolved inspected slots: 93,108, including excluded slots.
- Conflicting inspected slots: 5,392.

Candidate rates count matching keys even when capacity is invalid or blocked. Accepted rates
use the documented snapshot policy. Overall rates divide summed counts, not quarterly rates.

| Academic year | Quarter | Eligible slots | Candidates | Accepted | Accepted rate |
|---|---|---:|---:|---:|---:|
| 2018-2019 | Summer | 9,702 | 9,543 | 0 | 0.00% |
| 2018-2019 | Fall | 10,189 | 6,733 | 192 | 1.88% |
| 2018-2019 | Winter | 5,624 | 3,795 | 0 | 0.00% |
| 2018-2019 | Spring | 4,127 | 2,725 | 144 | 3.49% |
| 2019-2020 | Summer | 3,775 | 2,357 | 152 | 4.03% |
| 2019-2020 | Fall | 4,643 | 2,373 | 116 | 2.50% |
| 2024-2025 | Summer | 3,912 | 2,556 | 0 | 0.00% |
| 2024-2025 | Fall | 5,276 | 3,276 | 0 | 0.00% |
| 2024-2025 | Winter | 4,301 | 2,457 | 0 | 0.00% |
| 2024-2025 | Spring | 5,600 | 4,960 | 0 | 0.00% |
| 2025-2026 | Summer | 4,380 | 2,625 | 0 | 0.00% |
| 2025-2026 | Fall | 6,522 | 6,474 | 0 | 0.00% |
| 2025-2026 | Spring | 6,112 | 6,112 | 0 | 0.00% |
| 2026-2027 | Summer | 6,120 | 6,120 | 0 | 0.00% |
| 2026-2027 | Fall | 7,984 | 0 | 0 | 0.00% |

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
