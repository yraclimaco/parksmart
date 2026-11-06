# Issue #26 — saved-artifact demo and deployment preparation

Local verification (2026-11-06): **115 affected tests passed**. The full suite
then passed **901 tests and 39 subtests**, with 38 warnings, in 57.76s. DS3 review
is complete. Docker/SAM/AWS validation and parking-feed integration remain pending.

## Local demo scope

The website uses the existing recommender and saved-model v2 loader. The approved
estimator is **historical_average**, selected by the supported-validation
comparison documented in `docs/issue18_predictions.md`.

The saved service requires an observed exact facility/category/subtype/level
parking group and observed survey time/weekday/quarter. Unsupported fields keep
NaN and become `predictions_unavailable` after eligibility/ranking. Blank quarter
uses the documented historical fallback. Supported sparse matches can use the
labeled level_2/level_3 fallback; unseen groups do not receive a campus-wide
replacement. This differs from the older startup-fitted baseline demo.

## Local demo observations — 2026-11-05

- The local artifact was reproduced with `python -m src.train_availability`.
  Selection returned
  historical_average in Python 3.12.16; saved readiness returned HTTP 200 with
  catalog_ready/predictions_ready true and prediction_mode saved.
- The local website showed P302 first choice and P304 backup for Podemos,
  B permit, Nov 6 at 9 AM UCSD time. Cards showed about 68%/59% historical
  availability and 14/18 minute walks; first/backup markers were visible.
  Backend logs showed recommendations and routes both returning HTTP 200.
- Prepared configurable saved startup, readiness, private S3 bundle loading and
  Lambda/SAM deployment files. No AWS calls or deployment have been performed.
- No parking-feed collector/adapter is present in the merged source inspected
  for this issue. The feed contract is proposed in `docs/parking_status.md`;
  a real endpoint waits for the collector and reviewed mappings.
- Current automated verification is summarized at the top of this document.
  Joint website/app verification, AWS deployment and collector integration remain
  pending.

## Start the local demo

Activate any virtual environment whose Python and dependency versions match the
trusted artifact; its folder name does not matter. For the Lambda Python 3.12
image, generate the artifact in the compatible serving environment.
Stop an existing server with Ctrl+C before changing the serving entrypoint.
From the repository root:

```bash
source .venv/bin/activate  # Example name; use your actual environment path.
python -m pip install -r requirements.txt
```

If there is no compatible local artifact, Vivaan's existing offline reproduction
command creates the approved saved service and metadata:

```bash
python -m src.train_availability
```

This uses the existing processed dataset, runs the documented comparison and
writes local model artifacts. It does not belong in API startup or a request.
Keep the reviewed model-selection policy. If a compatible saved artifact is
unavailable, the explicit baseline mode below can be used for a labeled demo.
Only load trusted team artifacts; pickle files can execute code. Dependency
versions, including the Python patch version, must match their training runtime.
Do not edit artifact metadata to bypass the compatibility checks.

Start saved mode (default):

```bash
python -m uvicorn src.api.saved_model:create_configured_app --factory --reload
```

Check http://127.0.0.1:8000/readiness. Expected: HTTP 200 with
`prediction_mode: "saved"`, `catalog_ready: true`, `predictions_ready: true`.
GET `/health` alone is not evidence that the artifact loaded. Missing/corrupt,
unapproved or incompatible artifacts give readiness/recommendations 503; no
baseline is fitted in their place. Startup logs have the diagnostic details.
Restart after repairing files. The older strict
`src.api.saved_model:create_saved_app --factory` entrypoint remains available
and fails factory creation if its trusted artifact cannot load.

In a second terminal:

```bash
cd frontend
# npm ci only if the existing dependencies are not installed
VITE_RECOMMENDATION_SOURCE=api npm run dev
```

Open localhost:3000. Use Geisel Library or another real destination, S permit,
and Tuesday November 3, 2026 at 10 AM UCSD time as a first supported request.
Check the Network panel for POST `/recommendations`, HTTP 200, `is_example: false`,
and distinct first/backup IDs when two options qualify. Check both cards and map
markers. A null backup is valid; unsupported estimates must not become sample
cards or zeros. Pick a supported weekday because the saved service abstains on
weekdays not represented in training. Record actual outcomes, not expected ones,
in `docs/api_proposal.md`. The app uses the same base URL and snake_case JSON.
A physical phone needs the laptop's reachable LAN address, not its own localhost;
coordinate app transport/network configuration with Hanrong rather than changing
backend field names or adding broad CORS origins speculatively.

## Keep the working baseline demo

Stop the saved server first; both commands otherwise compete for port 8000.
The old, explicit baseline entrypoint still works:

```bash
python -m uvicorn src.api.main:app --reload
```

Or choose baseline through configuration:

```bash
PARKSMART_MODEL_MODE=baseline python -m uvicorn src.api.saved_model:create_configured_app --factory
```

Readiness reports `baseline`, not `saved`. This entrypoint fits the old baseline
once at startup and retains its older labeled fallback behavior. It is not
validation that the approved artifact loaded. Switching modes is an operator
choice, never an automatic response to missing saved resources.

## Configuration

| Variable | Default / meaning |
| --- | --- |
| `PARKSMART_MODEL_MODE` | `saved`; `baseline` must be explicit in configured serving |
| `PARKSMART_APPROVED_MODEL` | `historical_average`; change only after a reviewed model decision |
| `PARKSMART_ARTIFACT_PATH` | `models/issue18/selected.pkl` |
| `PARKSMART_DATASET_PATH` | `data/processed/pipeline/analysis_dataset.csv` |
| `PARKSMART_REGISTRY_PATH` | `config/locations.json` |
| `PARKSMART_BUNDLE_MANIFEST` | Optional trusted `s3://bucket/release-prefix/manifest.json`; all three file paths come from this bundle |
| `PARKSMART_CACHE_DIR` | `/tmp/parksmart-serving` for verified bundle files |
| `PARKSMART_CORS_ORIGINS` | Existing exact-origin allowlist extension; local origins remain allowed |

Relative local paths resolve against the project root. Configuration reads the
process environment; it never reads .env files automatically. File paths are
nonsecret, but actual datasets, artifacts, credentials and private source
snapshots remain local/private. No client can supply a pickle path or S3 URI.
Routing configuration and credential handling remain in `docs/routing.md`.

## Verification commands

The completed local results are recorded at the top. Use these commands for
future regression checks:

```bash
MPLBACKEND=Agg python -m pytest tests/test_prepare_serving_bundle.py tests/test_serving_configuration.py tests/test_serving_bundle.py tests/test_lambda_handler.py tests/test_api.py tests/test_api_schemas.py tests/test_availability_prediction.py tests/test_routing.py -q
MPLBACKEND=Agg python -m pytest -q
```

Tests cover load once/no training, real module orchestration on generated survey
fixtures, unsupported requests, no backup, artifact errors, explicit baseline,
checksummed S3 cache behavior, and repeated Lambda invocations. No real AWS
service is used by the fixture tests. Check artifact readiness and website/app
results with real local files separately. Run the DS3 review instructions in
`docs/codeReviewer.md` before requesting PR review; keep the report local.
Inspect staged files for unrelated changes, private data and credentials.

## Demo checklist

Show saved-mode readiness, one supported search, first-choice and backup cards
and markers, and the historical-data limitations. Keep a recorded response for
reference if network-dependent routing is unavailable. Parking-feed integration
and AWS deployment remain pending; the local saved-model workflow is verified.
