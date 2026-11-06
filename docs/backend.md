# Local FastAPI integration — Issue #19

The API connects the website to the shared registry, historical-average baseline,
and Dylan's eligibility/ranking modules. No notebook, downloader, or dataset
builder runs when a request arrives. Predictions are historical estimates, not
live availability or a guaranteed space.

## Start the backend

From the repository root, activate your existing environment and install the
recorded dependencies:

```bash
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn src.api.main:app --reload
```

For a new environment, first run `python3 -m venv .venv` (see the supported
setup below). On Windows use `py -m venv .venv` and `.venv\Scripts\Activate.ps1`,
or invoke `.venv\Scripts\python.exe` directly if activation is blocked.

### Supported Python setup

Use **Python 3.11 or newer built with OpenSSL** (3.12 matches AWS Lambda; 3.13
also works). Two things depend on it:

- **Routes.** The public OSRM servers used by default accept TLS 1.3 only. The
  macOS system/Xcode `python3` (3.9 with LibreSSL 2.8.3) has no TLS 1.3. The
  backend detects this at startup, logs a warning that names the SSL library,
  and turns routes off (`/routes` answers 503) instead of failing every request.
  Recommendations keep straight-line walking times.
- **Saved models.** Issue #18 artifacts record the exact Python, numpy, pandas,
  scikit-learn, scipy and joblib versions they were trained with, and
  `create_saved_app` refuses to start with any other versions. After creating a
  new environment or changing Python, regenerate them.

On macOS: `brew install python@3.12` (or `python@3.13`). Then, from the
repository root:

```bash
python3.12 -m venv .venv            # or python3.13
source .venv/bin/activate
python -m pip install -r requirements.txt
python -c "import ssl, sys; print(sys.version.split()[0], ssl.OPENSSL_VERSION, ssl.HAS_TLSv1_3)"
# expect 3.11 or newer, "OpenSSL 3...", True

# Regenerate the saved model artifacts for this environment
python -m src.train_availability     # needs data/processed/pipeline/analysis_dataset.csv
python -m uvicorn src.api.saved_model:create_saved_app --factory
```

If the dataset is missing, build it first (`python -m src.download_qpass`,
`python -m src.download_inventory`, `python -m src.build_dataset`). Old
artifacts in `models/issue18/` are overwritten; they are gitignored and never
shared between machines.

Open http://127.0.0.1:8000/docs. Try GET `/health`, GET `/locations`, then POST
`/recommendations` using [the request example](examples/backend/recommendation_request.json).
Stop the server with Ctrl+C.

The registry is `config/locations.json`. The baseline uses the existing
`data/processed/pipeline/analysis_dataset.csv`. If the dataset is not available,
follow `docs/pipeline.md` to build it separately; do not rebuild it for API calls.
Health and the real registry still work when only prediction resources are
missing. Startup logs explain missing, unreadable or invalid resources. Fix them
and restart the server. No API keys are needed.

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/locations
curl -X POST http://127.0.0.1:8000/recommendations -H 'Content-Type: application/json' --data-binary @docs/examples/backend/recommendation_request.json
```

## How the connection works

```text
Website form
  → HTTP POST with JSON (destination, arrival_time, permit_type)
  → FastAPI/Pydantic validate inputs
  → cached Recommender
      → AvailabilityEstimator attaches historical estimates
      → eligibility and ranking choose first and distinct backup
  → RecommendationResponse serialized to JSON
  → website client displays cards, explanations and map markers
```

- `src/api/main.py` creates the app and uses a FastAPI lifespan to load resources
  once per server process, before requests. Importing the module does not read
  the dataset. Shutdown releases the references. Restart to reload changed files.
- The CSV stores historical survey readings; it is not itself a forecast for the
  user's arrival. `load_analysis_dataset` validates it, then the existing
  `Recommender` prepares the `HistoricalAverage` once. No per-request fitting,
  CSV reading, notebook execution, or dataset rebuilding occurs.
- `src/api/locations.py` converts the validated shared registry into the catalog.
- Endpoint handlers only pass validated arguments to `src/recommender.py` and
  serialize its result. `src/availability.py`, `src/eligibility.py` and
  `src/ranking.py` own estimation and parking decisions.
- To use the reviewed Issue #18 artifact, run
  `python -m uvicorn src.api.saved_model:create_saved_app --factory` after
  `python -m src.train_availability`. The factory loads the checked v2 artifact,
  uses its `survey_times` metadata and shared basis descriptions, and passes
  `AvailabilityEstimator` to `create_app(estimator=...)` without fitting it.
  Exact training dependency versions are required; missing/incompatible artifacts
  stop saved-model startup with an error instead of a silent model substitution.
  The normal `src.api.main:app` entrypoint retains its original fitted baseline.
  The selected saved artifact now uses historical averages, selected on requests
  the service supports; unseen groups remain NaN. Full Python wiring, coverage
  rules and regression wording are in `docs/recommendations_handoff.md` and
  `docs/issue18_predictions.md`.

FastAPI's lifespan pattern is described in its
[official documentation](https://fastapi.tiangolo.com/advanced/events/).

## GET /locations

Returns `schema_version`, `data_status: "verified"`, `locations` and `limitations`.
Each location has `location_id`, `name`, and `coordinates`. IDs come from
`config/locations.json` (for example `gilman-ps` and `p406`), never array positions
or newly generated slugs. Fixture IDs such as `sample-parking-a` are retired from
actual endpoint data.

Only `registry_status == "supported"` entries are returned. Restricted, unresolved
and excluded entries stay in the registry for audit and are omitted from this
catalog and recommendation eligibility. Approximate or missing coordinates are
JSON null; only verified pins are published. The envelope's `verified` status
identifies the registry-backed catalog, not verified current use or eligibility.
A listed location may lack current survey groups and may not be recommended.
Predictions retain facility/category/subtype/level keys; the registry maps those
facilities to shared location IDs without pooling restricted parking groups.

If the registry cannot be loaded/validated, this endpoint returns HTTP 503 with
`detail`; it never silently substitutes fictional locations.

## POST /recommendations request

| Field | Required? | Meaning |
| --- | --- | --- |
| `destination` | Yes | Object with nonblank `name` and optional `coordinates` |
| `arrival_time` | Yes | ISO 8601 date and time containing `T` |
| `permit_type` | Yes | A, B, S, SR, D or V; V is the pay-station visitor permit |
| `starting_location` | No | Same shape as destination; accepted but not used yet |

Unknown fields, unsupported permits, blank names and invalid coordinate pairs
return 422. Names/permit text are trimmed and limited to 200 characters. Coordinates
are complete numeric WGS84 `latitude`/`longitude` pairs, within [-90,90] and
[-180,180]. Nonfinite values are rejected. User coordinates are input, not a
verification of catalog pins. Destination name is display text, not geocoded.
Null destination coordinates are allowed: walking time is unavailable and the
recommender explains that ranking uses availability alone. A supplied starting
location adds an explicit limitation because it does not affect ranking; driving
and walking routes come from `POST /routes` (`docs/routing.md`).

Arrival is normalized to `America/Los_Angeles`, with daylight saving. An offset
or `Z` identifies an instant and is converted to UCSD time. No offset means UCSD
local wall time, regardless of the browser's timezone. Do not append `Z` to a
local wall time. Nonexistent spring times are rejected. Repeated autumn times
need an explicit offset: `2026-11-01T01:30:00-07:00` and the `-08:00` version are
different instants. The website currently sends a naive local datetime; for the
ambiguous hour it will receive a clear 422 until an offset is provided.

Eligibility checks arrival only, not the whole stay. The holiday/quarter calendar
has a finite verified range and the recommender labels requests outside it.
Nearest survey times and broader baseline fallbacks are explained in the returned
limitations. Do not relabel those estimates as live parking availability.

## Responses and unavailable values

| HTTP / status | Meaning |
| --- | --- |
| 200 / `ready` | A first choice exists; distinct backup may be null |
| 200 / `no_suitable_location` | Evaluation found no eligible option within the walking limit |
| 200 / `predictions_unavailable` | Eligible options exist but none has an estimate |
| 422 | Invalid trip input; FastAPI `detail` identifies the error |
| 503 | Dataset, registry or estimator unavailable/invalid; `detail` explains service unavailability |

Neither empty result nor service unavailability means all parking is full.
`not_implemented` remains a legacy accepted schema state for compatibility; the
connected endpoint does not emit it.

Responses include `schema_version`, `is_example: false`, normalized `arrival_time`,
`time_zone`, `first_choice`, `backup_choice`, `explanation`, and `limitations`.
Each choice has a registry location, `estimated_available_fraction` (0–1),
`estimated_walking_minutes` (minutes or null), and its explanation. Walking is a
straight-line approximation, not a route. Missing backup and unknown coordinates
remain null; the website must not turn missing values into zero. Unknown estimates
are not replaced by a synthetic prediction. The baseline does use its documented
historical fallback averages and labels their basis.

All files under `docs/examples/backend/` are static developer examples, not
recorded model outputs. Responses in those files have `is_example: true`; their
null estimates and layout-only choices are intentional. They are never loaded by
runtime code. See ready, no-suitable, and predictions-unavailable examples there.

## Connect Dylan's website locally

`frontend/` is a synced copy of Dylan's website. Do not edit its files here.
The existing client already implements POST, result cards and error/empty states.
From a second terminal, install its recorded dependencies if needed and start in
API mode:

```bash
cd frontend
npm ci
VITE_RECOMMENDATION_SOURCE=api npm run dev
```

On PowerShell set `$env:VITE_RECOMMENDATION_SOURCE="api"` before `npm run dev`.
The default backend is `http://127.0.0.1:8000`. To override on macOS/Linux without
editing any environment file:

```bash
VITE_RECOMMENDATION_SOURCE=api VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Open http://localhost:3000. The explicit CORS allowlist covers localhost and
127.0.0.1 on ports 3000 and 5173, GET/POST, and Content-Type. Deployed sites
(for example the Amplify URL) are added with `PARKSMART_CORS_ORIGINS`, a
comma-separated list of exact origins. API mode does not fall
back to sample recommendations. An HTTP 503 currently produces the website's
service-error message; evaluated unavailable estimates use its empty state.
Without the API flag the prototype still uses labeled samples.

For local verification, select a destination, a supported permit and a survey-supported
arrival (for example Tue Nov 3, 2026 at 10 AM). Check browser DevTools Network:
POST `/recommendations` should return 200 with `is_example: false`. Cards should
match the returned first/backup IDs and estimates, and map markers should match
those IDs when pins exist. Test a single result, invalid input, unavailable
predictions and no eligible options; never interpret an empty response as full.
Use the automated fixture tests for states the current real baseline does not
naturally produce. Daira's local browser result is recorded in
`docs/api_proposal.md`; Dylan can review or reproduce it from the PR.

## Tests and coordination

```bash
MPLBACKEND=Agg python -m pytest tests/test_api.py tests/test_api_schemas.py tests/test_recommender.py tests/test_ranking.py tests/test_eligibility.py tests/test_availability.py tests/test_ucsd_calendar.py -q
MPLBACKEND=Agg python -m pytest -q
```

API tests use generated survey CSVs and the shared registry. Their estimates are
synthetic test expectations, not published real predictions. The app factory lets
tests supply temporary dataset/registry paths and a ready estimator. Tests cover
startup loading once, resource failures, 422s, result states, no backup, shared IDs,
CORS including errors, nulls and JSON examples.

The real-data/browser walkthrough must be verified locally; passing fixture tests
does not establish that outcome. Daira's local verification and full-suite result
are recorded in `docs/api_proposal.md`. Some full-suite tests
read local data or website data files that restricted agent environments cannot
access. Do not bypass those restrictions. Run the DS3 review instructions in
`docs/codeReviewer.md` before requesting review; keep `code_review.md` local.
