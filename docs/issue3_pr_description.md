# Standardize QPASS facility, category, and subtype labels

Closes #3

QPASS labels vary across quarters, so the same facility or category can appear
under several names. This change adds reusable formatting and exact alias
mappings while preserving raw values, source rows, and meaningful restrictions.
Uncertain labels remain in the output with unresolved flags and notes.

The notebook uses the Issue #1 loader. It inventories labels by file and quarter,
compares raw/cleaned values, and exports unresolved lists and summaries. The
reviewed run covers 23,428 records across 15 workbooks, with 188 unresolved
records (0.80%). Missing categories and ambiguous source wording are not guessed.
See `docs/issue3_label_decisions.md` for evidence and coverage limits.

Validation: 144 tests passed and 3 real-workbook tests skipped when running the
full suite in a temporary code-only copy using myenv. All 86 selected project
unit tests also passed in the working checkout, and Ruff passed on the label
modules and tests. Regression tests cover integer, float, and text zero
identifiers while preserving raw values.

The saved notebook completed a sequential run through 8B across all 15 loaded
workbooks. Reapplying the float-zero fix to the saved 23,428-record export changed
no record statuses; the unresolved total remains 188 (0.80%). Compact reports
are included; the full dataset and code_review.md remain ignored.

The 3 skipped tests require raw workbooks. They were not run because this
session cannot read those files; the code-only test copy contains no raw data.
The notebook's saved integration checks provide separate real-data evidence.

Issue #2 integration: counts currently refer to loader records before time
reshaping. The functions can run before or after reshaping while retaining raw
labels and provenance. Confirm column names, count units, and duplicate-check
keys when integrating the two issues.
