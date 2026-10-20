# Standardize QPASS facility, category, and subtype labels

Closes #3

QPASS labels vary across quarters. This change adds reusable formatting and
explicit aliases while preserving raw values, source rows, dates, and meaningful
restrictions. Uncertain labels remain in the output with reasons.

The notebook uses the Issue #1 shared loader. Current reports cover 23,428
records across 15 workbooks, with 220 unresolved records (0.94%). Counts refer
to loader records before Issue #2 observation-time reshaping.

Review fixes:

- Flag EV (Bagged Or Not In Use) as unresolved without changing its wording;
  20 additional records require review. Other specialized categories stay
  distinct, and unchanged does not imply permit eligibility.
- Update AGENTS.md with closure handling, scope priority, ownership-check status,
  the integration-test command, and the EV decision.
- Consistently flag Reserved, Accessible, Carpool, and Electric Vehicle wording
  as keep_separate; preserve restrictions for downstream eligibility checks.
- Standardize closed category wording to Closure with unresolved status,
  retaining raw text and limiting closure to its source record's survey time.
- Add generated-workbook integration coverage for the shared loader and label
  pipeline, checking raw values, provenance, counts, and output validation.
- Log missing Summer 2019 guard columns and record check status in attrs.
- Prioritize the P602-specific 2hr As correction regardless of mapping order;
  retain unresolved wording at P103 and other unverified facilities.

Validation: 93 label tests passed. The full suite passed 169 tests, with 3
real-workbook tests skipped in a temporary code-only copy. Ruff and whitespace
checks passed. The notebook was rerun locally after the EV decision; its saved
outputs show 220 unresolved records and passing integration checks across 15
workbooks. Compact reports are included; the full dataset and
code_review.md remain ignored. The DS3 review found no Must fix or Should fix
items; remote main freshness could not be verified because GitHub was unreachable.

Decision evidence and limitations are in docs/issue3_label_decisions.md.

Issue #2 integration: agree on column names, count units, and duplicate-check
keys while retaining raw labels and provenance. Matching standardized labels
alone do not establish duplicate observations.
