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

# 1. Download the workbooks from the index page into data/raw/QPASS/
#    (gitignored — never commit them). Keep filenames exactly as published.

# 2. Inventory every sheet (writes results/qpass_inventory.csv and .md)
python -m src.qpass_inventory

# 3. Load one workbook in Python or a notebook
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
| QPASS 2019-2020-1 Summer.xlsx | A | 1,280 | 2019-07-01 to 2019-07-12 | Loaded |
| QPASS 2019-2020-2 Fall.xlsx | A | 1,400 | 2019-09-30 to 2019-10-11 | Loaded; one sheet unsupported (see below) |
| QPASS 2024-2025-1 Summer.xlsm | B | 1,090 | 2024-07-01 to 2024-07-12 | Loaded |
| QPASS 2024-2025-2 Fall.xlsm | B | 1,346 | 2024-09-26 to 2024-10-11 | Loaded (includes Week 0) |
| QPASS 2024-2025-3 Winter.xlsm | B | 1,130 | 2025-01-06 to 2025-01-17 | Loaded |
| QPASS 2024-2025-4 Spring.xlsm | B | 1,500 | 2025-03-31 to 2025-04-11 | Loaded |
| QPASS 2025-2026-1 Summer.xlsm | B | 1,500 | 2025-06-30 to 2025-07-11 | Loaded |
| QPASS 2025-2026-2 Fall.xlsm | B | 1,800 | 2025-09-25 to 2025-10-10 | Loaded (includes Week 0) |
| QPASS 2025-2026-3 Winter.xlsm | — | — | — | **Excluded by team decision** (see below) |
| QPASS 2025-2026-4 Spring.xlsm | C | 1,680 | 2026-03-30 to 2026-04-10 | Loaded |
| QPASS 2026-2027-1 Summer.xlsm | C | 1,720 | 2026-06-29 to 2026-07-10 | Loaded |
| QPASS 2026-2027-2 Fall.xlsm | C | 2,136 | 2026-09-24 to 2026-10-09 | Loaded (includes Week 0) |

### Missing quarters (no workbook linked)

These are recorded as **unresolved**, not assumed to be absent from UCSD's
records. No cause is assumed.

- 2019-2020 Winter and Spring
- 2020-2021, 2021-2022, 2022-2023, 2023-2024 (all quarters)
- 2026-2027 Winter and Spring (not yet surveyed as of 2026-10-13)

### Excluded: QPASS 2025-2026-3 Winter.xlsm

Excluded by team decision. In this file every `Total Stall Count` is 0 (rows
are flagged `CHECK NUMBERS` in the workbook), and its `Week 0` sheet contains
September 2025 dates, which belong to Fall, not Winter. The file is not
downloaded into `data/raw/QPASS/`.

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
- Some sheets end with summary rows (`Vacancy`, `Physical Capacity`,
  `Occupancy`, `Oversubscription`), section headings (`SIO`), or a
  "Deleted/Closed Lots" list. These are not observations.

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

All formats include formatted views of the same numbers: day tabs
(`Monday (1)`), `Summary`, `Oversubscription`, `Text Week N`, `Print`,
`PT Summary`, `Stall Type`, `Directions & Links`, `Copy of ... Data`,
`Current Week Data Sorted by Lot`. The loader skips them.

Verified: the Fall 2024 `Monday (1)` tab equals `QPASS Data Entry (Week 1)`
summed by `Report Type` (105/105 rows identical).

Warning: Spring 2019 contains `Current Week Data Sorted by Lot` with
**January 2019** (Winter) dates. Reading every sheet would mislabel Winter
data as Spring, so the loader reads only known data sheets.

## Loader output (`load_qpass`)

One row per location x space type x survey date. Every file returns the same
columns:

| Column | Meaning |
|---|---|
| `source_file`, `sheet_name` | Where the row came from |
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

Nothing is dropped silently:

- `df.attrs["skipped_sheets"]`: sheets not read, with the reason.
- `df.attrs["dropped_rows"]`: per sheet, how many non-blank rows were not
  kept. Current counts: Summer 2018 64 (summary blocks: `Vacancy`,
  `Physical Capacity`, `Occupancy`, `Oversubscription`), Summer 2019 6
  (`SIO` section headings), Fall 2019 14 ("Deleted/Closed Lots" list),
  Fall 2024 4 (leftover template rows with no date, location, or counts).
  All other files 0.

Both are also logged. `UnsupportedQPASSFormatError` is raised when a file
does not match a known layout, or when a data sheet is missing a required
column (Formats B/C: `Date`, `Location`, `Type`, `Total Stall Count`, the
four `Open Spaces` columns; Format A: `Structure`, `Lot`, `Type`,
`Total Spaces`). This stops a renamed column in a future workbook from
silently producing blank values.

## Assumptions and decisions

1. **Values are kept raw.** Location and type names are not standardized
   (e.g. old `Visitor: PBS` vs new `Visitor`), trailing spaces are kept
   (`P602` vs `P602 `), and counts are not converted to numbers. Cleaning is a
   later issue.
2. **Blank cells are kept.** Many rows have blank count cells (16-377 per
   file) and Fall 2024 Week 0 has 2 rows with only a date. They are not
   dropped here.
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

## Unsupported content

- **`Fall19 Week 3 Central Campus`** (QPASS 2019-2020-2 Fall.xlsx): different
  layout, no `Structure` label row. Possibly a partial Week 3 survey of
  central campus only. Skipped and logged; not loaded.

## Open questions for the team

- Should Parking Occupancy Reports be used to cover the 2020-2024 QPASS gap?
  Out of scope for issue #1, and the project plan says they are summaries, not
  training rows. Suggest a separate issue.
- `data/raw/.gitkeep` and `data/processed/.gitkeep` are allowed by
  `.gitignore` but not committed, so a fresh clone has no `data/` folder.
- Mapping Format A names (`Visitor: PBS`, `Level 1`) to Format B/C names is
  needed before combining years for modeling.
