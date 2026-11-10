# Availability error analysis and focused experiments — Issue #27

Analysis date: November 10, 2026. Historical averages remain the approved model
from [PR #23](https://github.com/yraclimaco/parksmart/pull/23). The experiments
below write separate outputs and do not replace the working artifact.

## Evaluation boundaries

Use the integrated analysis CSV and Issue #18's three expanding whole-survey-date
development folds. The latest 20% of unique dates are the previously inspected
holdout; exclude them before error analysis and experimentation. This issue does
not score that holdout. Development validation has also been examined before, so
these are exploratory comparisons, not fresh confirmation of future accuracy.

All candidates require the same training-observed exact
facility/category/subtype/level, survey time, weekday and quarter through
`PredictionService.support_labels`. Blank quarters retain historical fallback;
unsupported requests retain NaN. The evaluator asserts equality of supported
record IDs in every fold, not just equality of row counts. These are model
support results before current registry and permit filters.

## Largest actionable weaknesses

The existing baseline validation has 24,492 supported readings out of 42,815
(57.20%), including 10,155 near-full readings. Another 10,092 readings have no
exact-group history, and 8,231 fail calendar support. Improving MAE alone does
not address this coverage gap; do not fill missing estimates to increase it.
Near-full means actual availability at most 10%. Errors below are percentage
points of available fraction, weighted by readings rather than facility totals.

| Baseline slice | Supported readings | MAE pp | Near-full MAE pp |
| --- | ---: | ---: | ---: |
| Visitor category | 4,429 | 22.882 | 24.218 |
| Hopkins | 1,268 | 24.449 | 18.172 |
| Pangea | 1,266 | 20.692 | 24.907 |
| Exact-group history: 1–4 distinct dates | 1,786 | 20.411 | 15.967 |
| Exact-group history: 5–19 distinct dates | 4,187 | 22.124 | 21.239 |
| Exact-group history: 20–49 distinct dates | 10,897 | 17.539 | 12.264 |
| Exact-group history: 50+ distinct dates | 7,622 | 15.991 | 7.723 |

Visitor near-full estimates overstate availability by 24.064 pp on average;
666 near-full readings overstate it by more than 20 pp. High-risk examples also
include P014 (117 near-full readings, 36.390 pp near-full MAE) and Torrey Pines
Center North (125, 38.682 pp). These are historical slices, not current-use or
eligibility claims. Sparse restricted groups can show extreme errors; keep
their definitions separate rather than borrowing unrestricted counts.

| Quarter | Supported readings | Baseline MAE pp |
| --- | ---: | ---: |
| Fall | 11,360 | 16.216 |
| Summer | 6,860 | 20.809 |
| Winter | 3,468 | 17.324 |
| Spring | 2,804 | 19.632 |

The quarter comparison mixes facilities, categories, years and survey times.
It does not establish that quarter itself causes the errors. Priorities are
compatible dated visitor observations, coverage for new/changed exact groups,
and later-quarter observations. The training-history pattern motivates testing
recency while cautioning that dropping old history can make sparse estimates
worse. Baseline fallback-level diagnostics are exported too.

## Two fixed experiments

1. **Recent three years:** fit the same hierarchical historical averages on
   dates within three calendar years of the last training survey. If an exact
   group is absent in that window, use its full-history baseline, preserving
   support and restrictions rather than replacing it with a recent global mean.
2. **Two-year half-life:** retain all training rows and compute the same grouped
   means with weight `2 ** (-age_days / 730.5)`. Age is relative to the last
   training date in each fold. No validation date or target determines weights.

No new features, encoders, category mappings or hyperparameter search are used.
Every mean, fallback and reference date is fitted on that fold's training data.
The criteria were fixed before execution: recommend a change only with at least
1 pp pooled supported MAE improvement, no worse pooled near-full MAE, unchanged
supported IDs and no fold losing more than 0.5 pp overall MAE. These practical
thresholds avoid promoting a tiny point estimate; they are not a significance
test. Do not tune them after inspecting this run or the old holdout.

The committed pandas implementation and an independent standard-library
calculation agree on the following results.

| Method | Supported rows / coverage | MAE pp | Near-full MAE pp | Near-full mean overestimate pp |
| --- | ---: | ---: | ---: | ---: |
| Historical averages | 24,492 / 57.20% | 18.050 | 12.250 | 11.790 |
| Recent three years, older-group fallback | 24,492 / 57.20% | 17.929 | 12.571 | 12.163 |
| Two-year half-life | 24,492 / 57.20% | 18.036 | 12.321 | 11.869 |

Both changes make near-full errors worse. The 0.121 pp and 0.014 pp overall
gains also fall short of the predeclared 1 pp threshold. **Retain historical
averages.** The number of near-full predictions overestimating by more than
20 pp rises from 2,086 to 2,147 with the recent window and 2,143 with decay.

| Fold | Supported rows | Baseline MAE / near-full MAE pp | Recent MAE / near-full MAE pp | Decay MAE / near-full MAE pp |
| --- | ---: | ---: | ---: | ---: |
| 1 | 4,900 | 13.758 / 9.503 | 13.758 / 9.503 | 13.749 / 9.488 |
| 2 | 10,988 | 18.746 / 14.332 | 18.746 / 14.332 | 18.736 / 14.342 |
| 3 | 8,604 | 19.606 / 11.109 | 19.261 / 12.219 | 19.583 / 11.351 |

Recent-window truncation cannot change the first two folds: their training
history spans less than three years. Only fold 3 evaluates removal of old years.
The second validation block crosses the long gap between 2019 and 2025. Three
folds are therefore not three independent confirmations of a recency benefit.
Academic-week features are deferred: the API's verified 2026–2027 calendar does
not establish correct historical quarter boundaries for all training years.

## Reproduce and hand off

```bash
python -m src.prediction_experiments
python -m pytest tests/test_prediction_experiments.py -q
```

Flags: `--dataset`, `--output-dir`. Local `results/issue27/` contains fold metrics,
the pooled validation summary, errors by facility/category/quarter/history and
fallback level, support reasons, aligned row predictions, fixed settings,
dependency versions and a development-data hash. Row-level outputs remain
gitignored. No command here reads or overwrites `models/issue18/`.

The [additional-data assessment](issue27_additional_data.md) keeps status counts
and occupancy summaries separate from QPASS. Hanrong has not collected his
multi-snapshot dataset yet; its actual historical-data review remains pending.
The [model-storage handoff](model_storage.md) reproduces the approved baseline
without rerunning candidate training and documents the matched bundle, exact
versions, permissions and startup configuration for Daira's merged backend.

Written expert-meeting explanation: historical averages remain the working
reference. Visitor and sparse-history near-full overestimation are the main
actionable errors. Two recency experiments preserve existing support but worsen
near-full predictions, so neither replaces the baseline. Newly collected
compatible dated observations are needed for fresh evaluation. No AWS deployment
or paid usage is enabled by this work. November 5 is past; this document records the November
10 work and does not claim the earlier checkpoint or a joint teammate session.

## Verification

[Linux run 42784254791](https://github.com/yraclimaco/parksmart/actions/runs/42784254791)
at source commit `c8ac676` rebuilt 76,102 readings, passed 42 targeted tests,
then passed the full suite: **918 tests and 39 subtests**, with 38 warnings.
The generated real-data bundle served readiness 200 and two requests with
distinct first/backup choices, exactly one artifact load and fitting disabled.
Missing/incompatible artifacts and unsupported requests are covered by tests.
The DS3 review report remains local and uncommitted.
