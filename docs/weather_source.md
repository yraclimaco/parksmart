# Weather context for trip alerts — Issue #35

The backend uses Open-Meteo's public forecast endpoint for arrival-time weather
context. It does not feed weather into the availability model, permit rules or
parking ranking. A normal forecast with no planning suggestions is still
`available`; an empty suggestion list does not mean the source failed.

## Source and access

Primary references, checked November 13, 2026:

- [Forecast API documentation](https://open-meteo.com/en/docs): hourly variables,
  units, UTC Unix timestamps and up-to-16-day forecast range.
- [Free API terms](https://open-meteo.com/en/terms): noncommercial use only,
  fewer than 10,000 calls/day, 5,000/hour and 600/minute; no uptime guarantee.
- [Pricing and call accounting](https://open-meteo.com/en/pricing): requests
  covering more than 14 days or more than ten variables count as multiple or
  fractional calls. Our 16-day request can therefore consume more than one call
  equivalent.
- [Data licence and attribution](https://open-meteo.com/en/licence): CC BY 4.0;
  display a link to Open-Meteo beside weather information, link the licence and
  explain that ParkSmart selects hourly values and derives planning suggestions.

Use `source_name: Open-Meteo` and `source_url: https://open-meteo.com/` from the
response for the visible attribution link. No paid subscription, account, API
key or customer endpoint is configured. This educational, noncommercial project
must reassess access terms before commercial or high-traffic use.

An initial campus request timed out during its TLS handshake. A later bounded
`JSONHTTP`/`WeatherProvider` check succeeded at `2026-11-14T08:07:03Z`, returning
`available` for Gilman's upcoming arrival hour; its model grid was
`32.872, -117.223`. That check verifies the request/parsing path, not forecast
accuracy or ongoing source availability. Tests use synthetic, API-shaped
payloads and injected transport errors, never call a real provider, and do not
present fixtures as observed weather.

## Query and location

`WeatherProvider(http, cache, utcnow=None).get(arrival, targets)` selects the first
parking target, otherwise the destination. It does not geocode display names or
send a user's starting position. The request rounds coordinates to three decimal
places, uses those same coordinates in its cache key, and asks for:

```text
GET https://api.open-meteo.com/v1/forecast
latitude=<rounded target latitude>
longitude=<rounded target longitude>
hourly=temperature_2m,apparent_temperature,precipitation_probability,precipitation,wind_speed_10m,weather_code
forecast_days=16
timeformat=unixtime
timezone=UTC
temperature_unit=celsius
wind_speed_unit=kmh
precipitation_unit=mm
```

This is one approximate weather-model grid point near the selected trip point,
not a measurement at a parking entrance or along the whole walking route. The
response limitations retain the returned model-grid coordinates when present.
Nearby conditions may differ. No precise user starting coordinates are needed.

Present grid coordinates must be finite WGS84 values. A grid more than 100 km
from the rounded requested point is rejected before replacing cached data.
This deliberately generous location-integrity guard allows coarse nearby grids
while rejecting unrelated-location responses; it is a ParkSmart implementation
choice, not a provider coverage or forecast-accuracy guarantee. Missing grid
metadata does not invalidate otherwise usable hourly values, but the limitations
explicitly say the source grid location and its proximity are unknown.

## Arrival-hour meaning

An arrival must have a resolved UTC offset. Convert it to UTC and choose the
first whole-hour timestamp at or after it. An exact-hour arrival uses that same
timestamp. For example, a 09:30 arrival uses the 10:00 sample:

| Output | Meaning |
| --- | --- |
| `forecast_time`, `period_end` | 10:00 forecast timestamp |
| `period_start` | 09:00 |
| `temperature_c`, `apparent_temperature_c`, `wind_speed_kmh`, `weather_code` | Instantaneous model values at 10:00; an approximation for the arrival |
| `precipitation_mm` | Model precipitation total during the preceding 09:00–10:00 hour |
| `precipitation_probability_percent` | Probability of more than 0.1 mm precipitation during that preceding hour |

The documentation specifies a fixed UTC offset for its ISO timestamps even when
the response spans a daylight-saving transition. Unix timestamps avoid that
ambiguity; the backend does not apply one fixed local offset to the whole
forecast. Repeated local hours remain distinct UTC hours.

Past arrivals are `out_of_range`, with no historical/current-condition fallback.
The advertised 16-day maximum is an initial request gate only. The requested
sample must also exist exactly in the actual returned hourly array. A shorter
returned range or an arrival whose rounded-up sample lies outside that range
returns `out_of_range`, no forecast and no suggestions. The provider never
substitutes another day or nearest available hour, interpolates missing readings,
or turns a model timestamp into an observation timestamp.

## Suggestions and missing fields

The following are fixed **ParkSmart walking-comfort rules**, not National Weather
Service or other official warning criteria:

| Known forecast value | Suggestion |
| --- | --- |
| Precipitation probability >= 50% | Consider rain protection for the walk |
| Apparent temperature >= 30°C | Consider water and shade |
| Wind speed >= 30 km/h | Wind may make walking less comfortable |

All generated items have `alert_type: weather`, `match_basis: forecast_hour`, the
selected target, the hour's start/end, source attribution, successful retrieval
time and the timing/approximation/threshold limitations. There are no official
warning claims or guaranteed weather outcomes. These thresholds express a
simple product choice and have not been validated as parking-prediction features.

Missing fields, nulls, mismatched source units, truncated arrays, booleans,
nonfinite numbers, negative precipitation/wind, invalid probability percentages
and unknown WMO codes remain null rather than becoming zero. A partially usable
arrival sample returns `partial`; rules use only known valid fields. Known zero
values remain valid. If no usable field exists at the selected arrival hour,
the result is `unavailable` with no forecast or suggestions.

Fundamentally malformed source/error responses, missing units/timeline, duplicate
or nonhourly timestamps, or wholly unusable payloads fail validation before
replacing cached data. The previous valid response may then be used only under
the explicit stale policy.

## Refreshes and failure behavior

The shared `JSONHTTP` applies a four-second refresh budget, socket waits capped
at two seconds, bounded response bytes, no redirects and no retries. The service
allows 6.5 seconds overall to include an in-progress socket wait beyond the
refresh deadline. The shared `CachedJSON` stores
at most 64 entries, shares refreshes for a coordinate key and different arrivals,
keeps successful results fresh for 15 minutes, backs off failed refreshes, and
permits explicitly stale data for at most one hour **total age** from successful
retrieval. Reading a cache never refreshes its timestamp.

A failed refresh retains `last_checked_at` from the actual successful retrieval
and separately records `last_attempt_at`. A usable stale forecast has status
`stale`, including when some fields are missing; its suggestions also carry the
stale limitation. A stale response that does not cover the arrival is
`out_of_range` with a stale limitation and no suggestions. Once the one-hour
total-age limit expires, failures are `unavailable`, without old forecast values.
Missing location, source failures and unknown fields do not break parking
recommendations or create simulated weather.

The cache bounds memory, not the provider's total quota. A retained coordinate
key needs at most four successful refreshes/hour/process. Many coordinates, LRU
churn, failure retries, multiple workers or shared-IP users increase usage. Keep
initial use to a single low-traffic process, monitor aggregate usage and leave
the provider disabled if the free service cannot support the planned load.

Offline verification:

```bash
python -m pytest tests/test_weather_alerts.py -q
```

The tests cover threshold boundaries, normal weather, UTC hour selection and
fall-DST repetition, unknown/invalid fields and units, actual source horizons,
missing locations, caching across arrivals/rounded points, failed refreshes,
stale provenance and expiry. The HTTP transport and shared cache have their own
tests outside this provider module. Grid validation tests cover malformed,
out-of-bounds and unrelated locations, stale-cache preservation, missing-grid
limitations and an ordinary nearby grid. Every suggestion message explicitly
identifies its information as a forecast, including when rendered alone.
