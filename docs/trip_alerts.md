# Shared trip alerts — Issue #35

`POST /trip-alerts` supplies informational forecast weather and published UCSD
construction notices for an arrival and selected parking point/destination.
Website and iOS clients use the same endpoint. Call it separately from
`POST /recommendations`; alert failures do not prevent a parking search. Alerts
never change predicted availability, permit eligibility, ranking or routing.
Nearby construction is not proof of whole-lot closure or route avoidance.

The proposed contract was shared with Dylan, Hanrong and Daira in the
[early Issue #35 handoff](https://github.com/yraclimaco/parksmart/issues/35#issuecomment-6874120003).
This document describes the implemented `schema_version: "0.1"` contract. The
source-specific matching evidence and limitations are in
[weather_source.md](weather_source.md) and
[construction_source.md](construction_source.md).

## Run and request

Use the existing backend environment and start from the repository root:

```bash
python -m uvicorn src.api.saved_model:create_configured_app --factory
```

The configured entrypoint preserves the approved saved historical model and its
exact-version requirements. `python -m uvicorn src.api.main:app` remains the
explicit startup-fitted baseline entrypoint. Neither alert requests nor this
integration train or replace a prediction artifact. Alert providers and their
cache/pool are created once during application lifespan, not on each request.

`PARKSMART_TRIP_ALERTS_ENABLED` defaults to `true`. Set it to `false` to disable
external alert calls; both sources explicitly report `unavailable`. No paid API
key, new account or AWS resource is required by the local integration. Keep
initial use low traffic and review the provider terms before deployment.

```bash
curl --max-time 10 --request POST http://127.0.0.1:8000/trip-alerts \
  --header "Content-Type: application/json" \
  --data @docs/examples/trip_alerts_request.json
```

The checked-in examples are labeled examples, not live source observations:

- [Request](examples/trip_alerts_request.json)
- [Example response](examples/trip_alerts_response.json)
- [Unavailable-source response](examples/trip_alerts_unavailable.json)

Choose a new aware arrival near the current time when testing live forecasts.
A dated example can become past/out of range without indicating an API failure.

## Request contract

| Field | Meaning |
| --- | --- |
| `arrival_time` | Required ISO datetime. Explicit offsets are recommended. Offset-free values use America/Los_Angeles; nonexistent spring-DST times are rejected and repeated fall-DST hours need an offset. |
| `parking_location_id` | Optional stable supported ID from `GET /locations`, for example `gilman-ps`. No inferred facility-name mapping. |
| `destination` | Optional `{name, coordinates: {latitude, longitude}}`. Coordinates are complete WGS84 degrees. A name alone is not geocoded. |

Supply a parking ID, destination coordinates, or both. Unknown request fields,
invalid coordinates and requests with neither location are rejected with 422.
An unknown/unsupported parking ID is 404; an unavailable catalog is 503 when a
parking ID must be resolved. A supported parking ID without verified coordinates
is retained as a limitation rather than assigned invented coordinates.
Destination-only coordinate requests do not require a ready prediction model or
catalog. Names/IDs are limited to 200 characters.

```json
{
  "arrival_time": "2026-11-18T10:00:00-08:00",
  "parking_location_id": "gilman-ps",
  "destination": {
    "name": "Geisel Library",
    "coordinates": {"latitude": 32.8811, "longitude": -117.2376}
  }
}
```

At most two points are matched: the registry parking point and the supplied
destination. Forecast weather uses parking coordinates when present, otherwise
destination coordinates. Construction checks both points independently; it does
not inspect a driving/walking route or geocode free text.

## Response contract

The envelope contains `schema_version`, `is_example: false`, normalized aware
`arrival_time`, `time_zone: "America/Los_Angeles"`, independent `weather` and
`construction` objects, and overall `limitations`. Source failures normally
return HTTP 200 with explicit source states. A successful HTTP response is not
proof that both upstream sources are available.

Each source result has these fields:

| Field | Meaning |
| --- | --- |
| `status` | One of the states below; never infer success from an empty alert list. |
| `source_name`, `source_url` | Provider attribution/link. Display them with the information. |
| `last_checked_at` | Last successful retrieval of the actual cached data, or null. It is not a measurement time, publication time or project update time. |
| `last_attempt_at` | Most recent source refresh attempt, including failures, or null. A failed refresh does not advance `last_checked_at`. |
| `alerts` | Zero or more normalized notices/suggestions. |
| `forecast` | Weather-only selected hourly values, or null. Construction uses null. |
| `limitations` | Source coverage, timing, matching, missing-field or stale qualifications to retain in clients. |

| Status | Client meaning |
| --- | --- |
| `available` | Usable fresh source information. Ordinary weather may have a forecast but no suggestion alerts. |
| `no_relevant` | A fresh construction snapshot was checked and no notices matched under the documented rules; this is not proof of no construction. |
| `partial` | Some matching/forecast information is usable, but fields or source coverage are incomplete. Show its limitations. |
| `stale` | An older usable snapshot survived a failed/in-progress refresh. Show the old retrieval time and stale label, even if its alert list is empty. |
| `unavailable` | No usable source information, disabled provider or exhausted/busy source capacity. Do not display an all-clear message. |
| `out_of_range` | The arrival cannot be served by the actual forecast timeline. No historical/nearest-day substitution. |
| `missing_location` | No usable coordinates for this source; no invented location match. |

Every `TripAlert` contains `alert_id`, `alert_type` (`weather` or `construction`),
plain-text `message` (at most 600 characters), one/two `locations`, nullable
`relevant_from`/`relevant_until`, `source_name`, `source_url`, `last_checked_at`,
`match_basis` and `limitations`. A location includes role (`parking` or
`destination`), name, latitude, longitude and optional registry `location_id`.
Render source text as text, not HTML. Preserve timestamps with their offsets.

`forecast` contains `location`, `forecast_time`, `period_start`, `period_end`,
nullable `temperature_c`, `apparent_temperature_c`,
`precipitation_probability_percent` (0–100), `precipitation_mm`, `wind_speed_kmh`
and `weather_code`. Unknown fields remain null, not zero. Temperature/wind/code
refer to the selected whole-hour timestamp; precipitation describes the
preceding hour. Weather suggestions are ParkSmart walking-comfort rules, not
official weather warnings. Keep visible Open-Meteo attribution and the linked
licence described in [weather_source.md](weather_source.md).

Construction uses published approved geometry/dates, a 200 m advisory buffer,
exact notice IDs for grouping and verified WGS84 coordinates. Public-impact date
pairs take priority; a complete broader alert-date pair is a labeled fallback.
Midnight end dates conservatively include that UCSD-local day. Unknown scope,
dates, geometry or status do not silently become fresh no-relevant results.
These are published notices with unverified update frequency/completeness.

## Refreshes and bounded work

| Source | Fresh TTL | Maximum total age of explicitly stale data |
| --- | ---: | ---: |
| Weather | 900 seconds | 3,600 seconds |
| Construction | 600 seconds | 86,400 seconds |

The cache is an in-memory LRU with at most 64 entries per process. Concurrent
refreshes for one key share existing/stale state rather than multiplying calls.
Failed refreshes back off for 30 seconds. Cache reads never refresh retrieval
timestamps; stale-age limits are measured from the original successful fetch.
The cache is not shared across Lambda execution environments/processes and is
not a global provider-quota guarantee.

Source HTTP refreshes have a four-second budget, bounded socket waits and a
2 MiB response cap; redirects and retries are disabled. Construction pagination
shares its budget across all layers/pages. The service permits at most two
source jobs per process and a shared 6.5-second alert response budget. Saturation
returns explicit unavailable states rather than an unbounded queue. Already
started work can finish within the underlying transport bounds after the
response deadline. Recommendations use a separate handler and need no alert
request to finish.

## Opt-in HTTP smoke check and Daira handoff

```bash
python -m scripts.check_trip_alerts --base-url http://127.0.0.1:8000
python -m scripts.check_trip_alerts --base-url https://<Daira-backend-base-url> --arrival 2026-11-18T10:00:00-08:00 --parking-location-id gilman-ps
```

The target is required. Only HTTP loopback or HTTPS URLs are accepted; URL
credentials, query strings and fragments are rejected. An existing deployment
path prefix is preserved. The script requests only `GET /health`,
`GET /readiness` and `POST /trip-alerts`, disables redirects/proxy environment
lookup, and validates the shared response models. The default arrival is current
UTC plus one hour; `--arrival` must include an offset. No token is accepted on
the command line or logged. If deployment authentication is required, obtain
Daira's access instructions before extending the smoke tool.

It uses one-second connect waits, at most eight-second read waits, a per-request
budget of nine seconds, an approximately 30-second overall budget and bounded
response bytes. It prints compact check/source summaries, not full source data.
Exit 0 means the API contract checks passed. A valid readiness 503 is reported
separately as `backend_predictions_ready: false`; valid source failures can also
pass the contract check. `both_sources_report_fresh` summarizes backend-reported
fresh cache states (`available`, `no_relevant` or `partial`) with an aware
retrieval timestamp. It does not establish completeness or a new upstream
refresh. The `live_upstream_refresh_verified` and
`aws_hosting_verified` remain false: cached responses and an HTTPS URL do not
independently establish a new upstream refresh or AWS hosting.

Daira's hosted base URL and access instructions were not present in checked
issues, PR discussions or current repository documentation. AWS integration
verification remains a teammate dependency; no hosted success, deployment,
resource creation or paid usage is claimed. Once she supplies the endpoint,
run the explicit smoke command, retain its flags/timestamps and check a real
website/iOS request. Confirm HTTPS/CORS, external egress, source terms/traffic,
per-process cache behavior and artifact compatibility before deployment.

PR #31's three review findings were addressed in `60b14e64`; the PR remains
awaiting Yra's approval/merge. Its approved historical method stays unchanged.
Events are deferred: the official
[widget guide](https://calendarhelp.ucsd.edu/training/event-widgets.html) describes
display filters, but precise machine-readable event time/location semantics
were not established. Weather and construction remain the required scope.

## Local verification and remaining dependencies

On November 14, a real local saved-model server returned HTTP 200 for health,
readiness and the shared alert contract. Weather was `available` with a forecast;
construction was correctly `unavailable` when feature queries timed out. The
approved historical artifact remained ready and a subsequent November 18,
10 AM S-permit recommendation returned distinct first/backup locations with
`is_example: false`. No artifact was changed or trained during this check.

This was a local check, not AWS-hosted verification. The source coverage
inspection is documented separately from current feature-query availability in
`construction_source.md`; the current timeout is not evidence of no notices.
Daira's actual hosted URL/access and a successful current construction feature
query remain external verification dependencies. Neither is represented as a
completed cloud/source check.

Final offline verification passed **1,027 tests and 39 subtests** (38 warnings)
on Windows/Python 3.12.10. It includes provider date/location matching, expired
and incomplete notices, UTC/DST handling, stale cache provenance and backoff,
bounded concurrency/deadlines, HTTP and Lambda-adapter contracts, and unchanged
recommendations during source/client failures. The DS3 review's smoke-tool DST
and misleading-completeness findings were fixed and regression-tested; the
review report stays local and uncommitted.

The early contract and implementation/dependency checkpoint were shared with
Dylan, Hanrong and Daira in [the issue thread](https://github.com/yraclimaco/parksmart/issues/35#issuecomment-6874624866).

Offline smoke-tool tests use `httpx.MockTransport` and never contact a server:

```bash
python -m pytest tests/test_check_trip_alerts.py -q
```
