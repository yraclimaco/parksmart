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
| `source_order` | Original Order column when available; not a verified allocation ID |
| `sub_type_in_format`, `report_type_in_format` | Per-row booleans from actual sheet headers, before schema filling |
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
- `not_in_format`: the shared loader verified that the source sheet lacked the
  header (including Format A, older Format B and some Format C sheets).
- `blank`: the header existed but the source cell was blank.
- `blank_or_unavailable`: header presence is unknown, for example an externally
  constructed loader-shaped table with no presence evidence. No absence is guessed.

The per-row presence booleans survive mixed sheets, `load_all_qpass()`, reshaping,
and validation. They describe source layout, not whether values are required.

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
- `ambiguous_allocation_requires_review`: a Format C identity group has different
  capacity payloads. These could be separate unnamed allocations; capacity is not
  added to identity and no distinct allocation is inferred from capacity alone.
  All members require review, including any exact repeated subset.
- `conflicting_observation`: an identity group has different count/capacity
  payloads and is not classified as an ambiguous Format C allocation group.
  Equal-capacity Format C rows with differing counts still get this flag.
- Exact repeats can coexist with either review flag. No flag deletes or combines rows.
- `observation_group` groups identities for review within this run; it is not
  a stable identifier across runs. Source file, sheet and row remain available.

`quality_flag` joins failures with '|'; `quality_pass` means only that implemented
checks passed. Per-check counts overlap; `any_check` counts unique failed rows.

## Format C source review (2026-10-20)

Inspected the local Spring 2025?2026, Summer 2026?2027 and Fall 2026?2027
`Data Entry` headers and ambiguous source rows. Spring Athena Visitor rows
12?15 have capacities 30, 9, 10 and 210 on 2026-03-30. Their Zone, Order
and Report Area values are all 0; Neighborhood and Lot / Structure also match.
Report Type is Visitor throughout; Sub Type is absent in Spring and Summer.
The repeated right-hand Structure / Lot, Space Type and Total Spaces columns
are helper copies, with count/time summaries rather than a verified allocation
identifier. These examples do not establish separate allocation identities.

The loader now preserves `Order` as `source_order`, alongside the existing
spatial/report metadata and original Excel row. Its meaning is unverified, so
it is not used as an identity key. Existing subtype and level distinctions
remain identity keys. Unresolved differing-capacity groups get the ambiguity
flag above. Do not delete, sum, or select one capacity automatically.

## Downstream coordination

Daira's label-standardization work is now on `main` (merged before the
2026-10-20 revision). `src/labels.py::prepare_label_records()` accepts audited
observations directly:

```python
from src.labels import prepare_label_records
label_records = prepare_label_records(audited)
```

Regression tests exercise shared loader ? reshape ? validate ? label adapter for
all three formats. Labels, timed rows, quality flags, raw values, presence
booleans, provenance and audit attributes survive without modifying the input.
Label formatting/reconciliation remains task #3's responsibility.

- Hanrong's `src/compare_capacities.py` on
  `origin/issue-4-inventory-capacity` reads `location`, `type`, `sub_type`,
  `level`, `date` and `total_stall_count`. These names remain available.
  His current entry point performs its own wide-to-time iteration; use the
  shared loader table for that entry point, or adapt it to consume this already
  timed output rather than reshaping a second time. Capacity matching must not
  sum subtype/level allocations without an explicit mapping decision.

The label adapter is verified by integration tests against the merged code.
Hanrong's separate capacity entry point still requires the adaptation noted above.

## Outputs

The notebook exports `observations.csv`, `questionable_records.csv`,
`quality_summary.csv`, and `run_metadata.json` under
`data/processed/qpass-notebook/`. Counts/datetimes are typed in memory; CSV
consumers should explicitly parse date/datetime columns when reloading.
Generated files remain ignored as Yra requested. A dated summary and actual
flagged examples are saved in notebook Markdown for review on GitHub.
