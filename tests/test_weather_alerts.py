"""Offline weather source, time alignment, missing values and cache regressions."""

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

import pytest

from src.trip_alerts.cache import CachedJSON, SourceError
from src.trip_alerts.contracts import AlertTarget
from src.trip_alerts.weather import WeatherProvider

UTC = timezone.utc
NOW = datetime(2026, 11, 13, 8, 10, tzinfo=UTC)
ARRIVAL = datetime(2026, 11, 13, 18, 30, tzinfo=UTC)
START = datetime(2026, 11, 13, 18, tzinfo=UTC)
PARKING = AlertTarget("parking", "Gilman", 32.87756, -117.23365, "gilman-ps")
DESTINATION = AlertTarget("destination", "Geisel", 32.88111, -117.23761)


class Clock:
    """Advance monotonic durations and aware UTC time together."""

    def __init__(self, now=NOW):
        self.now = now
        self.duration = 0.0

    def utcnow(self):
        return self.now

    def monotonic(self):
        return self.duration

    def advance(self, seconds):
        self.duration += seconds
        self.now += timedelta(seconds=seconds)


class FakeHTTP:
    """Return a controlled source response; no test contacts a provider."""

    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    def get_json(self, url, params=None, deadline=None):
        self.calls.append((url, params, deadline))
        if isinstance(self.payload, Exception):
            raise self.payload
        return deepcopy(self.payload)


def payload(start=START, hours=3):
    """Build a small synthetic API-shaped fixture with explicit source units."""
    return {
        "latitude": 32.875, "longitude": -117.25,
        "hourly_units": {
            "time": "unixtime", "temperature_2m": "°C",
            "apparent_temperature": "°C", "precipitation_probability": "%",
            "precipitation": "mm", "wind_speed_10m": "km/h",
            "weather_code": "wmo code",
        },
        "hourly": {
            "time": [int((start + timedelta(hours=i)).timestamp())
                     for i in range(hours)],
            "temperature_2m": [20] * hours,
            "apparent_temperature": [21] * hours,
            "precipitation_probability": [10] * hours,
            "precipitation": [0] * hours,
            "wind_speed_10m": [5] * hours,
            "weather_code": [0] * hours,
        },
    }


def provider(document=None, now=NOW):
    """Return provider/transport/clock with a real bounded cache and fake I/O."""
    clock = Clock(now)
    http = FakeHTTP(payload() if document is None else document)
    cache = CachedJSON(monotonic=clock.monotonic, utcnow=clock.utcnow)
    return WeatherProvider(http, cache, utcnow=clock.utcnow), http, clock


def test_forecast_available_without_threshold_alerts_and_hour_alignment():
    weather, http, _ = provider()
    result = weather.get(ARRIVAL, [DESTINATION, PARKING])
    assert result.status == "available"
    assert result.alerts == []
    assert result.forecast["location"] == asdict(PARKING)
    assert result.forecast["forecast_time"] == START + timedelta(hours=1)
    assert result.forecast["period_start"] == START
    assert result.forecast["period_end"] == START + timedelta(hours=1)
    assert result.forecast["precipitation_mm"] == 0
    assert result.last_checked_at == NOW
    assert result.last_attempt_at == NOW
    assert any("preceding hour" in text for text in result.limitations)
    assert any("approximate model-grid" in text for text in result.limitations)
    assert http.calls[0][1]["latitude"] == 32.878
    assert http.calls[0][1]["longitude"] == -117.234
    assert http.calls[0][1]["timezone"] == "UTC"
    assert http.calls[0][1]["timeformat"] == "unixtime"
    assert http.calls[0][1]["forecast_days"] == 16
    assert http.calls[0][1]["wind_speed_unit"] == "kmh"
    assert http.calls[0][2] is not None


def test_exact_hour_uses_that_hour_without_shift():
    weather, _, _ = provider()
    result = weather.get(START, [DESTINATION])
    assert result.forecast["forecast_time"] == START
    assert result.forecast["period_start"] == START - timedelta(hours=1)
    assert result.forecast["location"] == asdict(DESTINATION)


def test_threshold_values_create_three_typed_context_alerts():
    document = payload()
    document["hourly"]["precipitation_probability"][1] = 50
    document["hourly"]["apparent_temperature"][1] = 30
    document["hourly"]["wind_speed_10m"][1] = 30
    weather, _, _ = provider(document)
    result = weather.get(ARRIVAL, [PARKING])
    assert len(result.alerts) == 3
    assert len({alert["alert_id"] for alert in result.alerts}) == 3
    for alert in result.alerts:
        assert "forecast" in alert["message"].lower()
        assert alert["alert_type"] == "weather"
        assert alert["locations"] == [asdict(PARKING)]
        assert alert["match_basis"] == "forecast_hour"
        assert alert["relevant_from"] == START
        assert alert["relevant_until"] == START + timedelta(hours=1)
        assert alert["last_checked_at"] == NOW
        assert alert["source_url"] == "https://open-meteo.com/"
        assert any("not official" in text for text in alert["limitations"])
    assert result.alerts == weather.get(ARRIVAL, [PARKING]).alerts


@pytest.mark.parametrize("field,value,normalized", [
    ("precipitation_probability", 101, "precipitation_probability_percent"),
    ("precipitation_probability", -1, "precipitation_probability_percent"),
    ("precipitation_probability", None, "precipitation_probability_percent"),
    ("apparent_temperature", "32", "apparent_temperature_c"),
    ("apparent_temperature", True, "apparent_temperature_c"),
    ("apparent_temperature", float("inf"), "apparent_temperature_c"),
    ("temperature_2m", float("nan"), "temperature_c"),
    ("temperature_2m", 10 ** 500, "temperature_c"),
    ("wind_speed_10m", -1, "wind_speed_kmh"),
    ("precipitation", -1, "precipitation_mm"),
    ("weather_code", 999, "weather_code"),
])
def test_invalid_or_missing_values_remain_null_not_zero(field, value, normalized):
    document = payload()
    document["hourly"][field][1] = value
    weather, _, _ = provider(document)
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "partial"
    assert result.forecast[normalized] is None
    assert result.alerts == []


@pytest.mark.parametrize("problem", ["missing", "short", "wrong_unit"])
def test_missing_series_and_wrong_units_do_not_invent_field_values(problem):
    document = payload()
    if problem == "missing":
        del document["hourly"]["wind_speed_10m"]
    elif problem == "short":
        document["hourly"]["wind_speed_10m"] = [100]
    else:
        document["hourly_units"]["wind_speed_10m"] = "mph"
    weather, _, _ = provider(document)
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "partial"
    assert result.forecast["wind_speed_kmh"] is None
    assert result.alerts == []


def test_known_zeros_stay_available():
    document = payload()
    for name in document["hourly"]:
        if name != "time":
            document["hourly"][name] = [0, 0, 0]
    weather, _, _ = provider(document)
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "available"
    assert result.forecast["temperature_c"] == 0
    assert result.forecast["wind_speed_kmh"] == 0
    assert result.alerts == []


def test_past_and_beyond_maximum_horizon_do_not_contact_source():
    weather, http, _ = provider()
    for arrival in [NOW - timedelta(seconds=1), NOW + timedelta(days=16)]:
        result = weather.get(arrival, [DESTINATION])
        assert result.status == "out_of_range"
        assert result.forecast is None and result.alerts == []
    assert http.calls == []


def test_actual_returned_range_overrides_advertised_horizon():
    weather, _, _ = provider()
    result = weather.get(ARRIVAL + timedelta(days=1), [DESTINATION])
    assert result.status == "out_of_range"
    assert result.forecast is None and result.alerts == []
    assert result.last_checked_at == NOW
    assert any("actual returned" in text for text in result.limitations)


def test_forecast_is_unavailable_when_selected_hour_has_no_usable_values():
    document = payload()
    for name in document["hourly"]:
        if name != "time":
            document["hourly"][name][1] = None
    weather, _, _ = provider(document)
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "unavailable"
    assert result.forecast is None and result.alerts == []


@pytest.mark.parametrize("problem", ["error", "empty", "duplicate", "gap",
                                         "iso_time", "bad_time", "no_units"])
def test_unusable_payloads_fail_without_success_timestamp(problem):
    document = payload()
    if problem == "error":
        document = {"error": True, "reason": "bad request"}
    elif problem == "empty":
        document["hourly"]["time"] = []
    elif problem == "duplicate":
        document["hourly"]["time"][1] = document["hourly"]["time"][0]
    elif problem == "gap":
        document["hourly"]["time"][1] += 3600
    elif problem == "iso_time":
        document["hourly_units"]["time"] = "iso8601"
    elif problem == "bad_time":
        document["hourly"]["time"][0] = True
    else:
        del document["hourly_units"]
    weather, _, _ = provider(document)
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "unavailable"
    assert result.last_checked_at is None
    assert result.last_attempt_at == NOW
    assert result.forecast is None and result.alerts == []


def test_cache_shared_across_arrivals_and_round_equivalent_coordinates():
    weather, http, _ = provider()
    weather.get(ARRIVAL, [DESTINATION])
    nearby = AlertTarget("destination", "Nearby", 32.88112, -117.23762)
    result = weather.get(ARRIVAL + timedelta(minutes=5), [nearby])
    assert len(http.calls) == 1
    assert result.forecast["location"]["name"] == "Nearby"


@pytest.mark.parametrize("bad_refresh", [SourceError("timeout"), {"error": True}])
def test_failed_refresh_keeps_stale_values_and_original_retrieval_time(bad_refresh):
    document = payload()
    document["hourly"]["precipitation_probability"][1] = 70
    weather, http, clock = provider(document)
    weather.get(ARRIVAL, [DESTINATION])
    clock.advance(901)
    http.payload = bad_refresh
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "stale"
    assert result.last_checked_at == NOW
    assert result.last_attempt_at == NOW + timedelta(seconds=901)
    assert result.forecast["precipitation_probability_percent"] == 70
    assert len(result.alerts) == 1
    assert any("stale" in text for text in result.alerts[0]["limitations"])
    clock.advance(2700)
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "unavailable"
    assert result.forecast is None and result.alerts == []
    assert result.last_checked_at == NOW


def test_out_of_range_stale_cache_has_no_alerts_and_preserves_stale_label():
    weather, http, clock = provider()
    weather.get(ARRIVAL, [DESTINATION])
    clock.advance(901)
    http.payload = SourceError("timeout")
    result = weather.get(ARRIVAL + timedelta(days=1), [DESTINATION])
    assert result.status == "out_of_range"
    assert result.forecast is None and result.alerts == []
    assert any("stale" in text for text in result.limitations)


def test_missing_location_and_naive_arrival_make_no_source_call():
    weather, http, _ = provider()
    assert weather.get(ARRIVAL, []).status == "missing_location"
    invalid = AlertTarget("parking", "Bad", float("nan"), -117.2, "bad")
    assert weather.get(ARRIVAL, [invalid]).status == "missing_location"
    with pytest.raises(ValueError, match="UTC offset"):
        weather.get(ARRIVAL.replace(tzinfo=None), [DESTINATION])
    assert http.calls == []


def test_fall_dst_repeated_hour_matches_distinct_utc_timestamps():
    zone = ZoneInfo("America/Los_Angeles")
    first = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=0)
    second = datetime(2026, 11, 1, 1, 30, tzinfo=zone, fold=1)
    document = payload(datetime(2026, 11, 1, 8, tzinfo=UTC), hours=4)
    document["hourly"]["temperature_2m"] = [10, 11, 12, 13]
    weather, http, _ = provider(document, now=datetime(2026, 10, 31, tzinfo=UTC))
    earlier = weather.get(first, [DESTINATION])
    later = weather.get(second, [DESTINATION])
    assert earlier.forecast["forecast_time"] == datetime(2026, 11, 1, 9, tzinfo=UTC)
    assert later.forecast["forecast_time"] == datetime(2026, 11, 1, 10, tzinfo=UTC)
    assert earlier.forecast["temperature_c"] == 11
    assert later.forecast["temperature_c"] == 12
    assert len(http.calls) == 1


@pytest.mark.parametrize("field,value", [
    ("latitude", 91), ("latitude", -91),
    ("longitude", 181), ("longitude", -181),
    ("latitude", float("nan")), ("longitude", float("inf")),
    ("latitude", True), ("longitude", "-117.25"),
])
def test_invalid_grid_coordinates_are_unavailable_not_near_trip(field, value):
    document = payload()
    document[field] = value
    weather, _, _ = provider(document)
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "unavailable"
    assert result.forecast is None and result.alerts == []
    assert result.last_checked_at is None


def test_wrong_location_grid_does_not_replace_valid_cached_forecast():
    weather, http, clock = provider()
    weather.get(ARRIVAL, [DESTINATION])
    clock.advance(901)
    http.payload = payload()
    http.payload.update(latitude=0, longitude=0)
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "stale"
    assert result.last_checked_at == NOW
    assert result.last_attempt_at == NOW + timedelta(seconds=901)
    assert result.forecast["temperature_c"] == 20
    assert any("32.875, -117.250" in text for text in result.limitations)


@pytest.mark.parametrize("missing", [("latitude",), ("longitude",),
                                   ("latitude", "longitude")])
def test_missing_grid_metadata_is_explicitly_unknown(missing):
    document = payload()
    for field in missing:
        del document[field]
    weather, _, _ = provider(document)
    result = weather.get(ARRIVAL, [DESTINATION])
    assert result.status == "available"
    assert result.forecast["temperature_c"] == 20
    assert any("source model-grid location is unknown" in text
               for text in result.limitations)
    assert not any("approximate model-grid forecast near" in text
                   for text in result.limitations)


def test_normal_nearby_model_grid_remains_supported():
    document = payload()
    document.update(latitude=32.872, longitude=-117.223)
    weather, _, _ = provider(document)
    result = weather.get(ARRIVAL, [PARKING])
    assert result.status == "available"
    assert any("32.872, -117.223" in text for text in result.limitations)
