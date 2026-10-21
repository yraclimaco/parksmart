# Integrated data pipeline (Issue #10)

One command rebuilds the analysis dataset from the original workbooks. No
notebook steps are required and the workbooks are never modified.

## Run it

From the repository root, with the virtual environment active:

```bash
python -m src.download_qpass       # QPASS workbooks -> data/raw/QPASS/
python -m src.download_inventory   # Inventory workbooks + manifest
python -m src.build_dataset        # ~1 minute
```

`--reuse-inventory` skips re-extracting Inventory groups that are already in
`data/interim/inventory/`. Other flags: `--qpass-dir`, `--manifest`,
`--inventory-dir`, `--capacity-dir`, `--output-dir`. The same source files
produce byte-identical outputs, including `audit.csv.gz` (gzip is written with
a fixed timestamp).

**Excluded workbook.** `QPASS 2025-2026-3 Winter.xlsm` is excluded by team
decision (`EXCLUDED_FILES` in `src/download_qpass.py`). The downloader skips
it, and the pipeline also leaves it out if it is already on disk: it is not
loaded, and its row is dropped from the copy of the manifest the capacity step
uses (`data/interim/pipeline/capacity/inventory_sources_used.csv`). The
excluded file is listed in `summary.md` and `loader_audit.json`
(`excluded_files`).

## What it does

1. `load_all_qpass` → `reshape_loaded_observations` → `validate_observations`
   on all included workbooks together, so repeats and conflicts across files
   are found.
2. `run_capacity_matching` (label standardization + capacity selection) for
   every manifest quarter. Its reports go to `data/interim/pipeline/capacity/`.
3. One-to-one join of both tables on source file, sheet, Excel row, survey
   date, and time slot. The pipeline stops with an error on real join problems:
   a missing file/sheet/row/time identifier, a repeated key, a capacity row
   that matches no observation, an academic year/quarter disagreement, or a
   changed row count. Two cases are kept and excluded instead:
   - a workbook outside the capacity manifest: `capacity:not_in_capacity_manifest`;
   - a reading with no readable survey date: `capacity:missing_survey_date`.
     Its capacity row, if any, is matched by file, sheet, row, and time slot
     and accounted for, but not attached. Its `record_id` uses `no-date`.
4. Inclusion decision, deduplication, and `fraction_available`.
5. Output check (`validate_outputs`): the written files are re-read and the
   build fails if the audit total differs from the reshaped source
   observations, included plus excluded differs from the total, an included
   row has an exclusion reason or blocking flag, a fraction is invalid, a
   `duplicate_of` link does not point to the retained copy of the same
   observation, or an excluded workbook appears.

## Inclusion rule

A row is in the analysis dataset only when all of these hold:

- Capacity selection accepted a capacity and did not exclude the row
  (`exclusion_reason` empty).
- The selected capacity is a finite, positive whole number. Missing,
  non-finite, zero, negative, or fractional values are excluded as
  `invalid_selected_capacity`; the value received is kept in
  `selected_capacity_raw` in the audit.
- No blocking quality flag. Blocking: missing datetime/location/type; missing,
  text, negative, nonfinite, or fractional open spaces;
  `conflicting_observation`; `ambiguous_allocation_requires_review`.
- `open_spaces <= selected_capacity`. Counts are never clipped or filled.
- `fraction_available` is finite and between 0 and 1; anything else is
  excluded as `invalid_fraction_available`. Zero open spaces with a valid
  capacity is a usable reading (fraction 0); zero open spaces with zero
  capacity is not.

Flags on the QPASS capacity column (`zero_capacity`, `missing_total_stall_count`,
`open_exceeds_capacity`, ...) do not block on their own: capacity selection
already rejects or replaces unsafe QPASS capacities. The full policy is
`QUALITY_FLAG_BLOCKS` in `src/build_dataset.py`; a new quality check without a
policy entry stops the pipeline.

**Deduplication.** Included rows in one `observation_group` (same datetime,
location, type, subtype, level, and readings) are exact repeats. The copy with
the smallest (source file, sheet, row) is kept with `duplicate_copies` set; the
others are excluded as `exact_repeat` with `duplicate_of`. If the copies have
different selected capacities, all are excluded as
`duplicate_capacity_disagreement`.

## Outputs (`data/processed/pipeline/`, gitignored)

| File | Contents |
| --- | --- |
| `analysis_dataset.csv` | One row per usable observation (columns below) |
| `audit.csv.gz` | Every observation with all loader, quality, label, and capacity columns plus `capacity_match`, `selected_capacity_raw`, `included`, `exclusion_reasons`, `duplicate_of` |
| `summary.md` | Totals, exclusion reasons, coverage by quarter and facility, limitations |
| `exclusion_reasons.csv` | Rows per exclusion reason (a row can have several) |
| `coverage_by_facility_quarter.csv` | Included rows per facility and quarter |
| `loader_audit.json` | Workbooks loaded and excluded, sheets skipped, rows dropped by the loader |
| `pipeline.log` | Full run log (loader messages, capacity-step messages) |

The command prints only four progress steps and a short report. The capacity
batch's detailed per-quarter printout is saved to
`data/interim/pipeline/capacity/capacity_batch.log`. The report (also at the
top of `summary.md`) states the result in plain language: what one row means,
how many readings are usable, and why the rest were left out. Each excluded
reading is counted once, under the first matching group in `REASON_GROUPS`
(`src/build_dataset.py`); plain-language labels for reason codes are in
`REASON_LABELS`.

`exclusion_reasons` uses prefixes: `quality:` (observation checks),
`capacity_excluded:` and `capacity_unresolved:` (capacity selection reasons),
`capacity:` (no capacity row: `not_in_capacity_manifest`,
`missing_survey_date`), plus `invalid_selected_capacity`,
`open_exceeds_selected_capacity`, `invalid_fraction_available`,
`exact_repeat`, and `duplicate_capacity_disagreement`.

## Checking outputs

Every build runs `validate_outputs` on the files it just wrote. To check an
existing output folder against the current workbooks (for example a temporary
`--output-dir`):

```bash
PARKSMART_PIPELINE_DIR=/path/to/output python -m pytest tests/test_build_dataset.py -k real -q
```

Without the variable, the test checks `data/processed/pipeline/`; it is skipped
when the workbooks or outputs are missing.

## Analysis dataset columns

| Column | Meaning |
| --- | --- |
| `record_id` | `source_file\|sheet_name\|source_row\|date\|time column`; also in the audit (`no-date` plus `#n` for undated readings) |
| `facility`, `category`, `subtype` | Standardized labels (Issue #3) |
| `level` | Original QPASS level, blank when not level-specific |
| `facility_raw`, `category_raw`, `subtype_raw` | Original workbook values |
| `label_status` | Label standardization status |
| `observation_date`, `observation_time`, `observation_datetime` | Survey date, HH:MM slot, and local datetime |
| `academic_year`, `quarter` | Period from the workbook |
| `open_spaces` | Open-space count |
| `selected_capacity` | Capacity used for the fraction |
| `capacity_source` | `qpass` or `inventory_same_quarter` |
| `capacity_acceptance_reason`, `capacity_assumption` | Why the capacity was accepted; assumption text for Inventory fallback |
| `fraction_available` | `open_spaces / selected_capacity`, between 0 and 1 |
| `quality_flag` | Non-blocking quality flags (or `pass`) |
| `qpass_source_issue` | Known source-data problem, e.g. Fall 2025 zero-capacity formula |
| `inventory_coverage_status` | Whether that quarter's Inventory workbook was available |
| `duplicate_copies` | Number of identical source copies this row stands for |
| `source_file`, `sheet_name`, `source_row`, `format_version` | Provenance |

When reloading the CSV, parse `observation_date` and `observation_datetime` as
dates.

## Limitations

- QPASS mainly covers the first weeks of each quarter; several quarters are
  missing from the archive, and Winter 2025-2026 is excluded by the team.
- Fall 2026-2027 has no Inventory workbook, so its rows rely on QPASS capacity
  alone.
- `inventory_same_quarter` capacities assume the Inventory count applies on
  every survey date in that quarter.
- `fraction_available` is a historical survey reading, not live availability.
