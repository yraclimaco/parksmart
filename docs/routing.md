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
- **Backend / Lambda:** nothing extra to deploy. `/routes` is part of the same
  FastAPI app. Set `ORS_API_KEY` (as a secret) and, for the deployed website,
  `PARKSMART_CORS_ORIGINS` in the Lambda environment. Without a key, `/routes`
  answers 503 and everything else works.
- **Trying it locally without a key:** `PARKSMART_ROUTING_PROVIDER=osrm` (needs
  Python 3.11+; see the note below).

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
| `PARKSMART_ROUTING_PROVIDER` | `ors`, `osrm` or `none`. Unset: `ors` if `ORS_API_KEY` is set, otherwise routing is **off**. The public OSRM servers are only used when chosen explicitly. |
| `ORS_API_KEY` | OpenRouteService key. Secret: never commit it, never put it in a `VITE_` variable. |
| `OSRM_DRIVING_URL`, `OSRM_WALKING_URL` | Optional self-hosted OSRM servers; default to `routing.openstreetmap.de`. |

```bash
# Local development with OpenRouteService
export ORS_API_KEY=...            # from openrouteservice.org, never committed
python -m uvicorn src.api.saved_model:create_saved_app --factory

# Local development without a key (light use only)
PARKSMART_ROUTING_PROVIDER=osrm python -m uvicorn src.api.main:app --reload
```

An unknown provider name or `ors` without a key logs a warning and turns routes
off; recommendations and `/health` keep working.

**Local Python note:** the FOSSGIS servers accept only TLS 1.3. The macOS
system/Xcode Python 3.9 (LibreSSL 2.8.3) cannot connect to them and reports
`SSLV3_ALERT_HANDSHAKE_FAILURE`; the route endpoint then returns 502. Use a newer
Python (3.11+, as on AWS Lambda) for `osrm`. OpenRouteService works with either.

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
| 404 | The provider found no road or path near a point. |
| 422 | Invalid JSON, mode or coordinates. |
| 502 | Provider failed, timed out (8 s) or answered unreadably. Details go to the server log, never to the client. |
| 503 | Routing is not configured on this server. |

Successful routes are cached in memory (1,024 trips, about 1 m coordinate
precision). Failures are not cached. The website also keeps successful routes for
the visit, so switching between first choice and backup does not repeat requests.

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
therefore now uses routed walking times for the top locations whenever routing is
configured (see "Routed walks" in `docs/recommendations.md`): that location is
dropped as over the limit, and the card and the directions box show the same
routed time. A live check (S permit, Geisel Library, Tue 10 AM) took about 0.6 s
with an empty route cache and about 0.02 s cached.

A driving check from downtown San Diego to Hopkins Parking Structure returned
24.7 km and 21.4 minutes without traffic.

## Open items for review

- Confirm `POST /routes` with Daira so the mobile app can reuse it, and whether it
  stays a separate Lambda route or joins the main FastAPI handler.
- Sign up for an OpenRouteService key under a DS3-owned account and store it as a
  Lambda environment variable or secret, never in the repository.
- Verified vehicle entrances and pedestrian exits per location.
