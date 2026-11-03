# Recommendations and saved-prediction handoff

PRs #21 and #22 are merged. The shared registry, eligibility/ranking modules,
website connection, CORS POST support and POST `/recommendations` are implemented.
Current endpoint architecture and normal baseline startup are in `backend.md`.
Do not copy the retired standalone endpoint sketch: use the existing app factory.

## Serve the reviewed Issue #18 artifact

From the repository root, after building the integrated CSV:

```bash
python -m src.train_availability
python -m uvicorn src.api.saved_model:create_saved_app --factory
```

The saved-model factory loads `models/issue18/selected.pkl`, checks exact runtime
Python/numpy/pandas/scikit-learn/scipy/joblib versions, wraps it in AvailabilityEstimator,
and passes the ready estimator to the existing `create_app(estimator=...)`.
Missing, old or incompatible artifacts fail startup with a clear instruction;
no silent fallback to a different model occurs. The API still loads the CSV and
registry once for current-group candidates. No request trains or rebuilds data.

For custom paths, the equivalent Python setup is:

```python
from src.api.main import create_app
from src.availability import AvailabilityEstimator
from src.availability_prediction import load_prediction_service, BASIS_DESCRIPTIONS

model = load_prediction_service("models/issue18/selected.pkl")
estimator = AvailabilityEstimator(
    model, survey_times=model.survey_times,
    basis_descriptions=BASIS_DESCRIPTIONS,
)
app = create_app(estimator=estimator)
```

The normal `src.api.main:app` command remains the original baseline integration.
Use the saved-model entrypoint to exercise Issue #18's saved coverage policy.
The website uses `VITE_RECOMMENDATION_SOURCE=api` and its configurable backend
URL; frontend remains a synced copy and is not edited in this branch.

## Prediction contract and wording for Dylan

The corrected selected model is historical averages, selected on supported
chronological validation rows. The candidate regressors remain reproducible.
Exact facility/category/subtype/level keys are preserved. Survey time, weekday
and quarter must be seen in training; blank quarter uses labeled baseline
fallback even for a regression. Unknown exact groups stay NaN, not campus-wide
averages. AvailabilityEstimator leaves NaN missing so ranking can return
`predictions_unavailable`. That status does not mean parking is full.

`baseline_group == "model"` is a regression estimate and is described as
**model estimate based on historical surveys**, rather than an observed average.
It is not limited solely because it uses regression. `estimate_note` continues
to mark actual limitations: fallback basis, nearest survey time, out-of-survey
hours and unsupported calendar coverage. Exact-time regression tests ensure the
model label does not create a spurious limitation. The module changes and this
handoff supply the wording contract; separate teammate confirmation is pending.

## Responses and responsibilities

- `ready`: first choice present, distinct backup when available.
- `no_suitable_location`: no eligible/scorable option; not evidence of full parking.
- `predictions_unavailable`: eligible options exist without supported estimates.
- HTTP 503: API startup resources unavailable; health/catalog may remain usable.

Registry IDs and current groups come from Dylan's shared modules. Walking is
straight-line estimation, not routed navigation. Starting location is accepted
but unused; permit eligibility checks arrival only. Calendar verification is
limited to the dates in `src/ucsd_calendar.py`. None of these are inferred by
the model. Later-quarter accuracy remains unvalidated.

Tests in `tests/test_availability_prediction.py` cover the saved baseline and
regression through AvailabilityEstimator, Recommender and actual FastAPI
responses, including dependency checks, no refitting and estimate wording.
See `issue18_predictions.md` for corrected coverage counts, validation, holdout,
occupancy-report findings and artifact recreation.
