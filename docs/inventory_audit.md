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