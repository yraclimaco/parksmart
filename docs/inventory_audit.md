# Inventory Audit

## Workbook reviewed

- File: Inventory_2025-2026_Fall.xlsm
- Source sheet: Pivot Table Data
- Header row: Excel row 4
- Populated source records: 1,059
- Parking categories: 24
- Title sheet report date: December 20, 2025

## Initial capacity checks

For the Inventory By Location column:

- Blank cells: 366
- Zero values: 90
- Negative values: 0
- Non-numeric populated values: 0

These are cell counts, not counts of unresolved facility capacities.

## Important workbook behavior

Facility totals are calculated using facility, space type,
space subtype, and time limit. Totals appear only on the first
row of each group. Later blank total cells must not automatically
be treated as missing capacities.

Garage levels must not cause facility totals to be counted twice.
Space subtypes and time limits must be preserved during cleaning.

## Unresolved questions

- Does the report date represent the capacity effective date?
- Were capacities different earlier in Fall 2025?
- How do Inventory categories correspond to QPASS categories?
- Which additional quarters and workbooks are available?

## Current progress

The audit script exports source records to a staging CSV.
Capacity cleaning and QPASS matching are not yet implemented.

## Capacity extraction results

- Source rows: 1,059
- Facility/category/subtype/time-limit groups: 693
- Positive capacities awaiting historical verification: 603
- Zero capacities requiring review: 90
- Groups with missing totals: 0
- Groups with multiple populated totals: 0

The 366 blank total cells were within groups containing a
populated total. They were not filled with zero.

Output: data/interim/inventory/Inventory_2025-2026_Fall_capacity_groups.csv

This is an intermediate dataset. Standardized identifiers,
category aggregation, historical verification, and QPASS
matching remain unfinished.

## Representative QPASS findings

File: QPASS 2025-2026-2 Fall.xlsm

- Dated data-entry rows: 1,800 across Weeks 0, 1, and 2.
- Observation dates: September 25 through October 10, 2025.
- Raw facility field: Location.
- Raw category field: Type.
- All dated rows have cached Total Stall Count values of zero.
- Total Stall Count formulas reference blank cells in Inventory (PRINT).
- Preserve these raw zeros, but do not use them as valid denominators.
- Stall Type metadata says Summer 2025, conflicting with observation dates.

Example requiring investigation:
Facility 8980, category A, September 29 at 8am has 47 open
spaces in QPASS, but the December Inventory reports 34 A spaces.

Next steps:
Verify historical capacity changes, category scope, and source
workbook formulas. Do not force this capacity match.

## Results from the updated capacity comparison

The pipeline was run on Summer and Fall 2025–2026.

| Quarter | Eligible observation slots | Exact-key candidates | Candidate rate |
|---|---:|---:|---:|
| Summer | 4380 | 2625 | 59.93% |
| Fall | 6522 | 6474 | 99.26% |

Matching uses academic year, quarter, facility, and category.
Surrounding whitespace is removed from facility/category join values.
Original labels are preserved separately.

Summer had 2760 observation slots with agreeing positive reported
totals, pending verification of historical timing and category scope.
Fall had no comparable reported totals.

Summer flagged 16 slots where open spaces exceeded candidate capacity.
Fall flagged 312. These counts include excluded observation slots.

Separate reports preserve unmatched, conflicting, and unresolved cases.
Missing or invalid observations remain in the reports but are excluded
from rate denominators.

No capacities have been accepted as historically verified.
The current script leaves matched_capacity empty. Historical acceptance,
remaining workbook coverage, and verified identifier mappings still
require work.

Validation: 138 tests passed.

## Legacy Inventory layout and level-scope review

Reviewed Inventory 2018-2019-2 October 1.xlsx for Fall 2018–2019.

Unlike the newer workbooks, it has no Pivot Table Data sheet.
The legacy loader reshapes category columns from:
- 5A By Lot: 186 lot rows
- 6A By Structure: 11 structure rows

Extraction produced 1970 records:
- 600 positive, unverified capacities
- 1315 missing capacities
- 53 zero capacities requiring review
- 2 text values: Closed for construction

Original values and source cells are preserved. All-category totals
and motorcycle-section counts are excluded. Lot and structure tables
overlap and must not be summed together.

Fall 2018–2019 candidate matching:
- Eligible observation slots: 10189
- Exact-key candidates: 6733
- Candidate rate: 66.08%

Across all 10784 inspected slots:
- 2904 require level-scope review
- 3632 have agreeing reported totals, still unverified
- 396 have reported-total disagreements
- 3852 have no comparable reported totals

Individual QPASS levels must not be compared directly with whole-facility
Inventory totals without a verified scope mapping.

The scope correction was also run on Summer and Fall 2025–2026.
No capacities have yet been accepted as historically verified.

Latest validation: 149 tests and 17 subtests passed.

## Legacy Inventory layout and level-scope review

Reviewed Inventory 2018-2019-2 October 1.xlsx for Fall 2018–2019.

Unlike the newer workbooks, it has no Pivot Table Data sheet.
The legacy loader reshapes category columns from:
- 5A By Lot: 186 lot rows
- 6A By Structure: 11 structure rows

Extraction produced 1970 records:
- 600 positive, unverified capacities
- 1315 missing capacities
- 53 zero capacities requiring review
- 2 text values: Closed for construction

Original values and source cells are preserved. All-category totals
and motorcycle-section counts are excluded. Lot and structure tables
overlap and must not be summed together.

Fall 2018–2019 candidate matching:
- Eligible observation slots: 10189
- Exact-key candidates: 6733
- Candidate rate: 66.08%

Across all 10784 inspected slots:
- 2904 require level-scope review
- 3632 have agreeing reported totals, still unverified
- 396 have reported-total disagreements
- 3852 have no comparable reported totals

Individual QPASS levels must not be compared directly with whole-facility
Inventory totals without a verified scope mapping.

The scope correction was also run on Summer and Fall 2025–2026.
No capacities have yet been accepted as historically verified.

Latest validation: 149 tests and 17 subtests passed.

## Six-quarter legacy Inventory review

All six available Inventory workbooks for 2018-2019 and
2019-2020 were processed, producing 12,262 capacity records.

Special handling:
- Summer 2018 has a shifted lot-table header.
- Fall 2019 adds D to the lot table.
- Lot identifiers P406a and P406b are preserved.
- Spring 2019 marks P005, P403, and P404 as closed for construction.
  Their original labels remain intact, capacities remain missing,
  and 30 category records receive closure_review.
- Blank capacities are not converted to zero.
- Lot and structure summaries overlap and must not be summed together.

| Academic year | Quarter | Eligible slots | Exact-key candidates | Candidate rate |
|---|---|---:|---:|---:|
| 2018-2019 | Summer | 9702 | 9543 | 98.36% |
| 2018-2019 | Fall | 10189 | 6733 | 66.08% |
| 2018-2019 | Winter | 5624 | 3795 | 67.48% |
| 2018-2019 | Spring | 4127 | 2725 | 66.03% |
| 2019-2020 | Summer | 3775 | 2357 | 62.44% |
| 2019-2020 | Fall | 4643 | 2373 | 51.11% |

Combined candidate rate: 27,526 / 38,060 = 72.32%.
These denominators exclude observation slots flagged as ineligible
by the comparison code.

Before snapshot acceptance was implemented, verified capacity matches were zero. Exact keys alone do not verify historical
timing, level, subtype, or category scope.

Reports are stored in results/capacity_matching/YYYY-YYYY_quarter/.
The combined summary is legacy_quarter_summary.csv.


## Newer Inventory layout extraction

The newer cleaner is src/clean_inventory_modern.py. It recognizes the early 2024
row-count layout and the later Inventory By Location layout, including reordered columns.
Original workbooks are read only. Positive capacity candidates remain unverified.

For early 2024, use the explicitly requested seasonal count column and compare it with
Inventory. Repeated facility/category/subtype/time-limit rows are flagged instead of
summed or deduplicated. Blank or zero identifiers are retained and flagged.
For grouped layouts, use Inventory By Location and retain blank repetitions in provenance.
Combined Inventory by Lot totals all categories and must not supply a category capacity.
Conflicting title/selector quarter metadata blocks capacities and is recorded in the audit.
Formula caches are used without recalculation. Only wholly blank rows are excluded.

Run: python -m src.clean_inventory_modern "WORKBOOK" --academic-year YYYY-YYYY --quarter QUARTER
Optional: --output-dir DIRECTORY
Outputs: data/interim/inventory/WORKBOOK_capacity_groups.csv and WORKBOOK_modern_audit.json.
Tests: python -m pytest tests/test_inventory_modern.py -v

## Winter 2024-2025 period conflict

The Inventory filename and cover identify Winter 2024-2025.
The cover date is March 1, 2025, but the Pivot Table Data selector
says Spring 2025. All 627 capacity groups remain flagged
period_metadata_review, with capacity left missing.

Next step: verify the intended quarter and underlying counts
against an authoritative corrected report or source confirmation.
Do not relabel this workbook or substitute Spring capacities.


## Snapshot capacity acceptance policy

This policy supersedes the earlier audit-stage statements that every matched_capacity is blank.
Exact-key candidate rates remain distinct from accepted-capacity match rates.

The first supported acceptance case is a legacy lot/category observation on its Inventory snapshot
date. Known quarterly report filenames and table titles must agree with academic year and quarter.
Snapshots are July 1 (Summer), October 1 (Fall), January 1 (Winter), and April 1 (Spring),
with calendar year taken from the corresponding academic-year quarter.
Only the audited 5A By Lot schema with lot granularity is supported for acceptance.

Acceptance requires one positive integer Inventory candidate, a matching positive QPASS total,
no level/subtype/time-limit qualification, an eligible open-space count between zero and capacity,
and no conflicting scope/count observation for that lot/category and date. Raw fields remain intact.
No capacity is applied before or after the report date. Modern report dates and legacy dates
without contemporaneous QPASS agreement remain unresolved until additional evidence is supplied.
Counts agreeing numerically do not, on their own, authorize broader category or date mappings.

matched_records.csv contains accepted observations. capacity_comparison.csv retains every inspected
slot, while unresolved_cases.csv retains slots without an accepted capacity and explains why.
Accepted observations record capacity_acceptance_basis and inventory_snapshot_date.
The existing verified_capacity_match_rate column reports acceptance under this conservative policy,
not independent certification of every workbook count. An explicit assumption is that the dated
legacy Inventory report represents the lot/category capacity on that snapshot day.

Local validation on the real Fall 2018 files accepted 192 of 10,189 eligible observation slots
(1.8844%), all on October 1, 2018. The 6,733 exact-key candidates and 66.0811% candidate rate
are unchanged. Other quarterly rates must be regenerated with the updated comparison code.

Tests: python -m pytest tests/test_capacity_acceptance.py -v
Run comparisons through the existing src.compare_capacities CLI or compare_capacities API.


## Reproduce combined capacity deliverables

After downloading and cleaning all available Inventory workbooks, run:
python -m src.run_capacity_matching

Inputs: results/capacity_matching/inventory_sources.csv, data/raw/QPASS workbooks,
and data/interim/inventory/*_capacity_groups.csv. No original workbooks are modified.
Use --manifest, --qpass-dir, --inventory-dir, or --output-dir for alternative locations.

Outputs under results/capacity_matching/batch:
- inventory_cleaned.csv: one row per academic year, quarter, facility and category.
- inventory_capacity_groups.csv: all input groups, preserving finer source detail.
- inventory_coverage.csv: source availability for every QPASS quarter in the manifest.
- quarter_summary.csv and overall_summary.csv: counts, candidate rates and accepted rates.
- combined/capacity_comparison.csv: every inspected observation slot with provenance.
- combined/matched_records.csv: observations accepted by the snapshot policy.
- combined/unresolved_cases.csv: observations without accepted capacity and next steps.
- combined/unmatched_records.csv: observations with no exact Inventory key.
- combined/conflicting_records.csv: total disagreements or open counts exceeding candidates.
- Each quarter folder retains its own reports and the QPASS loader audit.

Existing files in this batch output directory are regenerated on each run.
Every manifest quarter contributes to coverage and rates, including Fall 2026-2027,
whose Inventory workbook was not listed in the archive at download time. Its capacities
stay missing. Earlier 14-quarter rates excluded that missing-source quarter; use the
batch summaries for complete coverage. Overall rates divide summed counts rather than
averaging quarterly percentages. Invalid/missing observation slots remain in detail reports
and their excluded counts are reported separately from eligible denominators.

Source filename/row/category/capacity values are preserved in source_groups_json.
For multiple groups sharing a key, capacity remains blank with multiple_inventory_groups_review.
Join identifiers use exact raw labels with whitespace trimmed. Teammate aliases have not
yet been applied; unresolved identifier mappings must not be guessed.

Tests: python -m pytest tests/test_capacity_batch.py -v
Full check before the pull request: python -m pytest
