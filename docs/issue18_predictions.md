# Availability prediction handoff and evaluation - Issue #18

Follow-up: [Issue #27 error analysis and recency experiments](issue27_predictions.md)
retain historical averages. [Versioned release preparation](model_storage.md)
reproduces the approved model separately from these original experiment outputs.

## Run and integrate

From the repository root, with requirements installed and the integrated CSV built:

```bash
python -m src.train_availability
python -m pytest tests/test_availability_prediction.py -q
python -m uvicorn src.api.saved_model:create_saved_app --factory
```

Training flags: `--dataset`, `--output-dir`, `--model-dir`. Defaults are the
integrated pipeline CSV, `results/issue18/`, and `models/issue18/`.
The command saves `baseline.pkl` early, then `selected.pkl` after selection.
Both regenerated artifacts now serve historical averages. Artifacts and row-level
outputs stay local and gitignored; teammates reproduce them with this command.
No dataset rebuild, notebook or training is required to load an artifact.

The saved-model factory uses the merged registry, recommendation and FastAPI
modules from PRs #21 and #22. Its actual startup wiring is:

```python
from src.api.main import create_app
from src.availability import AvailabilityEstimator
from src.availability_prediction import load_prediction_service, BASIS_DESCRIPTIONS

model = load_prediction_service()  # models/issue18/selected.pkl
estimator = AvailabilityEstimator(
    model, survey_times=model.survey_times,
    basis_descriptions=BASIS_DESCRIPTIONS,
)
app = create_app(estimator=estimator)
```

`src.api.saved_model.create_saved_app` implements this setup, with optional
`artifact_path`, `dataset_path` and `registry_path` Python arguments. Artifact
errors stop this factory before startup rather than silently choosing another
model. The normal `src.api.main:app` entrypoint still fits its original baseline
once; use the saved-model entrypoint above to serve the reviewed artifact and
its explicit support policy. Both use the same endpoint handlers and ranking.
The dataset is still loaded once for current parking groups, never per request.

Only load trusted pickle files. Artifact format v2 stores Python, numpy, pandas,
scikit-learn, scipy and joblib versions in an envelope and in the service. The loader requires
exact version agreement before deserializing the inner model, and reports the
training/runtime versions on mismatch. Recreate artifacts after environment
changes; old v1 files are rejected with a retraining instruction. Run metadata
also records versions and a canonical dataset SHA-256.

## Shared prediction and support contract

`predict(features)` accepts facility, category, subtype, level, weekday (English
day name), observation_time (`HH:MM`) and quarter (Summer/Fall/Winter/Spring or
blank). It returns aligned `prediction` (0-1 or NaN) and `baseline_group`.
Blank subtype/level is allowed. Raw labels are not aliased or pooled across
restrictions. Location IDs come from the shared registry, not model inference.

**One rule defines both selection and serving:** `PredictionService.support_labels`
requires an exact training parking group plus a training-observed survey time,
weekday and quarter. Blank quarter is allowed but always uses the historical
fallback, including for regression services. Unsupported rows retain NaN and an
`unsupported_group`, `unsupported_time` or `unsupported_calendar` reason.
No-history groups remain excluded; coverage was not expanded to favor Ridge.

Regression training and serving both call `select_features` with the explicit
original/engineered mode stored in the artifact. Model display names do not
control transformations. Engineered features add exact parking-group identity
and weekday/time interactions to the original seven fields. They contain no
counts, capacities, target statistics, provenance or quality metadata. Encoders
are fitted inside each training split only. These features do not model year,
date or week of quarter; dates derive weekdays and chronological splits.

Baseline level_1/2/3 retain Issue #11 meanings. A regression uses basis `model`
and is described as **model estimate based on historical surveys**. Being a
regression is not itself a limitation. Fallbacks, nearest-time approximations,
out-of-survey-hour arrivals and calendar limits remain labeled. Arrival and
America/Los_Angeles/calendar handling stay in the API and AvailabilityEstimator.
The regression blank-quarter path returns baseline labels rather than `model`.

## Corrected evaluation

Dataset: 76,102 readings; development 59,979; fixed latest-20%-of-dates holdout
16,123, starting 2025-10-08. Three expanding whole-date validation folds fit
preprocessing/models independently. Selection minimizes pooled MAE over only
supported validation rows, using identical row IDs for all candidates and
alphabetical tie-breaking. Near-full means actual availability <=10%.

There are 42,815 validation readings: 24,492 supported (10,155 near-full) and
18,323 unsupported (7,797 near-full). Exact group history alone covers 32,723
rows; 8,231 of those fail another part of the existing serving rule. Therefore
the support-based numbers below differ from group-history-only diagnostics.
Group-history-only validation: historical MAE 17.154 pp and near-full
MAE 12.326 pp; engineered Ridge 17.760 and
14.514 pp respectively. Both have 32,723 rows
(14,779 near-full). These diagnostics do not replace the
full support rule.

No holdout metric affects selection. The holdout was already inspected in Issue
#11 and in the original PR; it is not a fresh untouched test set.

### Validation performance of requests the saved service supports

| Candidate | Rows | Near-full rows | MAE pp | Near-full MAE pp |
| --- | ---: | ---: | ---: | ---: |
| Historical average (selected) | 24,492 | 10,155 | 18.050 | 12.250 |
| Linear, original | 24,492 | 10,155 | 18.978 | 14.904 |
| Ridge, original | 24,492 | 10,155 | 19.156 | 15.280 |
| Ridge, engineered | 24,492 | 10,155 | 18.217 | 14.218 |
| Random Forest, engineered | 24,492 | 10,155 | 21.059 | 16.329 |
| Gradient boosting, engineered | 24,492 | 10,155 | 21.673 | 18.470 |

Historical averages win the supported validation comparison on both overall
and near-full MAE, so the regenerated selected artifact uses that baseline.
The original pooled result favoring Ridge did not match served coverage and
is superseded as a model-selection result.

### Unsupported validation rows: experimental diagnostics only

The service returns no estimate for these rows. The following research errors
measure candidate extrapolation; they are never advertised as app performance.

| Candidate | Rows | Near-full rows | MAE pp | Near-full MAE pp |
| --- | ---: | ---: | ---: | ---: |
| Historical average (selected) | 18,323 | 7,797 | 22.647 | 17.643 |
| Linear, original | 18,323 | 7,797 | 21.170 | 18.275 |
| Ridge, original | 18,323 | 7,797 | 21.045 | 18.468 |
| Ridge, engineered | 18,323 | 7,797 | 20.536 | 17.870 |
| Random Forest, engineered | 18,323 | 7,797 | 22.477 | 17.401 |
| Gradient boosting, engineered | 18,323 | 7,797 | 23.433 | 20.354 |

### Pooled experiments versus supported holdout performance

Pooled experiments include unsupported extrapolations. They explain the original
Ridge win but do not determine the deployed choice. Holdout is reported only
after selection is frozen; historical averages remain selected regardless.

| Candidate | Pooled validation MAE pp | Supported holdout MAE pp | Supported holdout near-full MAE pp |
| --- | ---: | ---: | ---: |
| Historical average (selected) | 20.018 | 21.047 | 13.729 |
| Linear, original | 19.917 | 21.195 | 16.263 |
| Ridge, original | 19.965 | 21.209 | 16.401 |
| Ridge, engineered | 19.209 | 20.666 | 15.967 |
| Random Forest, engineered | 21.666 | 23.229 | 17.072 |
| Gradient boosting, engineered | 22.426 | 24.103 | 19.494 |

Holdout supported: 11,665 readings, 2,975 near-full; baseline MAE 21.047 pp, near-full MAE 13.729 pp.

Holdout unsupported_experimental: 4,458 readings, 675 near-full; baseline MAE 40.341 pp, near-full MAE 27.706 pp.

Fixed starting settings remain unchanged: Ridge alpha=10; Random Forest 60
trees/depth 12/minimum leaf 10; gradient boosting 60 depth-3 stages/minimum leaf
10; seed 42. There was no tuning against the holdout. Ridge's controlled original
versus engineered comparison is retained, but its feature gains do not establish
superiority over the baseline on served requests. The baseline pools sparse
weekday/time/quarter combinations and remains stronger on supported validation.

`metrics.csv` contains every split, including zero-count subsets.
`validation_summary.csv` is the supported selection table;
`validation_coverage.csv` and `holdout_coverage.csv` include all coverage slices,
including group-history-only diagnostics. `predictions.csv` retains record IDs,
support reasons, raw experimental predictions and `served_prediction` (NaN for
unsupported rows). Saved services are refitted on all records after frozen
holdout evaluation; metrics refer to the earlier evaluation fits, not the refit.
Serving coverage consequently uses all available historical groups. These are
model-support metrics before current registry and permit eligibility filters;
they are not a separate validation of the full recommendation ranking.

## Occupancy-report assessment

Inspected the official [quarterly archive](https://rmp-wapps.ucsd.edu/TS/Survey/Survey%20of%20Parking%20Space%20Occupancy%20Levels/Quarterly%20Tables/Contents.html)
and [historical campus tables](https://rmp-wapps.ucsd.edu/TS/Survey/Survey%20of%20Parking%20Space%20Occupancy%20Levels/Historical%20Tables%20and%20Charts/1%20Occupancy%20University%20of%20California,%20San%20Diego.pdf)
on 2026-10-31. The archive lists quarterly reports from 2000/01 through Summer
2026/27, with missing periods (including Summer 2025/26). The historical campus
PDF has 44 pages: category-level average weekday demand at peak and quarterly
hourly empty-space tables (8 AM through 5 PM), not individually dated surveys.
Those tables include A-space campus totals, which are broader than exact QPASS
facility/category/subtype/level groups. They cannot establish daily targets or
later-quarter prediction accuracy.

Also downloaded and inspected `Occupancy 2025-2026-2 Fall.xlsm` from that
archive, without changing raw project files. Its `Pivot Table Data` sheet has
1,104 rows and 44 columns, including Date, Structure, Lot #, Garage Level,
Space Type, Space Subtype, Inventory By Location, and hourly open counts.
The first inspected data rows have blank Date values, even when hourly values
are populated (for example structure 8980, A, level B2). `By Structure` and
`By Space Type` aggregate inventory and hourly open stalls from 8 AM–5 PM;
their scope differs (12,230 structure stalls versus 17,939 space-type stalls
in the displayed totals). Some groups, such as Arbor, have inventory but
missing hourly counts. This is not a verified set of individually dated
observations. Historical numeric location codes also need a reviewed crosswalk.

No occupancy features or synthetic dated rows are included. Same-quarter summary
values risk including validation dates and lack a verified publication cutoff.
Even an aggregate comparison needs matched location scope, category, time,
denominator and survey-period definitions; those crosswalks are not established.
Use these reports as historical context. Any future feature needs a verified
as-of publication date and a train-only ablation before use. This decision
allows baseline and selected-model delivery to proceed independently.

## Limits and integration checks

Tests cover saved service -> AvailabilityEstimator -> Recommender -> FastAPI,
for both baseline and regression, without fitting at load/startup/request time.
They check exact-time regression wording, nearest-time limitations, blank-quarter
baseline fallback, explicit feature mode after model rename, incompatible
artifacts, identical supported validation rows, and unchanged selection when
holdout targets change.

Observations concentrate near quarter starts, on weekdays at 08:00, 10:00,
12:00 and 14:00. Missing later-quarter weeks remain unvalidated, not filled with
invented dated observations. Estimates do not certify current allocations,
permit eligibility or live availability. Startup and missing-prediction handling
use the existing API contract; frontend files were not changed. The updated
wording contract is documented for Dylan in recommendations_handoff.md; no
separate teammate confirmation or joint walkthrough is claimed.

Verification on 2026-11-03: 710 tests and 39 subtests passed, no skips. The
saved-model uvicorn factory also served a real POST /recommendations request
successfully with distinct first/backup choices. The DS3 review was rerun
against main; its report remains local and uncommitted.
