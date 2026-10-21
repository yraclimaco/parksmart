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
produce byte-identical outputs.

## What it does

1. `load_all_qpass` → `reshape_loaded_observations` → `validate_observations`
   on all workbooks together, so repeats and conflicts across files are found.
2. `run_capacity_matching` (label standardization + capacity selection) for
   every manifest quarter. Its reports go to `data/interim/pipeline/capacity/`.
3. One-to-one join of both tables on source file, sheet, Excel row, survey
   date, and time slot. The pipeline stops with an error if a key repeats, a
   capacity row matches no observation, or academic year/quarter disagree.
   Observations from a workbook outside the capacity manifest are kept and
   excluded with `capacity:not_in_capacity_manifest`.
4. Inclusion decision, deduplication, and `fraction_available`.

## Inclusion rule

A row is in the analysis dataset only when all of these hold:

- Capacity selection accepted a capacity (`selected_capacity` is set) and did
  not exclude the row (`exclusion_reason` empty).
- No blocking quality flag. Blocking: missing datetime/location/type; missing,
  text, negative, nonfinite, or fractional open spaces;
  `conflicting_observation`; `ambiguous_allocation_requires_review`.
- `open_spaces <= selected_capacity`. Counts are never clipped or filled.

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
| `audit.csv.gz` | Every observation with all loader, quality, label, and capacity columns plus `included`, `exclusion_reasons`, `duplicate_of` |
| `summary.md` | Totals, exclusion reasons, coverage by quarter and facility, limitations |
| `exclusion_reasons.csv` | Rows per exclusion reason (a row can have several) |
| `coverage_by_facility_quarter.csv` | Included rows per facility and quarter |
| `loader_audit.json` | Workbooks loaded, sheets skipped, rows dropped by the loader |
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
plus `open_exceeds_selected_capacity`, `exact_repeat`,
`duplicate_capacity_disagreement`, `capacity:not_in_capacity_manifest`.

## Analysis dataset columns

| Column | Meaning |
| --- | --- |
| `record_id` | `source_file\|sheet_name\|source_row\|date\|time column`; also in the audit |
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
