# QPASS Workbook Schema Audit (Issue #1)

Audit of the public UCSD QPASS parking-availability workbooks and how
`src/qpass_loader.py` reads them into one standard table.

Source index: https://rmp-wapps.ucsd.edu/TS/Survey/QPASS/Contents.html
(checked 2026-10-13)

## How to run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 1. Download the workbooks into data/raw/QPASS/ (gitignored, never
#    committed). Safe to rerun: existing files are kept.
python -m src.download_qpass

# 2. Inventory every sheet (writes results/qpass_inventory.csv and .md)
python -m src.qpass_inventory

# 3. Load all workbooks (or one) in Python or a notebook
python -c "from src.qpass_loader import load_all_qpass; print(load_all_qpass().shape)"
python -c "from src.qpass_loader import load_qpass; print(load_qpass('data/raw/QPASS/QPASS 2024-2025-2 Fall.xlsm').head())"

# 4. Run tests (real-data tests are skipped if data/raw/QPASS/ is missing)
pytest
```

Paths are built from the repo's location, so the inventory script and the
tests work from any folder; the data must still be in `data/raw/QPASS/`.

The inventory finds the header row by first looking for a row starting with
`Date` (newer files) or `Structure` (2018-2019 files), then falling back to
keyword scoring for other sheets.

## Files

The index page links 16 workbooks. Filenames follow
`QPASS {academic_year}-{N} {Quarter}` where N is 1 Summer, 2 Fall,
3 Winter, 4 Spring. Some names have two spaces before the quarter
(`QPASS 2024-2025-1  Summer.xlsm`); the loader tolerates this. All quarter
numbers match their names, and every data sheet's dates fall in the
academic year named in the file.

| File | Format | Rows loaded | Survey dates | Status |
|---|---|---|---|---|
| QPASS 2018-2019-1 Summer.xlsx | A | 2,655 | 2018-06-18 to 2018-07-13 | Loaded (4 weeks) |
| QPASS 2018-2019-2 Fall.xlsx | A | 2,696 | 2018-09-17 to 2018-10-11 | Loaded (3.8 weeks) |
| QPASS 2018-2019-3 Winter.xlsx | A | 1,440 | 2019-01-07 to 2019-01-18 | Loaded |
| QPASS 2018-2019-4 Spring.xlsx | A | 1,060 | 2019-04-01 to 2019-04-12 | Loaded |
| QPASS 2019-2020-1 Summer.xlsx | A | 1,120 | 2019-07-01 to 2019-07-12 | Loaded |
| QPASS 2019-2020-2 Fall.xlsx | A | 1,180 | 2019-09-30 to 2019-10-11 | Loaded; one sheet unsupported (see below) |
| QPASS 2024-2025-1 Summer.xlsm | B | 1,090 | 2024-07-01 to 2024-07-12 | Loaded |
| QPASS 2024-2025-2 Fall.xlsm | B | 1,344 | 2024-09-26 to 2024-10-11 | Loaded (includes Week 0) |
| QPASS 2024-2025-3 Winter.xlsm | B | 1,090 | 2025-01-06 to 2025-01-17 | Loaded |
| QPASS 2024-2025-4 Spring.xlsm | B | 1,400 | 2025-03-31 to 2025-04-11 | Loaded |
| QPASS 2025-2026-1 Summer.xlsm | B | 1,360 | 2025-06-30 to 2025-07-11 | Loaded |
| QPASS 2025-2026-2 Fall.xlsm | B | 1,669 | 2025-09-25 to 2025-10-10 | Loaded (includes Week 0); all stall counts are 0, see Known data issues |
| QPASS 2025-2026-3 Winter.xlsm | — | — | — | **Excluded by team decision** (see below) |
| QPASS 2025-2026-4 Spring.xlsm | C | 1,600 | 2026-03-30 to 2026-04-10 | Loaded |
| QPASS 2026-2027-1 Summer.xlsm | C | 1,720 | 2026-06-29 to 2026-07-10 | Loaded |
| QPASS 2026-2027-2 Fall.xlsm | C | 2,004 | 2026-09-24 to 2026-10-09 | Loaded (includes Week 0) |

Total: 23,428 rows from 15 files.

### Missing quarters (no workbook linked)

These are recorded as **unresolved**, not assumed to be absent from UCSD's
records. No cause is assumed.

- 2019-2020 Winter and Spring
- 2020-2021, 2021-2022, 2022-2023, 2023-2024 (all quarters)
- 2026-2027 Winter and Spring (not yet surveyed as of 2026-10-13)

### Excluded: QPASS 2025-2026-3 Winter.xlsm

Excluded by team decision. The file is not downloaded into
`data/raw/QPASS/`. What was checked (server copy):

- Its `Week 0` sheet has September 25-26, 2025 dates, which belong to Fall,
  and its numbers differ from Fall 2025-26's Week 0. Which days it really
  covers is unknown. This is the problem unique to this file.
- Every `Total Stall Count` is 0 (rows flagged `CHECK NUMBERS`). This is
  **not** unique: Fall 2025-26, which is loaded, has the same zeros, for
  the same reason (the workbook's own inventory sheet is empty; see Known
  data issues). So the zeros alone are not a reason to exclude it.
- Weeks 1-2 (2026-01-05 to 2026-01-16) contain about 1,500 rows of
  open-space counts for 63 locations.

## Using this in other issues

After this is merged, pull `main` and run `python -m src.download_qpass`.
Then one call gives every observation in one table:

```python
from src.qpass_loader import load_all_qpass

df = load_all_qpass()          # 23,428 rows, 26 columns, all 15 files
df.attrs["dropped_rows"]       # what was left out, per file, with reasons
```

Use `load_all_qpass()` rather than `pd.concat` over `load_qpass()`:
pandas drops `attrs` when combining, so the per-file records would be lost.
Values are raw; see "Known data issues" below before relying on them.

| Issue | Columns to start from |
|---|---|
| #2 Reshape and quality checks | `open_8am` ... `open_2pm` (one row per time after reshaping; counts may be text), `total_stall_count`, `source_file` + `sheet_name` + `source_row` to identify a record |
| #3 Standardize names | `location`, `type`, `sub_type`, `report_type` (raw), `raw_structure`, `raw_lot` (2018-2019 cells), `source_file` (which quarters a value appears in) |
| #4 Match capacities | `academic_year`, `quarter`, `location`, `type`, `total_stall_count` (Fall 2025-26 is all 0: needs the Inventory files) |

## Format versions

### Format A — wide weekly sheets (2018-2019, 6 files)

One sheet per survey week. Each day is a block of four columns. The header
is spread across several rows:

```
          Monday                    Tuesday
          2018-09-17                2018-09-18
Structure Lot     Type  Total Spaces 08:00 10:00 12:00 14:00  08:00 ...
                                     Available x4             Available x4
Athena    Level 1 A     64           24    2     5     9      34 ...
          Level 2 B     17           ...
          P002    B     31           ...
```

Variations within Format A:

- The `Structure` label row is Excel row 3 (Summer 2018), 5 (Fall 2018), or
  6 (2019 onward).
- Column order: `Type, Total Spaces` (2018) vs `Total Spaces, Type`
  (2019-2020); in Spring 2019 `Type` is the last column. The loader finds
  columns by name, not position.
- Data-sheet names vary: `F18 Sep17 Data`, `F18 Oct8`, `S19 W1 Data`,
  `Fall19 Week 1 Data`, `1 Summer 2018 June 18`.
- Blank `Structure`/`Lot` cells mean "same as above" for structure levels,
  but surface lots (`P002`, `P785`) with a blank `Structure` are **not** part
  of the structure above them.
- Some sheets end with summary sections. These are not observations and
  are dropped (counted in `attrs["dropped_rows"]`):
  - Summer 2018: a space type in `Structure` and `Vacancy`,
    `Physical Capacity`, `Occupancy`, `Oversubscription` in `Lot`.
  - Summer and Fall 2019: headings `West Campus`, `East Campus`, `SIO`
    (only the `Structure` cell filled), each followed by subtotal rows whose
    `Lot` is a space type (`A` 1593, `Short Term A`, `SIO B` 290, ...).
    Checked: in Summer 2019, West + East `A` (1593 + 708) equals the sum of
    all type-A rows (2,301); in Fall 2019, `SIO B` 290 equals the sum of the
    10 SIO B lots. The `Aquarium` row under `SIO` repeats lot `P017`
    (same total and counts). Before this was fixed these rows were loaded as
    locations named `A`, `B`, `SIO B`, etc.
    A heading counts as a summary only if none of the rows under it with
    values is a level (`Level 1`), a lot ID (`P002`), or a row with a blank
    Lot and a Type (a structure without levels). So a structure name on its
    own row followed by its levels or types is kept as that structure's
    observations. In the real files every row under the three headings has
    a space type in Lot, so all are still dropped (checked in all 4 sheets).
    A row dropped this way is still counted in `attrs["dropped_rows"]`.
  - Fall 2019: a "Deleted/Closed Lots" list (lot names, no counts).

### Format B — long, one sheet per week (2024-2025 to Fall 2025-2026, 6 files)

Data sheets: `QPASS Data Entry (Week 0)`, `(Week 1)`, `(Week 2)` (Summer 2024
uses `QPASS Data Entry` and `QPASS Data Entry W2`). Header on Excel row 2.
One row per location x space type x day.

Core columns: `Date, Day, Zone, Order, Report Area, Neighborhood,
Lot / Structure, Location, Type, Report Type, Total Stall Count,
Open Spaces 8am, Open Spaces 10am, Open Spaces 12pm, Open Spaces 2pm`.
Summer 2024 also has `Old Zone`.

Columns to the right of `Open Spaces 2pm` (`Min Open Spaces`,
`doesn't fill`, `Time Full`, a second `Day`, etc.) are calculated by Excel
from the core columns and are ignored.

### Format C — long, one sheet for the quarter (Spring 2025-2026 onward, 3 files)

Same core columns as Format B, in a single `Data Entry` sheet, plus:

- `Week #` (`Week 0`, `Week 1`, `Week 2`)
- `Sub Type` (Fall 2026 only), e.g. `24/7 Enforced`, `Loading`,
  `Loading Reserved` — relevant to permit eligibility
- More helper columns (`Max Vehicles`, `Max %`, `*** Number Check ***`)

### Sheets that are not raw data

All formats include sheets that are not the raw survey rows: day tabs
(`Monday (1)`), `Summary`, `Oversubscription`, `Text Week N`, `Print`,
`PT Summary`, `Stall Type`, `Directions & Links`, `Copy of ... Data`,
`Current Week Data Sorted by Lot`. The loader skips them.

Verified for the 2024-2025 files: the day tabs equal the data-entry sheet
summed by `Report Type` (e.g. Fall 2024 `Monday (1)`: 105/105 rows
identical). In the Format C files (Spring 2026 onward) the day tabs are a
different summary that does not match these sums; they are not used.

Warning: Spring 2019 contains `Current Week Data Sorted by Lot` with
**January 2019** (Winter) dates. Reading every sheet would mislabel Winter
data as Spring, so the loader reads only known data sheets.

## Loader output (`load_qpass`)

One row per location x space type x survey date. Every file returns the same
26 columns:

| Column | Meaning |
|---|---|
| `source_file`, `sheet_name`, `source_row` | Where the row came from; `source_row` is the Excel row number, so every value can be found in the workbook |
| `format_version` | `A_wide_weekly`, `B_long_weekly`, or `C_long_single` |
| `academic_year`, `quarter`, `quarter_number` | From the filename |
| `date`, `day`, `week` | Survey date; `week` is blank when the source does not state it |
| `location` | Structure name (e.g. `Athena`) or lot ID (e.g. `P602`) |
| `lot_or_structure` | `Structure` or `Lot` |
| `level` | Format A only: `Level 1`, etc. |
| `zone`, `report_area`, `neighborhood` | Formats B/C only |
| `type`, `sub_type`, `report_type` | Space type as written in the source |
| `total_stall_count` | Capacity as written in the source |
| `open_8am`, `open_10am`, `open_12pm`, `open_2pm` | Open-space counts |
| `raw_structure`, `raw_lot` | Format A only: original cells before filling down |

Nothing is dropped silently. All of these are stored on the result and
logged:

- `df.attrs["skipped_sheets"]`: sheets not read, with the reason.
- `df.attrs["dropped_rows"]`: `{sheet: {reason: count}}` for non-blank
  rows inside data sheets that were not kept. Reasons: summary section,
  no counts and no total, no structure/lot/type (Format A); no date,
  invalid date, empty template row (Formats B/C). Current counts per file:

  | File | Summary section | No counts or total | No date | Empty template row |
  |---|---|---|---|---|
  | Summer 2018 | 64 | | | |
  | Summer 2019 | 32 | 6 (`West Campus`/`East Campus`/`SIO` headings) | | |
  | Fall 2019 | 46 | 12 (headings, closed-lot names) | | |
  | Fall 2024 | | | 4 | 2 |
  | Winter 2025 | | | | 40 |
  | Spring 2025 | | | | 100 |
  | Summer 2025 | | | | 140 |
  | Fall 2025 | | | | 131 |
  | Spring 2026 | | | | 80 |
  | Fall 2026 | | | | 132 |

  All other files: nothing dropped. 789 rows in total.

  "Empty template row" (Formats B/C): the 2024+ workbooks are templates
  whose `Location`, `Type`, `Total Stall Count` etc. are formulas copying
  from an inventory sheet. Rows whose source row is empty show 0 or blank
  everywhere (location `0`, type `0`, counts 0 or blank). A row is dropped
  only if its location and type are 0/blank **and** all four counts are
  0/blank. The one such row with counts (Fall 2025, Week 1, Excel row 52:
  1, 1, 1, 1) is kept, with location `0`.
- `df.attrs["non_numeric_values"]`: `{column: count}` of count/total cells
  holding text. These rows are **kept** with the text as written, in every
  format. Current values: `-` (Fall 2019, Campus Point East B, Monday),
  a non-breaking space (Fall 2024), spaces (Winter 2025), and `` `95 ``
  (Summer 2025, a typo for 95). Cleaning decides what they mean.

`UnsupportedQPASSFormatError` is raised when:

- a file does not match a known layout;
- a data sheet is missing a required column (Formats B/C: `Date`,
  `Location`, `Type`, `Total Stall Count`, the four `Open Spaces` columns;
  Format A: `Structure`, `Lot`, `Type`, `Total Spaces`), so a renamed column
  cannot silently produce blank values;
- two columns hold the same survey date and time (Format A), or a
  required Format B/C column appears twice, so one value cannot silently
  overwrite another. The error names the Excel columns. No current file
  does this. Repeated helper headers (`Day`, and `Sub Type` in Fall 2026,
  whose two columns hold identical values) are allowed; the first is used.

Dates (Formats B/C): a date stored as an Excel serial number (e.g. 45565)
is converted to the real date (2024-09-30), not read as 1970. A value that
is not a valid date is dropped as "invalid date" with a warning. No current
file stores dates as numbers. A date outside the file's academic year is
kept and logged as a warning.

## Assumptions and decisions

1. **Values are kept raw.** Location and type names are not standardized
   (e.g. old `Visitor: PBS` vs new `Visitor`), trailing spaces are kept
   (`P602` vs `P602 `), and counts are not converted to numbers. Cleaning is a
   later issue.
2. **Blank cells are kept.** 1,143 rows have all four counts blank (0-215
   per file), e.g. the July 4 holiday (July 3 in 2026) and lots not
   surveyed that day.
   They are kept, not dropped. Text such as `n/a` or `NA` is kept as text
   too (pandas would otherwise read it as blank).
3. **Week is left blank when not stated**: Summer and Fall 2018 sheet names
   have no week number, and Summer 2024's first sheet is `QPASS Data Entry`
   with no number (probably Week 1, not assumed).
4. **Empty sheets are skipped and logged** (e.g. empty `Week 0` templates in
   Winter/Spring 2024-2025 and Summer 2025-2026).
5. **`sub_type` exists for every file** and is blank where the source has no
   `Sub Type` column.
6. **Format A structure filling**: `Lot` is filled down, but never past a row
   that names a new `Structure` (otherwise, in Spring and Summer 2019,
   structures listed without a lot inherited the surface lot above them,
   e.g. Athena became `P010`). `Structure` is filled down only for `Level ...`
   rows and for structure rows with no lot. Surface lots use their lot ID as
   `location`, and any label in their `Structure` cell (`Aquarium`,
   `Regents Parking Lots`) is kept in `raw_structure`.
7. **Format A sheet selection**: a sheet is data if it has a `Structure`
   label row with dates above it and its name does not contain
   `oversubscription`, `summary`, `sorted`, `copy of`, or `current week`.

## Known data issues (kept as written, for the cleaning issue)

The loader keeps values raw. These were found while checking the loaded
rows against the workbooks; each needs a cleaning decision.

- **Fall 2025-26 stall counts are all 0.** `Total Stall Count` is a
  formula (`='Inventory (PRINT)'!I3`) and column I of that sheet is empty
  in all 231 rows. Zone, Order and Report Area are 0 for the same reason.
  These zeros mean "missing", not "0 stalls"; capacity has to come from
  UCSD's separate Inventory files. They cause 1,498 of the 1,642 rows
  where an open count is larger than the total.
- **0 can mean blank in formula columns** (2024+ files): a formula pointing
  at an empty cell shows 0. This applies to location, type, zone, order,
  report area and total, not to the typed-in open counts.
- **A copied value:** Fall 2025-26, Week 1, Excel row 89 (P604 B,
  2025-09-29): the 12pm and 2pm cells are formulas copying Week 0, where
  those cells are blank, so their 0s were not observed.
- **Estimated counts:** Osler, Winter 2018-19 (30 rows, Excel rows 18, 47,
  50, 61, 97, 115): counts are fractions of the total (e.g. 109.2 = 156 x
  0.70), so they look like estimates from percentages, not counts.
- **Other impossible values:** 144 rows with a real total still have an
  open count above it (e.g. Torrey Pines Center South).
- **Rows that look alike:** `(date, location, type)` is not unique (806
  rows). Spring and Summer 2026 have several `Visitor` / `Reserved` rows
  per location with different totals (e.g. Athena Visitor 30, 9, 10, 210)
  and no `Sub Type` column to tell them apart; Fall 2026 adds `Sub Type`.
  Also P507 Visitor (Fall 2025) and Theatre District Garage S entered
  twice on 2024-09-26 (Excel rows 110-111, counts blank). `source_row`
  tells such rows apart.
- **Unclear owner:** Summer 2019, Week 2, Excel row 101: a `V` row (9
  stalls) with blank Structure and Lot right after Pangea. The fill-down
  rule assigns it to Pangea, but Week 1 has no such row, so it may belong
  to another lot.
- **`CLOSED` markers:** some lots carry `CLOSED` in the Structure cell
  (Spring 2019: P111, P113, P201; Summer 2019: P508). Kept in
  `raw_structure`.
- **Text in count cells:** see `attrs["non_numeric_values"]` above.

## Limits for modeling

Checked on the loaded data (2026-10-14). Not fixable in the loader; they
limit what a model can claim.

- **Only the start of each quarter.** About 10 survey days per quarter
  (weeks 0-2), weekdays only, at 8am, 10am, 12pm and 2pm. A model trained
  on this cannot claim later weeks, evenings or weekends.
- **A 2020-2024 gap.** 57 locations appear both in 2018-19 and 2024+, 12
  only in 2018-19 and 23 only in 2024+. Space-type labels changed: only 14
  labels are written the same way in both periods (issue #3).
- **Capacity is needed to compare lots** (open share = open / total), and
  Fall 2025-26 has none (issue #4).
- **Small lots are noisy.** One car changes a 2-space lot by 50%.
- **EV and accessible spaces** are in QPASS for only a few lots, from
  Summer 2025 on. UCSD's Inventory files list 768 accessible and 1,060 EV
  spaces (Winter 2026) but with no daily counts.

How predictable it is: about 80,000 usable observations (count present,
total above 0, open not above total), 86% of all. Holding out Fall 2026
and predicting it from earlier quarters with a plain average per lot, type
and time of day gives an average error of 0.15 in open share (weighted by
spaces; 0.14 for lots with 200+ spaces, 0.27 for lots under 10). Guessing
by time of day alone gives 0.31. Even using the same quarter's week 1 to
predict its week 2 gives 0.12, which is roughly the day-to-day noise. So
the data supports a useful model, and the simple average is the baseline
to beat; the realistic room for improvement is between 0.15 and 0.12.

## Unsupported content

- **`Fall19 Week 3 Central Campus`** (QPASS 2019-2020-2 Fall.xlsx): different
  layout, no `Structure` label row. Possibly a partial Week 3 survey of
  central campus only. Skipped and logged; not loaded.
