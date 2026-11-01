# Availability prediction handoff and evaluation — Issue #18

## Run and integrate

From the repository root, with requirements installed and the integrated CSV built:

```bash
python -m src.train_availability
python -m pytest tests/test_availability_prediction.py -q
```

Optional flags: `--dataset`, `--output-dir`, `--model-dir`. Defaults are the
integrated pipeline CSV, `results/issue18/`, and `models/issue18/`.
The command writes `baseline.pkl` before comparisons, then `selected.pkl`.
Artifacts and row-level reports stay local and gitignored. Teammates recreate
them with this command; no dataset rebuild or notebook is needed when serving.
Only load trusted pickle artifacts, using the same dependency versions used to
train them. The run metadata records versions and a canonical dataset SHA-256.

Dylan's open PR #21 (`origin/feature/recommendations`) was inspected, including
`src/availability.py`, `src/recommender.py`, and its handoff. Once that PR is
available, the startup integration is:

```python
from src.availability_prediction import load_prediction_service, BASIS_DESCRIPTIONS
from src.availability import AvailabilityEstimator
from src.recommender import Recommender

model = load_prediction_service()  # or models/issue18/baseline.pkl
estimator = AvailabilityEstimator(
    model, survey_times=model.survey_times,
    basis_descriptions=BASIS_DESCRIPTIONS,
)
recommender = Recommender.from_files(estimator=estimator)
```

This snippet requires Dylan's PR; it does not run against main's current API.
It was smoke-tested against PR #21 commit `570c0cb` in a separate checkout,
using the saved selected artifact and real pipeline CSV. An S-permit arrival
at 2026-11-03 09:00 near Geisel returned status `ready`, Torrey Pines Center
North first and Pangea backup, with model and nearest-time notes preserved.
Daira can use the same ready recommender in the endpoint. The API, eligibility,
registry and ranking code are not duplicated or changed in this branch.
Registry location IDs remain Dylan's responsibility; prediction keys are exact
`facility`, `category`, `subtype`, `level`, preserving restricted stalls.

`model.predict(features)` accepts a DataFrame with those four fields plus
`weekday` (English day name), `observation_time` (`HH:MM`) and `quarter`
(`Summer`, `Fall`, `Winter`, `Spring`, or blank outside verified quarters).
Blank subtype/level is supported. Output preserves row order and index and has
`prediction` (available fraction in [0,1] or NaN) and `baseline_group`.
`model` means the selected regression; baseline `level_1`, `level_2`, `level_3`
retain Issue #11 meanings. A blank quarter uses a labeled historical fallback.
Unknown groups, unobserved survey times, weekdays or quarters return NaN with
`unsupported_group`, `unsupported_time`, or `unsupported_calendar`.
Global means remain in the research comparison but are not served for unseen
groups. Missing artifacts raise FileNotFoundError; the API should report unavailable
predictions, never interpret this as full parking.

Arrival parsing, America/Los_Angeles conversion, verified quarter lookup and
nearest-survey-time selection remain in the existing API/arrival adapter. The
model does not infer dates or invent calendar coverage. Dates outside historical
coverage are historical pattern estimates, not validated forecasts for that date.
Dylan's adapter labels nearest-time approximations and out-of-survey-hour requests.
Actual survey times are available on `model.survey_times`; never hardcode them.

## Evaluation snapshot

Local integrated dataset: 76,102 readings. Development: 59,979; fixed latest-20%
date holdout: 16,123, beginning 2025-10-08. Three expanding whole-date validation
blocks use development records only; each encoder and model is fitted anew.
Selection uses pooled validation MAE (weighted by readings), with deterministic
alphabetical tie-breaking. No tuning search was performed. The holdout's earlier
baseline results were already inspected in Issue #11; it is not an untouched
test set. Holdout results do not change the selected model or hyperparameters.

| Model | Validation MAE pp | Holdout MAE pp | Holdout near-full MAE pp |
| --- | ---: | ---: | ---: |
| Historical average | 20.018 | 26.382 | 16.314 |
| Linear, original | 19.917 | 25.760 | 18.336 |
| Ridge, original | 19.965 | 25.756 | 18.366 |
| **Ridge, engineered** | **19.209** | **25.038** | 17.829 |
| Random Forest, engineered | 21.666 | 27.800 | 17.718 |
| Gradient boosting, engineered | 22.426 | 28.163 | 19.903 |

Ridge regularizes sparse indicators (alpha=10). Random Forest tests nonlinear
interactions with 60 trees, depth 12 and minimum leaf 10. Gradient boosting tests
additive tree effects with 60 depth-3 stages and minimum leaf 10. Random seed is
42. These are modest fixed starting settings, not extensively optimized models.

Features add joint exact parking-group identity and weekday/time indicators.
The first captures stall-group differences beyond independent label effects;
the second captures different daily demand shapes. Ridge's controlled feature
comparison improves validation MAE by 0.755 pp and holdout MAE by 0.718 pp.
No counts, capacities, target-derived statistics, provenance or quality flags
enter features. Encoding uses training rows only; unseen indicators are ignored.

| Holdout subset | Readings | Historical MAE pp | Selected Ridge MAE pp |
| --- | ---: | ---: | ---: |
| Exact parking group has training history | 11,665 | 21.047 | 20.666 |
| No exact parking-group history | 4,458 | 40.341 | 36.477 |

The selected model improves overall holdout MAE by 1.345 pp. Historical average
remains better near full (actual availability <=10%): 16.314 versus 17.829 pp,
and also on near-full rows with matching history (13.729 versus 15.967 pp).
All models are scored on identical rows, including unseen groups for research.
Serving conservatively abstains on unseen groups despite these extrapolation
scores; they are not estimates that will silently reach recommendations.
`metrics.csv` includes raw/clipped errors, out-of-range diagnostics, near-full
counts and coverage subsets for every split. `predictions.csv` retains record
IDs for error analysis. Serving artifacts are refitted on all records only
after frozen evaluation; these metrics describe the earlier evaluation fits.

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

## Limitations and coordination

Historical observations concentrate near quarter starts and weekdays, at 08:00,
10:00, 12:00 and 14:00. Results do not certify live availability, current parking
allocations, permit eligibility or later-quarter accuracy. Model errors are
substantial, particularly for groups without history. Sparse history is not
silently merged across restrictions. Daira and Dylan should confirm the ready
artifact path, startup error handling and abstention policy in their integration.
No teammate agreement is claimed; this branch provides the concrete compatible
interface and testable handoff without posting messages on their behalf.
