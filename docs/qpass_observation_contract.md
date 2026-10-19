# Issue #2 observation contract (PR #9 revisions)

## Shared entry point

```python
from src.qpass_loader import load_all_qpass
from src.qpass_observations import (
    reshape_loaded_observations,
    validate_observations,
)

loaded = load_all_qpass()  # data/raw/QPASS/
observations = reshape_loaded_observations(loaded)
audited, summary = validate_observations(observations)
```

No independent workbook parser remains in task #2. The shared loader alone
decides which raw sheets/template rows are excluded and records why in attrs.
These exclusions are retained in exported run metadata, not silently counted
as passing observations. Core logic lives in `src/qpass_observations.py`;
run tests with `python -m pytest -q`. Run the notebook from the repository
root or `notebooks/` after `python -m src.download_qpass`.

## Shared names and values

| Field | Contract |
| --- | --- |
| `location` | Shared loader facility label, unchanged; no aliases guessed |
| `type` | Category from the loader's Type column, unchanged |
| `sub_type` | Separate optional subtype, unchanged; never populated from type |
| `report_type` | Auxiliary optional report grouping, never substituted for type |
| `level`, `raw_structure`, `raw_lot` | Preserved for allocation scope and source review |
| `source_file`, `sheet_name`, `source_row` | Original workbook/sheet/Excel row provenance |
| `format_version`, `academic_year`, `quarter`, `quarter_number` | Preserved loader metadata |
| `date` | Loader date parsed/normalized to midnight; original in raw_date |
| `total_stall_count` | Parsed nullable Float64 workbook capacity; original in raw_total_stall_count |
| `observation_datetime`, `observation_time` | Added local datetime and HH:MM time |
| `source_time_column` | One of open_8am, open_10am, open_12pm, open_2pm |
| `open_spaces`, `raw_open_spaces` | Parsed selected reading and original value |
| `loader_row_id` | Run-local input row position; not a persistent facility identifier |
| `raw_location`, `raw_type`, `raw_sub_type`, `raw_report_type`, `raw_level` | Copies before any later reconciliation |

The four wide open_* columns are replaced by timed rows, not renamed into a
different facility/category schema. Every other loader column remains, and
every loader row yields four observations, including blank or invalid readings.
No `facility_name`, `parking_category`, `parking_subtype`, `capacity`, or
`source_sheet` aliases are created. Those earlier task #2 names are retired.

Optional report_type/sub_type status columns are informational:

- `present`: a nonblank value exists.
- `not_in_format`: blank field in Format A, whose layout did not have it.
- `blank_or_unavailable`: blank in another format; the shared loader does not
  currently expose whether an optional header existed in that individual sheet.

Missing optional metadata does not fail an observation. Missing `type`,
`location`, or datetime does. Category reconciliation remains task #3's job.

## Reading and duplicate rules

Blank means missing, empty string, or whitespace-only string. Nonblank text
that fails numeric parsing gets `unexpected_text_<count>` instead of a missing
reading flag. Strings such as FULL, NA, n/a and '-' are not translated to zero.
Negative, fractional and nonfinite numeric values retain separate flags. Small
negative floating-point values are preserved without an assumed tolerance.

Apparent identity is datetime + location + type + sub_type + level. Comparison
trims label whitespace and treats optional blanks equally without changing
the original labels. Required identity fields must be complete for duplicate
classification; optional report_type is not part of the identity.

- `exact_repeated_record`: at least two rows share identity and the parsed
  capacity/open-count payload. Numeric strings compare by parsed numeric value.
  Invalid text tokens remain distinct from blanks and from other text tokens.
- `conflicting_observation`: an identity group has different count or capacity
  payloads. All members get the conflict flag, even a repeated subset.
- Both flags can apply. Neither causes deletion or aggregation.
- `observation_group` groups identities for review within this run; it is not
  a stable identifier across runs. Source file, sheet and row remain available.

`quality_flag` joins failures with '|'; `quality_pass` means only that implemented
checks passed. Per-check counts overlap; `any_check` counts unique failed rows.

## Downstream coordination

Remote implementations inspected on 2026-10-18:

- Daira's `src/labels.py` on `origin/Daira-Merino-branch` uses `location`,
  `type`, `sub_type` and provenance in `prepare_label_records()`. These names
  remain available here; no replacement label mapping is implemented in task #2.
- Hanrong's `src/compare_capacities.py` on
  `origin/issue-4-inventory-capacity` reads `location`, `type`, `sub_type`,
  `level`, `date` and `total_stall_count`. These names remain available.
  His current entry point performs its own wide-to-time iteration; use the
  shared loader table for that entry point, or adapt it to consume this already
  timed output rather than reshaping a second time. Capacity matching must not
  sum subtype/level allocations without an explicit mapping decision.

The output contract was checked against those source files, not confirmed in a
conversation. Daira and Hanrong should confirm their intended entry points on
PR review. No messages were sent and their branches were not modified.

## Outputs

The notebook exports `observations.csv`, `questionable_records.csv`,
`quality_summary.csv`, and `run_metadata.json` under
`data/processed/qpass-notebook/`. Counts/datetimes are typed in memory; CSV
consumers should explicitly parse date/datetime columns when reloading.
Generated files remain ignored as Yra requested. A dated summary and actual
flagged examples are saved in notebook Markdown for review on GitHub.
