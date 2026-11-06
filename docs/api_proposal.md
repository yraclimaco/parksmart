# API integration contract — Issue #19

Issue #26 update (2026-11-05): configured saved serving now uses the approved
`historical_average` artifact with Vivaan's exact support policy. Local file
paths and optional private S3 bundle are configurable; GET `/readiness` exposes
resource readiness/mode without file paths. The baseline is explicit only, never
an automatic substitute for an artifact error. Section 1 local verification is
recorded below; cloud validation and collector integration remain pending. The earlier
Issue #19 result is separate evidence. See `docs/issue26_handoff.md` and `infra/README.md`.
The source-count interface is separately proposed in `docs/parking_status.md`;
no collector or live-count endpoint has been verified in this checkout.

Saved-mode local browser verification (2026-11-05):

- Vivaan's offline preparation selected historical_average; readiness returned
  HTTP 200, catalog_ready/predictions_ready true and prediction_mode saved.
- Geisel/S/Nov 3 at 10 AM returned ready with Pangea and a valid null backup.
- Website at localhost:3000: Podemos/B/Nov 6 at 9 AM showed P302 first choice
  and P304 backup, both cards/markers and historical survey limitations.
  Recommendations and routes requests returned HTTP 200.
- Latest automated verification (2026-11-06): 115 affected checks passed;
  the local full suite passed 901 tests and 39 subtests, with 38
  warnings. DS3 review refreshed. See `docs/issue26_handoff.md` for commands.
  Container/SAM/AWS validation remains pending.
- These results cover local verification; joint website/app testing remains pending.

This implementation follows Dylan's merged Issue #20 handoff. It uses the shared
registry and historical baseline, with an optional saved Issue #18 estimator.
This is the implemented API contract; acceptance by all teammates and a joint
website walkthrough have not been recorded. Record feedback and outcomes below.

| Interface | Contract used by this integration |
| --- | --- |
| Location IDs | Stable IDs from `config/locations.json`, e.g. `gilman-ps` and `p406` |
| Public locations | Supported registry entries only; verified coordinates or null |
| Trip input | `destination`, `arrival_time`, `permit_type`, optional `starting_location` |
| Destination/origin | `name`, optional complete `latitude`/`longitude` coordinates; no geocoding |
| Permits | A, B, S, SR, D, V (pay-station visitor); other values return 422 |
| Time | America/Los_Angeles; naive local or explicit instant normalized to UCSD time; DST ambiguity requires offset |
| Predictions | Facility/category/subtype/level plus weekday, survey time and quarter; returns 0–1 `prediction` or NaN, and `baseline_group` |
| Recommender | `.recommend(permit, arrival, destination=coordinates)`; `.to_api()` returns choices, status, explanation and limitations |
| Result | `ready`, `no_suitable_location`, `predictions_unavailable`; null backup when only one location qualifies |
| Units | Availability fraction 0–1; walking minutes; null for unknown values |
| Routes (Issue #25) | `POST /routes` with `mode` (`driving`/`walking`), `origin`, `destination`; returns GeoJSON `[lon, lat]` `geometry`, meters, miles, minutes, `traffic_aware: false`. Examples: `docs/examples/backend/route_*.json`; details: `docs/routing.md` |

FastAPI loads the registry and existing dataset once at startup. The current
baseline is fitted once, never per request. A ready `AvailabilityEstimator`
wrapping a model loaded with Vivaan's loader can replace it without endpoint
changes. `src.api.saved_model:create_saved_app` loads the version-checked v2
artifact through `src.availability_prediction.load_prediction_service`; its
selected historical baseline abstains on unsupported groups/time/calendar fields.
See `docs/issue18_predictions.md` for the shared selection/support rule and
`src/availability.py` for the arrival adapter interface.

The registry attaches shared IDs to facility/category/subtype/level groups;
restrictions and level distinctions are not flattened. Production pins retain
registry verification rules. `GET /locations` omits restricted, unresolved and
excluded entries and explains this in its limitations. Catalog support is not
proof that the location is currently open or eligible for a user's permit.

Destination coordinates determine walking times: mapped walking routes for the
top locations when routing is available (Issue #25), otherwise straight-line
estimates; the explanation and limitations say which. Destination
name is display-only. Starting location is accepted but unused for ranking, explicitly
reported in response limitations when supplied. Eligibility checks arrival only.
Historical fallback basis, outside-survey-hours requests and calendar limitations
come from the reusable recommender, not endpoint guesses.

Missing/invalid startup resources return 503, not an evaluated empty result.
Eligible groups without estimates return 200 / `predictions_unavailable`.
Evaluation with no eligible option returns 200 / `no_suitable_location`.
Neither means parking is full. `not_implemented` remains a legacy schema state,
but is no longer emitted by the endpoint.

Static JSON responses in `docs/examples/backend/` remain explicitly marked
`is_example: true`; runtime results are `false`. No synthetic fixture estimates
are used as a runtime fallback. See [backend setup and learning guide](backend.md)
for the request/response details and local website commands.

## Coordination and acceptance

- Dylan owns the registry, eligibility/ranking modules and source website.
  His merged `docs/recommendations_handoff.md` supplies the integration interface.
- Vivaan owns saved predictions and reproducible model comparison. The corrected
  selected artifact uses historical averages; exact dependency versions, feature
  mode, survey-time metadata and support labels are stored. The saved-model
  entrypoint returns no estimate for unseen groups, while normal baseline startup
  keeps its original behavior. No joint saved-model website walkthrough is claimed.
- Routes (Issue #25): the website calls `POST /routes`
  twice per selected choice — driving from the user's start to the parking
  location, walking from it to the destination. The app can make the same two
  calls; 503 means routing is off and should be shown as "directions not set up",
  not as an error. Open points are listed at the end of `docs/routing.md`.
- Hanrong's app can use the same HTTP contract. No additional app confirmation
  is recorded here; live-data research is a separate task.
- [x] API integration and generated-fixture endpoint tests implemented.
- [x] Local website tested in API mode with the historical baseline.
- [x] Record the local test and full-suite result below.

Baseline local verification (2026-11-01):

- Used Dylan's merged registry/recommender and the existing historical baseline,
  as requested; no improved-model artifact was required.
- At `localhost:3000` in API mode, searched for Pepper Canyon Hall with B permit
  and arrival November 1, 2026 at 5 PM UCSD time.
- The supplied screenshot shows Lot P671 as first choice, a 68% historical
  estimate, a 9-minute approximate walk, and first/backup map markers. The card
  explains the 2 PM survey fallback and that availability is not live.
- The raw network JSON and backup ID were not captured during this local test.
- Full local suite: `MPLBACKEND=Agg python -m pytest -q` — **683 passed,
  17 warnings in 71.79s**. Automated fixture tests cover invalid requests,
  unavailable predictions, no eligible options and a result without a backup.
