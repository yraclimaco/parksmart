# Local backend and proposed interface contract

Contract version: **0.1, proposed**. Dylan is willing to adapt his frontend;
Hanrong has not started his app and his confirmation is pending. Client
integration has not been verified. See [coordination status](api_proposal.md).
This backend does not depend on QPASS workbooks or
`data/processed/pipeline/`; the integrated dataset can remain under development.

## Start the backend

Run from the repository root using Python 3.9 or newer:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn src.api.main:app --reload
```

On Windows PowerShell use `py -m venv .venv` and
`.venv\Scripts\Activate.ps1` in place of the first two commands. No API keys,
workbooks, database, or model files are required. Stop the server with Ctrl+C.

Open <http://127.0.0.1:8000/docs>. Expand **GET /health**, select **Try it out**,
then **Execute**. Repeat for **GET /locations**. Both should return HTTP 200.
The raw OpenAPI schema is at <http://127.0.0.1:8000/openapi.json>.

From another terminal:

```bash
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/locations
```

Expected health response: `{"status":"ok"}`. It confirms that the process is
running; it does not certify prediction readiness. Only `/health` and
`/locations` are implemented. No recommendation endpoint exists; a request to
`/recommendations` returns HTTP 404, not a recommendation result. Recommendation
input validation is tested directly on the proposed Pydantic models.

## Learn how the pieces fit

An API is an agreement about messages. Both clients send HTTP requests to the
same backend; they do not import the backend's Python functions. A GET reads
information. A POST sends JSON in its request body.

1. `src/api/main.py` creates the FastAPI application. A decorator such as
   `@app.get("/health")` connects an HTTP method and URL to a Python function.
2. `src/api/schemas.py` defines Pydantic models: typed objects that describe the
   fields, reject invalid input, and serialize responses into JSON. FastAPI
   uses these models to generate `/docs` and OpenAPI automatically.
3. `src/api/locations.py` supplies an explicitly fictional development catalog.
   It returns fresh objects, so callers cannot mutate a shared catalog.
4. Recommendation models describe future messages only. No recommendation
   service or algorithm is implemented. Keep future model and ranking logic
   outside endpoint functions.
5. `tests/test_api.py` calls the app in-process using `TestClient`; a server
   does not need to be running for these tests.

To try input validation without adding an endpoint, run this from the root:

```bash
python -c 'from src.api.schemas import RecommendationRequest; print(RecommendationRequest.model_validate_json(open("docs/examples/backend/recommendation_request.json").read()))'
```

Change `permit_type` to an empty string in a local copy of the example and
validate it the same way: Pydantic raises a `ValidationError`. The checked-in
examples should stay valid. `/docs` documents the two working GET endpoints;
the proposed recommendation models are in `src/api/schemas.py` and this guide.

## GET /locations

```json
{
  "schema_version": "0.1",
  "data_status": "sample",
  "locations": [
    {"location_id": "sample-parking-a", "name": "Sample Parking A", "coordinates": null},
    {"location_id": "sample-parking-b", "name": "Sample Parking B", "coordinates": null}
  ],
  "limitations": [
    "Fictional sample locations for interface development only.",
    "Proposed location IDs and fields support Hanrong's app development.",
    "Coordinates and permit eligibility have not been verified.",
    "Catalog is not connected to the processed pipeline dataset."
  ]
}
```

These are fictional fixtures, not a UCSD inventory or evidence of permit
eligibility. All coordinates are unknown. **Every field name and location ID is
proposed, and the backend uses them now to support Hanrong's app development.**
His feedback can inform later changes. The fixture IDs are stable across
calls and restarts, unique, case-sensitive strings. Clients should treat IDs as opaque and
use `name` for display; never generate IDs from array order or display names.

Before replacing fixtures, agree on a persisted canonical location registry
with Dylan. Resolve facility versus level scope and aliases using reviewed
project decisions. Do not turn unreviewed dataset labels directly into IDs.
Keep production IDs stable across renamed display labels; fixture IDs are not
production IDs. Only publish coordinates with reviewed source evidence; store
that evidence with the future registry. No verified coordinates are bundled yet.

## Proposed recommendation input (no endpoint implemented)

See [the example request](examples/backend/recommendation_request.json).
This is development input, not an assertion that its permit can park anywhere.

| Field | JSON type | Rule |
| --- | --- | --- |
| `destination` | object | Required; contains nonblank `name` and optional `coordinates` |
| `arrival_time` | string | Required ISO 8601 date and time containing `T` |
| `permit_type` | string | Required, nonblank; proposed vocabulary pending team review |
| `starting_location` | object or null | Optional; same format as destination |

All names, IDs, and permit strings are trimmed and limited to 200 characters.
Unknown fields are rejected, including misspellings such as `permitType`.
The proposed model accepts any nonblank permit string to avoid inventing an
authoritative permit list. This is syntactic validation, not eligibility
validation. The team must agree on permit codes before real recommendations.
Destination names are user input; there is no geocoder or destination registry.

`coordinates` is either `null` or a complete object with numeric `latitude` and
`longitude` in WGS84 decimal degrees. Latitude must be between -90 and 90;
longitude between -180 and 180. Nonfinite numbers and partial pairs are invalid.
User-supplied coordinates are not automatically verified catalog coordinates.

UCSD local time is **America/Los_Angeles**, including daylight-saving changes.
Prefer an explicit offset: `2026-10-27T09:00:00-07:00`. If the offset is omitted,
the server interprets the value as UCSD local time. An offset or `Z` identifies
an instant and is converted to UCSD local time in the response. Do not append
`Z` to a local wall-clock time: `Z` means UTC. A date alone is invalid. Local
times in the missing spring hour are rejected; repeated autumn times need an
explicit offset. For example, `2026-11-01T01:30:00` is ambiguous, while the
versions with `-07:00` and `-08:00` identify different instants.

## Proposed recommendation response

| Field | Meaning |
| --- | --- |
| `schema_version` | Contract version string, currently `"0.1"` |
| `status` | `ready`, `no_suitable_location`, or `not_implemented` |
| `is_example` | `true` identifies a static UI example, never a real prediction |
| `arrival_time`, `time_zone` | Arrival normalized to UCSD local time with offset, and IANA zone name |
| `first_choice` | Parking choice object, or null |
| `backup_choice` | Different parking choice object, or null |
| `explanation` | Human-readable reason for the overall result |
| `limitations` | Array of relevant limitations, displayed by the client |

A choice contains `location` (the same ID/name/coordinates shape as the catalog),
`estimated_available_fraction`, `estimated_walking_minutes`, and `explanation`.
Fractions are in **0–1**, not 0–100. Walking estimates are nonnegative minutes.
Both estimates can be null independently, including for an otherwise ready
result. An unavailable backup is null; a ready result requires a first choice.
`no_suitable_location` and `not_implemented` require both choices to be null.

Clients should display null estimates as “Unavailable,” never “0%” or “0 min.”
Zero is a known numerical estimate, not a missing-value sentinel. Skip map
markers for null coordinates. No guarantees of parking availability should
appear in the UI.

| Example file | Intended use |
| --- | --- |
| [recommendation_not_implemented.json](examples/backend/recommendation_not_implemented.json) | Static **EXAMPLE ONLY** future unavailable-feature state; no evaluation exists |
| [recommendation_example.json](examples/backend/recommendation_example.json) | Static **EXAMPLE ONLY** two-card layout; fictional choices, null estimates |
| [recommendation_no_suitable.json](examples/backend/recommendation_no_suitable.json) | Static **EXAMPLE ONLY** future empty state |

`not_implemented` means recommendation functionality does not exist, so no
parking evaluation was attempted. It is a proposed result state, not an actual
HTTP response from this backend. In the future,
`no_suitable_location` will mean evaluation found no defensible recommendation;
it must not be presented as proof that all locations are full. Static examples
stay under `docs/examples/backend/` and are never loaded by endpoint code.
No numerical estimates have been fabricated for these examples.

## Website and iOS connection

Base URL locally: `http://127.0.0.1:8000`. A React app can start with:

```javascript
const apiBaseUrl = "http://127.0.0.1:8000";
const response = await fetch(`${apiBaseUrl}/locations`);
if (!response.ok) throw new Error(`API error: ${response.status}`);
const catalog = await response.json();
// Show a sample-data badge when catalog.data_status === "sample".
// Key location cards by location_id; display name as the label.
```

Only connect the two GET endpoints now. The JSON recommendation examples are
static UI fixtures and must display an example badge; do not POST them to the
current backend. A future recommendation endpoint may accept JSON, but its
route and error format are not part of this implementation. Handle offline
and network failures when calling either GET endpoint.

The local CORS allowlist includes `http://localhost:3000`,
`http://127.0.0.1:3000`, `http://localhost:5173`, and
`http://127.0.0.1:5173`. It permits GET with Content-Type. If the web
team uses another origin, update the explicit list and its tests. CORS is a
browser access rule, not authentication. Native iOS clients use the same JSON
contract without browser CORS. Match the snake_case JSON keys in Swift using
CodingKeys or a consistent decoding strategy.

For the iOS simulator on this Mac, try the same base URL. A physical phone's
`127.0.0.1` refers to the phone itself; physical-device networking and transport
settings are separate setup work. This local task does not configure deployment,
authentication, routing services, or live parking integrations.

## Team handoff: Daira, Dylan, and Hanrong

Share [the proposal](api_proposal.md), the example files, and `/docs` with both
teammates. The contract remains proposed while feedback is pending. Dylan's
willingness to adapt and Hanrong's app status are recorded in the proposal.

The setup instructions must let another teammate start the backend and call
both endpoints. A teammate walkthrough is recommended validation, not a separate
approval requirement. During interface integration, confirm fields, permit
codes, units, UCSD time, null handling, and sample/empty states. Record agreed
changes in the proposal. Review production IDs and facility/level scope before
replacing the sample catalog; that registry is future work.

## Tests and review

```bash
python -m pytest tests/test_api.py tests/test_api_schemas.py -q
python -m pytest -q
```

Tests cover liveness, sample metadata and stable fixture IDs, OpenAPI/docs,
browser CORS, absence of a recommendation endpoint, required model fields,
invalid inputs, coordinate and estimate bounds, time-zone/DST behavior, result
consistency, and JSON example validity.
Backend tests do not read the pipeline dataset. Some existing repository tests
depend on local workbooks; do not bypass access restrictions to run those.

Before requesting Yra's PR review, refresh the branch from main, run the full
suite, and run the mentor's DS3 code-review instructions in
`docs/codeReviewer.md` against main. Keep the generated `code_review.md` local.
The PR description must include the real `Closes #<issue-number>`, testing
results, any blocked checks, and the AGENTS.md update. Only the mentor merges.
