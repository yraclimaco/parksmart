# Driving and walking routes — Issue #25

The website (and later the mobile app) shows two legs for the selected parking
choice: **driving** from the user's starting point to the parking location, and
**walking** from the parking location to the destination. Both come from the
backend's `POST /routes`, so any provider key stays on the server.

Code: `src/routing.py` (providers, validation, cache) and the endpoint in
`src/api/main.py`. Tests: `python -m pytest tests/test_routing.py -q` (no test
reaches a real provider).

## Quick start for teammates

- **Website / mobile app:** for the selected parking choice, send two requests.
  The first is `mode: "driving"` from the user's start to the parking location's
  registry coordinates (only if a start is known). The second is `mode: "walking"`
  from those coordinates to the destination. Draw `geometry` as a line. Show
  `duration_minutes` and `distance_miles`, the `limitations` and the
  `attribution`. Treat 503 (or a plain 404 `"Not Found"` from an older backend) as
  "directions not set up", not as an error. Copyable JSON:
  `docs/examples/backend/route_request.json` and `route_response.json`. The
  website's client is `frontend/src/api/routes.ts`.
- **Backend / Lambda:** `/routes` is part of the same FastAPI app; see
  [Lambda handoff](#lambda-handoff) for timeouts, internet access, cache and
  provider constraints. `PARKSMART_ROUTING_PROVIDER=none` turns routes off (503).
- **Locally:** nothing to set; just start the backend with Python 3.11+ built
  with OpenSSL (see "Supported Python setup" in `docs/backend.md`).

## Provider choice

| Provider | Driving + walking | Free limits | Key | Notes |
| --- | --- | --- | --- | --- |
| **OpenRouteService** (`ors`, recommended) | yes | 2,000 directions/day, 40/min | free sign-up | OpenStreetMap data; works over TLS 1.2 |
| OSRM on FOSSGIS servers (`osrm`) | yes (one server per mode) | light use only (~1 req/s), no uptime promise | none | Good for development and the pilot, not production |
| Google Routes / Mapbox | yes | need a billing account or card | yes | Not used: the project must not enable paid usage |

ORS limits were checked on its plans page on 2026-11-04; recheck before relying
on them. Neither provider uses live traffic, so every response has
`traffic_aware: false` and travel times are described as typical, never
traffic-aware.

## Configuration

Set environment variables before starting the backend (there is no `.env`
loader; export them in the shell or in the Lambda configuration):

| Variable | Meaning |
| --- | --- |
| `PARKSMART_ROUTING_PROVIDER` | `ors`, `osrm` or `none`. Unset: `ors` if `ORS_API_KEY` is set, otherwise `osrm` on the public FOSSGIS servers, so routes work with no setup. `none` turns routes off. |
| `ORS_API_KEY` | OpenRouteService key. Secret: never commit it, never put it in a `VITE_` variable. |
| `OSRM_DRIVING_URL`, `OSRM_WALKING_URL` | Optional self-hosted OSRM servers; default to `routing.openstreetmap.de`. |

```bash
# Default: public OSRM servers, no key needed
python -m uvicorn src.api.saved_model:create_saved_app --factory

# Optional: OpenRouteService (openrouteservice.org was offline on 2026-11-04)
export ORS_API_KEY=...            # never committed
python -m uvicorn src.api.saved_model:create_saved_app --factory
```

An unknown provider name or `ors` without a key logs a warning and turns routes
off; recommendations and `/health` keep working.

**TLS check:** the FOSSGIS servers accept only TLS 1.3. The macOS system/Xcode
Python 3.9 (LibreSSL 2.8.3) has none. At startup, if the public servers would be
used and `ssl.HAS_TLSv1_3` is false, the backend logs one warning naming the SSL
library and turns routes off (`/routes` answers 503; recommendations keep
straight-line walks). At run time routes are turned off only for a **confirmed**
unsupported setup: an OpenSSL protocol-version reason (`UNSUPPORTED_PROTOCOL`,
`TLSV1_ALERT_PROTOCOL_VERSION`, ...), or a handshake failure on a Python without
TLS 1.3 (`TLS_PROTOCOL_REASONS`, `tls_problem()` in `src/routing.py`). That logs
one warning and recommends Python 3.11+ built with OpenSSL (`docs/backend.md`).
Every other SSL failure is an ordinary provider error (502, or a straight-line
walk) and routing stays on for the next request: a failed certificate check says
"TLS certificate check failed", anything else "TLS connection failed".
Certificates are always verified. OpenRouteService and a self-hosted `http://`
OSRM do not need TLS 1.3.

## Public-server limits and deployment plan

The FOSSGIS servers are a free community service: about **one request a second**,
no uptime promise, no key, and a `User-Agent` that identifies the app (ParkSmart
sends one). ParkSmart respects that limit like this:

- **One shared throttle per process.** Every FOSSGIS request, from
  `/recommendations` walking checks and from `/routes` directions alike, waits
  for a slot in one throttle that starts requests at least 1 s apart
  (`FOSSGIS_MIN_INTERVAL_SECONDS`), across both modes. A request whose slot is
  more than 6 s away fails fast (`/routes` 502, recommendations keep
  straight-line times) instead of queueing.
- **`/routes` cannot crowd out searches.** With a rate-limited provider
  (public FOSSGIS or ORS), directions requests that need the provider start at
  most every 2 s process-wide (`ROUTES_ENDPOINT_MIN_INTERVAL_SECONDS`), so even
  a flood of `/routes` calls leaves at least half of the FOSSGIS slots for
  recommendation walking routes. Cached trips and self-hosted servers are not
  limited. Identical requests arriving together share one provider call. For the deployed API, also set API Gateway
  throttling (a per-route rate limit), since this backend does not identify
  clients.
- **Few calls per search.** A recommendation routes at most the top 5 locations,
  then only the first choice and backup if they are not yet checked (at most 11
  calls, in an 8 s budget per request; see `docs/recommendations.md`).
  Successful routes are cached, so repeat searches cost nothing.
- **Request deadlines.** Each recommendation's walking routes share one
  deadline (its 8 s budget); each `/routes` call gets 10 s
  (`ROUTE_REQUEST_BUDGET_SECONDS`, under the website's 12 s route timeout). The
  throttle refuses a slot that would leave less than 0.25 s, without reserving
  it; the deadline is checked again right before the request is sent; and the
  provider timeout is capped at the time left. Queued work that was never
  started is cancelled. So once a request's budget is over, it starts no new provider
  calls and takes no slots from later searches.
- **Already-started calls.** A walking route already sent when a
  recommendation's budget runs out is not aborted, and the response does not
  wait for it (a `/routes` call answers when its one provider call ends). Its timeout was capped at
  the time left; httpx applies that to each network step (connect, send, each
  read), so a slow call can end a little after the deadline. A route that
  arrives is cached for the next search. A call is only started with at least
  0.25 s left (`MIN_PROVIDER_SECONDS`). On Lambda the response returns at the
  budget and the instance freezes; a call still open is dropped or finishes
  when the instance next thaws, and it can never start a new request then,
  because the deadline is checked right before sending.
- **Not shared between processes.** The throttle and cache live in memory. Two
  uvicorn workers, or several concurrent Lambda instances, each have their own,
  so together they could exceed one request a second.

Deployment plan:

1. **Demo and pilot (now):** public FOSSGIS, one backend process (or Lambda with
   reserved concurrency 1). Searches during a busy minute may show
   straight-line walking times, labeled as unchecked.
2. **Before public launch:** switch off the public servers. Either set
   `ORS_API_KEY` (OpenRouteService free plan: 2,000 directions/day, 40/min; set
   `PARKSMART_ROUTING_PROVIDER=ors`), or run our own OSRM with OpenStreetMap
   data for San Diego and set `OSRM_DRIVING_URL` / `OSRM_WALKING_URL` (no
   throttle is applied to self-hosted servers). Self-hosting needs an always-on
   server, which needs funded DS3 AWS access.
3. **If neither is available:** `PARKSMART_ROUTING_PROVIDER=none`. The site keeps
   working with straight-line walks and the "Open in Google Maps" link.

## Lambda handoff

For Daira's backend deployment. Nothing here needs code changes.

| Topic | What to set or know |
| --- | --- |
| Python | 3.12 runtime (has OpenSSL 3 and TLS 1.3). Package `requirements.txt` as usual; `httpx` is the only routing dependency. |
| Function timeout | At least **30 s**. Routing work stops at each request's deadline (see "Request deadlines" above). Each provider call times out after 8 s (`PROVIDER_TIMEOUT_SECONDS`); a recommendation spends at most 8 s on walking routes (`WALK_ROUTING_BUDGET_SECONDS`) on top of ranking; the website gives up after 20 s. API Gateway caps integrations at about 30 s (29 s for REST APIs). |
| Internet access | The function must reach `routing.openstreetmap.de` (or `api.openrouteservice.org`) over HTTPS. Outside a VPC this works by default. Inside a VPC it needs a NAT gateway, which costs money: do not enable it without funded DS3 access; use `PARKSMART_ROUTING_PROVIDER=none` instead. |
| Concurrency | The FOSSGIS, OpenRouteService and `/routes` throttles are per instance. Set reserved concurrency to **1** while using the public servers, or switch provider (plan above). Add API Gateway throttling on `POST /routes`. |
| Cache | In memory only (1,024 routes). Lost on every cold start and not shared between instances, so a cold function routes again. Not a reason to add a database; it only saves provider calls. |
| Environment | `PARKSMART_CORS_ORIGINS` (Amplify URL). Optional `ORS_API_KEY` as an encrypted variable or Secrets Manager value, never in Git or `VITE_` variables. `PARKSMART_ROUTING_PROVIDER=none` to turn routes off. |
| Logs | CloudWatch shows one warning when routes are turned off (no TLS 1.3, bad configuration) and a warning, with the reasons, whenever every walking route in a recommendation's routing round failed. Provider errors are never returned to the browser. |
| Attribution | Responses carry "Route data © OpenStreetMap contributors"; the website shows it with a "Fix the map" link to openstreetmap.org/fixthemap. Keep both if another client (the mobile app) shows routes. |

## `POST /routes` contract

Request:

```json
{
  "mode": "walking",
  "origin": {"latitude": 32.88423701, "longitude": -117.24306936},
  "destination": {"latitude": 32.8811, "longitude": -117.2376}
}
```

Response (200):

```json
{
  "schema_version": "0.1",
  "mode": "walking",
  "distance_meters": 896.2,
  "distance_miles": 0.56,
  "duration_minutes": 11.9,
  "geometry": [[-117.243088, 32.884246], "... [longitude, latitude] pairs"],
  "traffic_aware": false,
  "provider": "OSRM (OpenStreetMap data)",
  "attribution": "Route data © OpenStreetMap contributors",
  "limitations": ["Walking path from map data; check signs for closures and construction.",
                  "Starts at the parking location's map point, which may not be its pedestrian exit."]
}
```

`geometry` is GeoJSON LineString order, ready for a map line layer.

| Status | Meaning |
| --- | --- |
| 400 | Trip longer than the mode allows in a straight line (driving 150 km, walking 5 km), so the endpoint cannot be used as a general router that spends the project's quota. |
| 404 | The provider found no road or path near a point, or had to move a point more than 150 m (walking) or 250 m (driving) to reach one. |
| 422 | Invalid JSON, mode or coordinates. |
| 502 | Provider failed, timed out (8 s, or less when the 10 s request budget is nearly used), was too busy (throttle slot over 6 s away or after the request deadline), had a certificate or temporary TLS error, or answered unreadable or invalid geometry. Details go to the server log, never to the client. |
| 503 | Routing is not configured on this server, or was turned off because this Python cannot use TLS 1.3 (see the server log). |

Successful routes are cached in memory (1,024 trips, about 1 m coordinate
precision). "No route" answers (no path, or a point snapped too far) are
remembered for an hour (`NO_ROUTE_CACHE_SECONDS`) so an impossible trip does not
spend a provider call on every search; provider failures are never cached. For
OpenRouteService only error codes 2009/2010 count as "no route"; any other 404
is reported as a configuration problem (base URL or profile). OpenRouteService
requests are spaced 1.6 s apart per process (`ORS_MIN_INTERVAL_SECONDS`, at most
38 a minute) to stay under its 40-a-minute free limit; with ORS a search routes
fewer walks in its 8 s budget, and the rest stay labeled unchecked.

`duration_minutes` is rounded to 0.1 min (`route_minutes`); the website shows
it rounded up with a 1-minute floor, and ranking uses the same number
(`display_minutes`), so a card and the directions box always show the same
walking time. The website also keeps successful routes for
the visit, so switching between first choice and backup does not repeat requests.

## Snapping check (2026-11-05)

Providers move ("snap") each requested point to the nearest mapped road or path.
For all 46 supported registry locations, a walking route from the location to
Geisel Library and a driving route from downtown San Diego to it moved the
parking point at most **55 m** (walking) and **60 m** (driving); most moved under
25 m. Routes that move a point more than 150 m (walking) or 250 m (driving)
(`MAX_SNAP_METERS`) are rejected as no route, because they would not start or
end where asked. They are not cached; ranking keeps the straight-line estimate
and labels it unchecked.

## Parking end points (approximation)

Registry coordinates (`config/locations.json`) are UCSD GIS **building points**,
not verified vehicle entrances or pedestrian exits. Routes therefore start or end
at the building point, and both the API limitations and the website say so.
Replacing them needs a separate, verified entrance field per location; nothing
in the registry is guessed.

## Walking-route pilot (2026-11-04)

Eight parking-to-destination pairs, FOSSGIS walking server, compared with the
recommender's straight-line estimate (13 min/km + 2 min, minimum 3):

| Parking | Destination | Straight km | Routed km | Routed min | Straight-line estimate min |
| --- | --- | --- | --- | --- | --- |
| hopkins-ps | Geisel Library | 0.34 | 0.44 | 5.9 | 6 |
| pangea-ps | Geisel Library | 0.62 | 0.90 | 11.9 | 10 |
| torrey-pines-center-north-ps | Geisel Library | 1.26 | 1.70 | 22.6 | 18 |
| p402 | Price Center | 0.54 | 0.69 | 9.2 | 9 |
| gilman-ps | Price Center | 0.33 | 0.47 | 6.3 | 6 |
| scholars-ps | Geisel Library | 0.39 | 0.47 | 6.2 | 7 |
| torrey-pines-center-north-ps | RIMAC | 0.52 | 0.72 | 9.6 | 9 |
| p705 | Jacobs Medical Center | 0.64 | 0.85 | 11.3 | 10 |

Routed paths followed campus walkways and were 1.2–1.4× the straight line. The
estimate is within about a minute for short walks but underestimates long ones:
Torrey Pines Center North to Geisel routes at 22.6 minutes, above the
recommender's 20-minute walking limit, while the card said about 18. Ranking
therefore now uses routed walking times for the top locations, and then for the
final picks, whenever routing is configured (see "Routed walks" in `docs/recommendations.md`): that location is
dropped as over the limit, and the card and the directions box show the same
routed time. A live check (S permit, Geisel Library, Tue 10 AM) took about 0.6 s
with an empty route cache and about 0.02 s cached.

A driving check from downtown San Diego to Hopkins Parking Structure returned
24.7 km and 21.4 minutes without traffic.

## Open items for review

- Confirm `POST /routes` with Daira so the mobile app can reuse it, and whether it
  stays a separate Lambda route or joins the main FastAPI handler.
- Optional: an OpenRouteService key under a DS3-owned account once
  openrouteservice.org is back online, stored as a Lambda secret.
- Verified vehicle entrances and pedestrian exits per location.
