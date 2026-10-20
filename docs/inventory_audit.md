# Inventory extraction and capacity selection — Issue #4

## Supported sources and structure

The Inventory archive provides quarterly workbooks. A source manifest records the
academic year, quarter, QPASS filename, original Inventory path, URL and download
status. Never replace a missing quarter with a current workbook.

Reviewed layouts:

| Layout | Source tables | Capacity field | Special handling |
|---|---|---|---|
| 2018–2019 / 2019–2020 legacy summaries | `5A By Lot`, `6A By Structure` | Category columns A/B/S/(D)/Visitor/Reserved/Allocated/Accessible/UC Vehicle/Service Yard/Loading | Detect headers; verify title period; preserve two-row category headers, closures and source cells. Exclude all-category totals and motorcycle sections. |
| Early 2024 row counts | `Pivot Table Data` | Exact requested quarter column, checked against `Inventory` | Multiple rows per detailed group and differing columns require review; never sum automatically. |
| Later grouped workbooks | `Pivot Table Data` | `Inventory By Location` | One populated total per detailed group; intentional blank repeated cells are retained. Never select `Combined Inventory by Lot`. |

Lot and structure tables can overlap; never add them together. Missing, zero,
negative, noninteger, nonnumeric, duplicate and period-conflicting capacities keep
explicit review statuses. Formula caches are read without recalculating Excel.
Original workbooks are never modified.

The first Fall 2025–2026 audit found 1,059 populated source rows, 366 blank
facility-total cells, 90 zeros, no negative totals and no populated nonnumeric
totals. Blank repeated cells can be intentional; they are not replaced with zero.
Per-workbook audits are regenerated with each supported extraction run.

Winter 2024–2025 has conflicting period information: its cover says Winter while
the data selector says Spring 2025. Inventory fallback is blocked for this file.
Fall 2026–2027 had no listed Inventory link when the original archive check ran;
current download status remains in the manifest. Source availability can change.

## Capacity selection policy

1. Prefer QPASS's own positive integer capacity for its exact facility, category,
   level and subtype source group. Known formula errors, unresolved labels,
   closure/scope issues, contradictory usable Inventory counts, multiple reported
   capacities for the same exact group/date, or a valid open count above capacity
   prevent acceptance. The QPASS source row is evidence of its own capacity scope;
   an Inventory whole-facility value is not evidence against a single-level total.
2. Only when QPASS capacity is missing or demonstrably broken, allow one positive
   same-academic-year/quarter Inventory candidate with matching standardized
   facility/category and exact subtype scope, no QPASS level, no unresolved
   time-limit qualification and no period conflict. Label it
   `assumed_same_quarter_capacity`. This does not establish capacity on every date.
3. A zero by itself requires review; it is not automatically missing or broken.
   The documented Fall 2025–2026 `Inventory (PRINT)` formula problem is an explicit
   exception: its zero remains raw and flagged while safe fallback may be selected.
4. Never replace an otherwise valid but contradictory QPASS total with Inventory.
   Leave selected capacity unknown. No fuzzy mapping or cross-quarter carry occurs.

Missing and invalid readings are excluded from group-conflict calculations. A blank
8 AM reading cannot block valid readings later that day. Conflicts are grouped by
academic year, quarter, facility, category, standardized subtype, raw trimmed level
and survey date. Different levels/subtypes do not conflict merely because their
capacities differ. Unresolved Inventory subtype groups are not summed.

The audited Fall 2025 Week 1 row 89 (P604 B, September 29) has copied 12 PM/2 PM
values from a blank prior week. These exact source slots are flagged as known
non-observations. Other zero readings are retained unless independently identified
as broken; zero availability can be real.

## Standardized labels and unresolved cases

Both QPASS and Inventory use `src.label_decisions.standardize_labels` and Issue #3
configuration. Exact verified aliases such as V → Visitor and Osler → South are
applied. Restricted categories and populated subtypes stay separate; `keep_separate`
is not a statement of eligibility. Category/subtype boundaries and time limits are
not automatically rearranged. Legacy UC + Vehicle and Service + Yard headers use
the extractor's reconstructed labels, with original headers retained separately.

Missing/blank/placeholder and numeric-zero identifiers are invalid and excluded
from eligible denominators, including actual NaN and literal `nan`. An unresolved
nonmissing mapping remains an eligible but unresolved case. Closure labels are
source/scope issues. The Issue #3 mappings are integrated; `mapping_review` now
means a remaining unresolved decision, not that the entire dependency is missing.

`unresolved_type` distinguishes `mapping_review`, `source_data_problem`,
`missing_inventory` (in combined batch reports), `inventory_key_unmatched`,
`inventory_capacity_review`, `scope_conflict`, `period_metadata_conflict`,
`capacity_conflict`, `invalid_identifier`, and `invalid_observation`. Independent
source flags, label notes, Inventory statuses and raw records retain additional
issues even if one primary unresolved type is shown. Accepted fallbacks still
retain any known QPASS source-data warning.

## Output contract

- Every inspected slot preserves original labels, subtype, level, QPASS capacity,
  Inventory raw values/source rows, source file/sheet/row, date/time and raw reading.
- `qpass_source_record_json` retains all shared loader columns for the source row.
- `selected_capacity` is the denominator; `matched_capacity` is its compatibility
  alias. `capacity_source` is `qpass`, `inventory_same_quarter`, or `unknown`.
- Acceptance reason, basis and `capacity_assumption` explain the choice. Only
  Inventory fallback requires the explicit same-quarter assumption.
- `inventory_cleaned.csv` has one row per academic year/quarter/facility/category.
  `source_groups_json` preserves every input group and raw field. Multiple groups
  retain unknown capacity rather than being summed.
- Reports: `capacity_comparison.csv`, `matched_records.csv`, `unresolved_cases.csv`,
  `unmatched_records.csv` (no exact Inventory key, including QPASS-only acceptance),
  `conflicting_records.csv`, quarter/overall summaries and loader audit JSON.
- Conflicting records include eligible slots affected by contradictory group totals,
  not just the row that directly disagreed. Excluded readings do not create group
  conflicts. All unselected slots remain in unresolved reports.

Quarter and overall summaries use the same columns: `total_observation_slots`,
`eligible_observation_slots`, `excluded_observation_slots`, `exact_key_candidates`,
`accepted_qpass_capacities`, `accepted_inventory_capacities`, and
`accepted_capacity_matches`, with corresponding clearly named rates. Every rate
uses eligible slots; zero denominators produce missing rates. Overall rates use
summed counts, never an average of quarter rates. Old `observation_slots` and
`verified_capacity_*` columns are retired because their meaning was ambiguous.

## Run from the repository root

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m src.download_qpass
python -m src.download_inventory
python -m src.run_capacity_matching --rebuild-inventory
python scripts/prepare_capacity_deliverables.py
python -m pytest -q
```

`data/raw/QPASS/` capitalization matters. The downloader keeps existing originals.
The batch command reads `results/capacity_matching/inventory_sources.csv`, validates
inputs, regenerates all available Inventory groups from original workbooks, and
includes QPASS quarters without Inventory. Choose an audited supported extractor
based on actual sheet layout; the manifest batch dispatches the reviewed older
2018/2019 sources to legacy and 2024+ sources to modern. Unknown layouts fail rather
than silently extracting arbitrary columns.

For individual files:

```bash
python -m src.clean_inventory_legacy "data/raw/inventory/Inventory 2018-2019-2 October 1.xlsx" --academic-year 2018-2019 --quarter Fall
python -m src.clean_inventory_modern "data/raw/inventory/Inventory 2025-2026-2 Fall.xlsm" --academic-year 2025-2026 --quarter Fall
python -m src.compare_capacities --inventory "data/interim/inventory/Inventory 2025-2026-2 Fall_capacity_groups.csv" --qpass "data/raw/QPASS/QPASS 2025-2026-2 Fall.xlsm" --output-dir results/capacity_matching/fall_2025
```

The old `src.clean_inventory` extraction entry point is deprecated and delegates
to the supported modern implementation; its numeric validation helper remains
shared. Use explicit legacy/modern commands for new work.

Intermediate groups and audits: `data/interim/inventory/`.
Batch outputs: `results/capacity_matching/batch/`, with quarter subdirectories and
combined reports. The preparation script validates counts, denominators, source
selection, fallback scope and lossless group preservation before writing compact
`.csv.gz` reports to `results/capacity_matching/deliverables/` and regenerating
`docs/capacity_matching_summary.md`. Full raw workbooks remain local.

Tests cover both cleaner layouts, aliases/restrictions, QPASS-first selection,
same-quarter fallback, excluded readings, invalid IDs, conflicts, weighted rates,
and an end-to-end generated Excel fixture through extraction/loader/labels/batch
and delivery validation. Real-workbook regeneration is a separate required check;
report its command/results and the full pytest outcome when updating the PR.

The initial snapshot-only policy and its 604 accepted slots are superseded. Do not
reuse its old summary as a claim about the revised policy. Keep PR #7 as a draft
until tests, real-data regeneration and the mentor-provided DS3 review are complete.

## Period validation and rerun behavior

Missing/invalid observation dates, nonconsecutive academic-year labels, unknown
quarters, or calendar-year conflicts block both capacity sources and set
`qpass_period_metadata_conflict`. Summer/Fall use the starting calendar year;
Winter/Spring use the ending year. This is a metadata consistency check, not an
exact quarter-boundary or survey/inventory date-equality rule. The raw date and
period labels remain unchanged; unresolved cases use `period_metadata_conflict`.
All-missing-Inventory batches write header-only Inventory datasets, replacing
prior outputs. `src.audit_inventory` is a deprecated explicit-period wrapper for
the modern cleaner; it no longer filters missing-identifier source rows.

## Legacy summary scope and canonical filenames

`legacy_summary_category_requires_review` is an unverified Inventory category
scope. Such groups remain in audit outputs but cannot contradict QPASS capacity
or provide fallback. The same restriction applies to legacy-schema records with
a missing scope marker. An explicit exact-group scope decision requires both
`scope_verified=True` and nonblank `scope_verification_evidence` on the extracted
group; retain the original category_scope marker. Neither matching labels nor
a positive count establish scope equivalence. No legacy scopes are automatically
marked verified by the pipeline. Comparable verified-source disagreements remain
unresolved. Modern layout scope checks remain in force.

The downloader saves the filename linked by the archive, including spaces.
The Fall 2025 source is `Inventory 2025-2026-2 Fall.xlsm`; generated group files
use that same stem. The former local underscore alias is no longer consulted.
Existing local copies are preserved, but rerun `python -m src.download_inventory`
to generate a manifest using canonical downloaded filenames; no manual rename
is needed. Quote paths containing spaces.
