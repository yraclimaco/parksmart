"""Arrival-hour Open-Meteo forecasts and simple walking-comfort suggestions.

Precipitation values describe the hour ending at a provider timestamp, whereas
temperature, wind and weather code describe that timestamp. We select the next
whole UTC hour at/after arrival, never interpolate or replace an absent hour.
See docs/weather_source.md for source terms, attribution and the planning rules.
"""

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import hashlib
import math
import time

from .cache import SourceError
from .contracts import ProviderResult
from .http import SOURCE_BUDGET_SECONDS

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
SOURCE_NAME = "Open-Meteo"
SOURCE_URL = "https://open-meteo.com/"
CACHE_SECONDS = 15 * 60
MAX_STALE_SECONDS = 60 * 60
COORDINATE_DECIMALS = 3
FORECAST_DAYS = 16
HOURS_PER_DAY = 24
SECONDS_PER_HOUR = 60 * 60
MAX_HOURLY_RECORDS = FORECAST_DAYS * HOURS_PER_DAY
# IUGG mean Earth radius, also used by the project's routing calculations.
EARTH_RADIUS_KM = 6371.0088
# Generous wrong-location guard, beyond Open-Meteo's normal kilometre-scale
# grids; this is a response-integrity check, not a forecast-accuracy boundary.
MAX_GRID_DISTANCE_KM = 100

# ParkSmart walking-comfort rules, not official warning/advisory thresholds.
RAIN_PROBABILITY_PERCENT = 50
HEAT_APPARENT_C = 30
WIND_SPEED_KMH = 30
WEATHER_CODES = frozenset({
    0, 1, 2, 3, 45, 48, 51, 53, 55, 56, 57, 61, 63, 65, 66, 67,
    71, 73, 75, 77, 80, 81, 82, 85, 86, 95, 96, 99,
})
FIELDS = {
    "temperature_2m": ("temperature_c", "°C"),
    "apparent_temperature": ("apparent_temperature_c", "°C"),
    "precipitation_probability": ("precipitation_probability_percent", "%"),
    "precipitation": ("precipitation_mm", "mm"),
    "wind_speed_10m": ("wind_speed_kmh", "km/h"),
    "weather_code": ("weather_code", "wmo code"),
}
TIMING_LIMITATION = (
    "The selected forecast is the next whole UTC hour at or after arrival. "
    "Precipitation covers the preceding hour; temperature, wind and weather "
    "code are values at the ending timestamp."
)
ADVICE_LIMITATION = (
    "Weather suggestions use ParkSmart planning thresholds, not official "
    "weather warnings."
)
STALE_LIMITATION = (
    "This forecast is stale; the last successful retrieval time is retained "
    "and a failed refresh does not make it current."
)


def _number(value):
    """Return a finite JSON number as float, preserving missing/invalid as None."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        try:
            number = float(value)
        except (OverflowError, TypeError, ValueError):
            return None
        if math.isfinite(number):
            return number
    return None


def _field_value(field, value):
    """Validate one provider value without clipping or inventing a replacement."""
    number = _number(value)
    if number is None:
        return None
    if field == "precipitation_probability" and not 0 <= number <= 100:
        return None
    if field in {"precipitation", "wind_speed_10m"} and number < 0:
        return None
    if field == "weather_code":
        return int(number) if number in WEATHER_CODES else None
    return number


def _grid_location(document, latitude, longitude):
    """Validate supplied source-grid coordinates against the requested point."""
    grid = {}
    for name, maximum in (("latitude", 90), ("longitude", 180)):
        raw = document.get(name)
        value = _number(raw)
        if raw is not None and (value is None or not -maximum <= value <= maximum):
            raise SourceError("Weather model-grid coordinates are invalid.")
        grid[name] = value
    if grid["latitude"] is not None and grid["longitude"] is not None:
        request_lat, grid_lat = map(math.radians, (latitude, grid["latitude"]))
        longitude_difference = math.radians(grid["longitude"] - longitude)
        chord = (math.sin((grid_lat - request_lat) / 2) ** 2
                 + math.cos(request_lat) * math.cos(grid_lat)
                 * math.sin(longitude_difference / 2) ** 2)
        distance = (2 * EARTH_RADIUS_KM
                    * math.asin(math.sqrt(min(1, max(0, chord)))))
        if distance > MAX_GRID_DISTANCE_KM:
            raise SourceError("Weather model grid is too far from the request.")
    return grid


def _validated_payload(document, latitude, longitude):
    """Check the hourly timeline and normalize fields for a cacheable forecast."""
    if not isinstance(document, dict) or document.get("error") is True:
        raise SourceError("Weather provider returned an invalid forecast.")
    grid = _grid_location(document, latitude, longitude)
    hourly = document.get("hourly")
    units = document.get("hourly_units")
    if not isinstance(hourly, dict) or not isinstance(units, dict):
        raise SourceError("Weather forecast is missing its timeline or units.")
    times = hourly.get("time")
    if (units.get("time") != "unixtime" or not isinstance(times, list)
            or not 1 <= len(times) <= MAX_HOURLY_RECORDS):
        raise SourceError("Weather forecast has no usable UTC hourly timeline.")
    previous = None
    for stamp in times:
        number = _number(stamp)
        if (number is None or number % SECONDS_PER_HOUR != 0
                or (previous is not None
                    and number - previous != SECONDS_PER_HOUR)):
            raise SourceError("Weather forecast timestamps are invalid.")
        try:
            datetime.fromtimestamp(number, timezone.utc)
        except (OverflowError, OSError, ValueError) as error:
            raise SourceError("Weather forecast timestamp is outside range.") from error
        previous = number
    values = {}
    for field, (output, unit) in FIELDS.items():
        series = hourly.get(field)
        valid_shape = isinstance(series, list) and len(series) == len(times)
        values[output] = [
            _field_value(field, value) for value in series
        ] if valid_shape and units.get(field) == unit else [None] * len(times)
    if not any(value is not None for series in values.values() for value in series):
        raise SourceError("Weather forecast contains no usable values.")
    return {"times": times, "values": values, **grid}


def _target(targets):
    """Choose the first parking point, otherwise the destination, with coordinates."""
    for role in ("parking", "destination"):
        for target in targets:
            if target.role != role:
                continue
            latitude = _number(target.latitude)
            longitude = _number(target.longitude)
            if (latitude is not None and longitude is not None
                    and -90 <= latitude <= 90 and -180 <= longitude <= 180):
                return target
    return None


class WeatherProvider:
    """Read/cache a small forecast and return arrival-specific trip context.

    Args:
        http: Shared JSONHTTP transport; no retries, credentials or paid endpoint.
        cache: Shared CachedJSON instance bounding refreshes and retained data.
        utcnow: Optional aware clock used to reject past arrival requests.
    """

    def __init__(self, http, cache, utcnow=None):
        self.http = http
        self.cache = cache
        self.utcnow = utcnow or (lambda: datetime.now(timezone.utc))

    def get(self, arrival, targets):
        """Return ProviderResult for an aware arrival and verified trip targets.

        Parking is preferred over destination. Queries use rounded coordinates
        and share one cached response across arrival times. Unsupported hours,
        past arrivals and unusable values never produce fabricated forecasts.
        """
        if arrival.tzinfo is None or arrival.utcoffset() is None:
            raise ValueError("Weather arrival must include a UTC offset.")
        arrival = arrival.astimezone(timezone.utc)
        now = self.utcnow().astimezone(timezone.utc)
        target = _target(targets)
        if target is None:
            return ProviderResult(
                "missing_location", SOURCE_NAME, SOURCE_URL,
                limitations=["A verified parking or destination point is needed "
                             "for a weather forecast."],
            )
        forecast_time = arrival.replace(minute=0, second=0, microsecond=0)
        if forecast_time < arrival:
            forecast_time += timedelta(hours=1)
        maximum = now.replace(hour=0, minute=0, second=0, microsecond=0)
        maximum += timedelta(days=FORECAST_DAYS)
        if arrival < now or forecast_time >= maximum:
            return ProviderResult(
                "out_of_range", SOURCE_NAME, SOURCE_URL,
                limitations=["Weather forecasts cover future arrivals within "
                             "the provider's returned range, up to 16 days "
                             "starting today; past arrivals are not supported."],
            )
        latitude = round(target.latitude, COORDINATE_DECIMALS)
        longitude = round(target.longitude, COORDINATE_DECIMALS)
        key = ("weather", latitude, longitude)

        def load():
            """Fetch/validate within one refresh deadline before replacing cache."""
            params = {
                "latitude": latitude, "longitude": longitude,
                "hourly": ",".join(FIELDS), "forecast_days": FORECAST_DAYS,
                "timeformat": "unixtime", "timezone": "UTC",
                "temperature_unit": "celsius", "wind_speed_unit": "kmh",
                "precipitation_unit": "mm",
            }
            document = self.http.get_json(
                FORECAST_URL, params=params,
                deadline=time.monotonic() + SOURCE_BUDGET_SECONDS,
            )
            return _validated_payload(document, latitude, longitude)

        cached = self.cache.get(key, load, ttl_seconds=CACHE_SECONDS,
                                max_stale_seconds=MAX_STALE_SECONDS)
        provenance = {
            "last_checked_at": cached.last_checked_at,
            "last_attempt_at": cached.last_attempt_at,
        }
        if cached.data is None:
            return ProviderResult(
                "unavailable", SOURCE_NAME, SOURCE_URL, **provenance,
                limitations=["The weather source is unavailable; no forecast "
                             "or weather suggestions are available."],
            )
        data = cached.data
        limitations = [TIMING_LIMITATION, ADVICE_LIMITATION]
        grid_lat, grid_lon = data["latitude"], data["longitude"]
        if grid_lat is not None and grid_lon is not None:
            limitations.append(
                "Weather is an approximate model-grid forecast near the selected "
                f"trip point (grid {grid_lat:.3f}, {grid_lon:.3f}); campus "
                "conditions may differ.")
        else:
            limitations.append(
                "Weather was requested near the selected trip point, but the "
                "source model-grid location is unknown; its proximity cannot "
                "be checked and campus conditions may differ.")
        if cached.state == "stale":
            limitations.append(STALE_LIMITATION)
        stamp = int(forecast_time.timestamp())
        if stamp not in data["times"]:
            limitations.append("The requested arrival hour is outside the "
                               "actual returned forecast hours; no substitute "
                               "hour was used.")
            return ProviderResult(
                "out_of_range", SOURCE_NAME, SOURCE_URL, **provenance,
                limitations=limitations,
            )
        index = data["times"].index(stamp)
        selected = {name: series[index] for name, series in data["values"].items()}
        if all(value is None for value in selected.values()):
            limitations.append("No usable weather fields were supplied for "
                               "the selected arrival hour.")
            return ProviderResult(
                "unavailable", SOURCE_NAME, SOURCE_URL, **provenance,
                limitations=limitations,
            )
        missing = [name for name, value in selected.items() if value is None]
        if missing:
            limitations.append("Some forecast fields are unavailable and remain "
                               "unknown: " + ", ".join(missing) + ".")
        start = forecast_time - timedelta(hours=1)
        forecast = {
            "location": asdict(target), "forecast_time": forecast_time,
            "period_start": start, "period_end": forecast_time, **selected,
        }
        alerts = self._suggestions(selected, target, start, forecast_time,
                                   cached.last_checked_at, limitations)
        status = "partial" if missing else "available"
        if cached.state == "stale":
            status = "stale"
        return ProviderResult(
            status, SOURCE_NAME, SOURCE_URL, **provenance,
            forecast=forecast, alerts=alerts, limitations=limitations,
        )

    def _suggestions(self, values, target, start, end, checked, limitations):
        """Return only planning suggestions justified by known threshold values."""
        messages = []
        rain = values["precipitation_probability_percent"]
        heat = values["apparent_temperature_c"]
        wind = values["wind_speed_kmh"]
        if rain is not None and rain >= RAIN_PROBABILITY_PERCENT:
            messages.append(("precipitation", "Forecast precipitation could affect the "
                             f"walk ({rain:g}% probability); consider rain "
                             "protection around arrival."))
        if heat is not None and heat >= HEAT_APPARENT_C:
            messages.append(("heat", f"Forecast feels-like temperature is "
                             f"{heat:g}°C around arrival; consider water and "
                             "shade for the walk."))
        if wind is not None and wind >= WIND_SPEED_KMH:
            messages.append(("wind", f"Forecast wind of {wind:g} km/h around "
                             "arrival may make the walk less comfortable."))
        result = []
        for kind, message in messages:
            identity = (f"{target.latitude:.3f}:{target.longitude:.3f}:"
                        f"{int(end.timestamp())}:{kind}")
            digest = hashlib.sha256(identity.encode("ascii")).hexdigest()[:16]
            result.append({
                "alert_id": "weather-" + digest, "alert_type": "weather",
                "message": message, "locations": [asdict(target)],
                "relevant_from": start, "relevant_until": end,
                "source_name": SOURCE_NAME, "source_url": SOURCE_URL,
                "last_checked_at": checked, "match_basis": "forecast_hour",
                "limitations": list(limitations),
            })
        return result
