# Parking label standardization — Issue #3

## Run

Open `notebooks/01_issue3.ipynb`, restart the kernel, and run all cells in order.
Workbooks must be in `data/raw/QPASS/`. The notebook uses the shared Issue #1
loader; it does not implement a second parser or reshape observation times.
Section 8B writes reports under `results/issue3/`.

```python
from src.qpass_loader import load_all_qpass
from src.labels import prepare_label_records
from src.label_decisions import standardize_labels

source = load_all_qpass()
records = prepare_label_records(source)
cleaned = standardize_labels(records)
```

The notebook also applies the team's Winter 2025–2026 exclusion. If that file
is present, its excluded record count is reported explicitly. Direct callers
must follow the same source-selection policy before comparing totals.

## Output and counting unit

The required columns are `facility_raw`, `facility`, `category_raw`, `category`,
`subtype_raw`, `subtype`, and `label_status`. Loader columns, dates, source file,
sheet, and Excel row are retained. For older workbooks, `facility_raw` is the
loader's reconstructed location; `raw_structure` and `raw_lot` preserve the
original cells used to recover it.

Counts refer to loader records before time reshaping, generally a location and
space type on one survey day. They are neither parking-space totals nor counts
of unique physical stalls. Multiple field problems count once in the overall
unresolved total. Source-row groups combine daily repetitions for inspection.

The saved workbook run reviewed on October 18 contains **23,428 records from
15 workbooks**: 18,276 unchanged, 2,110 standardized, 2,854 keep_separate, and
**188 unresolved (0.80%)**, across 82 source-row groups. Section 8B regenerates
these totals; use its summary if later decisions change them.

## Formatting

Whitespace is trimmed and repeated whitespace collapsed. Words are capitalized
across slash and parenthesis boundaries, while uppercase codes such as TDLLN
and SIO are preserved. This conservative rule cannot distinguish every acronym
from an uppercase word. Empty strings, NA, N/A, NULL, NONE, and NAN are the
configured missing placeholders, matched without case sensitivity. Numeric zero
is preserved and flagged when used as a facility or category identifier,
including float/string forms such as `0.0`.

Exact hour-limited categories use type-first order and unit `Hour`:
`3hr A` becomes `A 3 Hour`, and `Visitor 2 Hours` becomes `Visitor 2 Hour`.
Only recognized types and a complete numeric duration pattern are accepted.
Extra qualifiers, repeated wording, and unexplained numbers are not removed.
Separate subtype values stay in their source field.

## Aliases and restrictions

The JSON files use `raw_value`, `standard_value`, `status`, and `notes`.
A decision may include `scope` to restrict it to original-column values.
Basic whitespace and capitalization fixes are handled in code.

| Decision | Evidence |
|---|---|
| V → Visitor | [UCSD permit definitions](https://transportation.ucsd.edu/commute/permits/index.html) |
| Gliderport / P386 (Gliderport) → P386 | [UCSD Gliderport/Lot P386 notice](https://today.ucsd.edu/story/transportation_services_working_to_expand_parking_commuter_options), [2019 directions](https://cwc.ucsd.edu/node/225) |
| Osler → South | [UCSD directions identify the former name](https://mandeville.ucsd.edu/directions/index.html) |
| A (24/7), 24/7 A → A 24/7 Enforced | P402 workbook screenshots from 2024 and 2025; UCSD permit definitions distinguish A 24/7 from ordinary A |
| 2 Person Carpool → Carpool 2 Person | Hopkins workbook screenshots from Fall 2024 and Summer 2025 |
| Repeated Visitor duration / Carpool wording | Workbook comparisons; exact corrections and references are in the decision notes |
| A Physician A → Physician A | Summer 2025 Stall Type list, Fall 2026 P759 subtype, and [October 2020 Inventory, Table 10, PDF page 66](https://rmp-wapps.ucsd.edu/TS/Survey/Parking%20Space%20Inventory/Quarterly%20Tables/Inventory%202020-2021-2%20October%201.pdf) |
| 2hr As → A 2 Hour at P602 only | P602 comparisons: Fall 2019 `2hr As`, Summer 2024 `2 hour A` |

Corrections preserve restrictions. Visitor modifiers, hour limits, physician and
person-count conditions, and populated subtypes remain separate from broader
categories. Historical P782 SS and VA labels stay distinct; the screenshots
support different source categories, not an alias. The exact transition date
and expansion of VA were not independently confirmed and are not inferred.
No mapping claims equal capacities or physical stall identity across years.

Statuses have this precedence: `unresolved`, `keep_separate`, `standardized`,
`unchanged`. A restricted label can be corrected and still have keep_separate
as its record status. Field statuses and notes explain the decision. Unchanged
means no implemented transformation, not independent verification of eligibility.

## Unresolved values and limits

Missing categories remain missing. Missing subtype alone is allowed because
many source layouts have no subtype field. Zero identifiers, P103/other unverified
`2hr As` occurrences, `A 2hr 12`, bare `24/7`, price-only `$3`/`3.25`,
`Visitor Loading 2`, and `Visitor 2-Hour Limit 6` remain unresolved with their
wording intact.

Summer 2019 Week 2's unnamed 9-space V row after Pangea has an unresolved
facility. The guarded rule checks workbook, week, Excel row 101, raw blank
Structure/Lot cells, V category, and nine spaces. Its cleaned facility is missing;
the loader location and original cells remain available. See the shared schema
audit for the ownership uncertainty.

Potential relationships between Nuevo West and Nuevo West/Vela, and between
TDLLN and Theatre District Garage, are not merged without stronger evidence.
EV4's expansion is also unverified; its distinct subtype text is preserved.
The inventory review is limited to records recovered by the shared loader.
Skipped reports and unsupported content are documented in the Issue #1 audit;
we do not claim their labels or observations have been independently reconciled.

## Deliverables and integration

Section 8B exports raw and cleaned inventories, an unresolved-value list,
unresolved source rows and records, file/quarter counts, examples, and a summary.
The full `standardized_records.json` stays local. Compact reports are allowed by
`.gitignore` so they can accompany the PR.

Issue #2 can apply these functions before or after time reshaping if raw labels
and provenance are preserved. Confirm column names, record-count units, and
duplicate-check keys during integration. Matching labels alone do not establish
that two observations are duplicates.

Run the label tests with:

```bash
python -m pytest tests/test_labels.py tests/test_label_decisions.py tests/test_label_reports.py -q
```

Run the repository's full `pytest` suite locally before submitting. Real-workbook
tests need the source files; the agent's filesystem profile does not allow reading
those files. Saved notebook checks verify raw/provenance preservation and
repeatability across the 15 loaded workbooks.

## Final validation after review fixes

The zero-identifier check now recognizes numeric/text forms such as `0.0`.
All raw values are retained. The full test suite passed in a temporary code-only
copy: **144 passed, 3 skipped** (real-workbook tests require the omitted raw
files). The working-checkout selection passed **86 tests**; Ruff passed on the
label modules and tests. Revalidation of the saved 23,428-record notebook export
changed no record statuses, leaving **188 unresolved**. A local full-suite run
with source workbooks remains additional validation, not evidence claimed here.
