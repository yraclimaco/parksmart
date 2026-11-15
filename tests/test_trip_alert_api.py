"""Shared HTTP/Lambda alerts contract and prediction/source failure isolation."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.alert_schemas import TripAlertsResponse
from src.api.main import create_app
from src.trip_alerts.cache import CachedJSON
from src.trip_alerts.construction import ConstructionProvider, LAYERS
from src.trip_alerts.contracts import AlertTarget, ProviderResult
from src.trip_alerts.service import TripAlertService
from src.trip_alerts.weather import WeatherProvider

ARRIVAL = "2026-11-18T09:30:00-08:00"
REQUEST = {"arrival_time": ARRIVAL, "parking_location_id": "gilman-ps"}
CHECKED = datetime(2026, 11, 13, tzinfo=timezone.utc)


class Provider:
    """Injectable source with explicit status and recorded calls, never network."""

    def __init__(self, status="unavailable", fail=False, wait=None):
        self.status, self.fail, self.wait = status, fail, wait
        self.calls = []
        self.started = Event()

    def get(self, arrival, targets):
        self.calls.append((arrival, targets))
        self.started.set()
        if self.wait is not None:
            assert self.wait.wait(timeout=3)
        if self.fail:
            raise RuntimeError("external failure")
        return ProviderResult(self.status, "Test source", "https://example.test/",
                              CHECKED, CHECKED, limitations=["Fixture, not live data."])


@pytest.fixture
def build(tmp_path):
    """Build an app with real ranking fixtures and injectable alert providers."""
    path = tmp_path / "survey.csv"
    pd.DataFrame([
        dict(record_id=name, facility=name, category="S", subtype="", level="",
             observation_date="2026-10-06", academic_year="2026-2027",
             quarter="Fall", observation_time="10:00", fraction_available=value)
        for name, value in (("Gilman", 0.6), ("Hopkins", 0.4))
    ]).to_csv(path, index=False)

    def factory(weather=None, construction=None, dataset=path):
        service = TripAlertService(weather or Provider(), construction or Provider(
            "no_relevant"))
        return create_app(dataset_path=dataset, trip_alert_service=service), service
    return factory


def test_sources_are_not_called_by_startup_or_recommendations(build):
    weather, construction = Provider(fail=True), Provider("no_relevant")
    app, _ = build(weather, construction)
    parking_request = {"arrival_time": "2026-11-03T10:00:00", "permit_type": "S",
                       "destination": {"name": "Test"}}
    with TestClient(app) as client:
        before = client.post("/recommendations", json=parking_request).json()
        assert before["status"] == "ready"
        assert weather.calls == construction.calls == []
        response = client.post("/trip-alerts", json=REQUEST)
        assert response.status_code == 200
        body = response.json()
        TripAlertsResponse.model_validate(body)
        assert body["weather"]["status"] == "unavailable"
        assert body["weather"]["last_checked_at"] is None
        assert body["construction"]["status"] == "no_relevant"
        assert client.post("/recommendations", json=parking_request).json() == before
        assert body["is_example"] is False
        assert body["arrival_time"] == ARRIVAL
        assert weather.calls[0][1][0].location_id == "gilman-ps"


def test_destination_only_alerts_do_not_require_predictions_or_catalog(build, tmp_path):
    app, _ = build(dataset=tmp_path / "missing.csv")
    with TestClient(app) as client:
        assert client.get("/readiness").status_code == 503
        response = client.post("/trip-alerts", json={
            "arrival_time": ARRIVAL,
            "destination": {"name": "Geisel", "coordinates": {
                "latitude": 32.8811, "longitude": -117.2376}},
        })
        assert response.status_code == 200
        assert response.json()["construction"]["status"] == "no_relevant"


@pytest.mark.parametrize("payload", [
    {"arrival_time": ARRIVAL},
    {"arrival_time": ARRIVAL, "destination": {"name": "Unknown"}},
    {**REQUEST, "arrival_time": "2026-11-18"},
    {**REQUEST, "arrival_time": "2026-03-08T02:30:00"},
    {**REQUEST, "arrival_time": "2026-11-01T01:30:00"},
    {**REQUEST, "unexpected": True},
    {"arrival_time": ARRIVAL, "destination": {"name": "Invalid",
        "coordinates": {"latitude": 91, "longitude": 0}}},
])
def test_invalid_request_never_calls_external_sources(build, payload):
    weather, construction = Provider(), Provider()
    app, _ = build(weather, construction)
    with TestClient(app) as client:
        assert client.post("/trip-alerts", json=payload).status_code == 422
    assert weather.calls == construction.calls == []


def test_unknown_parking_id_and_known_destination_are_not_fuzzy_matched(build):
    weather = Provider()
    app, _ = build(weather)
    with TestClient(app) as client:
        assert client.post("/trip-alerts", json={
            **REQUEST, "parking_location_id": "Gilman"}).status_code == 404
        response = client.post("/trip-alerts", json={
            **REQUEST, "destination": {"name": "Geisel without coordinates"}})
        assert response.status_code == 200
        assert "not geocoded" in " ".join(response.json()["limitations"])
    assert len(weather.calls) == 1


def test_disabled_sources_never_call_providers(build):
    app, service = build()
    service.enabled = False
    with TestClient(app) as client:
        response = client.post("/trip-alerts", json=REQUEST)
    assert response.status_code == 200
    assert service.providers["weather"].calls == []
    assert response.json()["construction"]["status"] == "unavailable"


def test_bounded_parallel_capacity_does_not_queue_more_jobs():
    release = Event()
    weather, construction = Provider(wait=release), Provider(wait=release)
    service = TripAlertService(weather, construction)
    with ThreadPoolExecutor(max_workers=1) as pool:
        pending = pool.submit(service.get, CHECKED, [])
        assert weather.started.wait(timeout=3)
        assert construction.started.wait(timeout=3)
        try:
            busy = service.get(CHECKED, [])
            assert all(value["status"] == "unavailable" for value in busy.values())
            assert len(weather.calls) == len(construction.calls) == 1
        finally:
            release.set()
        pending.result(timeout=3)
    service.close()


@pytest.mark.parametrize("age,status", [(0, "available"), (1000, "stale")])
def test_busy_workers_serve_matching_cached_alerts_without_http(age, status):
    arrival = datetime(2026, 11, 18, 17, 30, tzinfo=timezone.utc)
    end = arrival.replace(hour=18, minute=0)
    target = AlertTarget("parking", "Gilman", 32.88, -117.24, "gilman-ps")
    elapsed = [0]
    cache = CachedJSON(monotonic=lambda: elapsed[0],
                       utcnow=lambda: CHECKED + timedelta(seconds=elapsed[0]))
    calls = []

    class HTTP:
        def get_json(self, url, params=None, deadline=None):
            calls.append(url)
            if "open-meteo" in url:
                return {"latitude": target.latitude, "longitude": target.longitude,
                    "hourly_units": {"time": "unixtime", "temperature_2m": "°C",
                        "apparent_temperature": "°C", "precipitation_probability": "%",
                        "precipitation": "mm", "wind_speed_10m": "km/h",
                        "weather_code": "wmo code"},
                    "hourly": {"time": [int(end.timestamp())],
                        "temperature_2m": [20], "apparent_temperature": [20],
                        "precipitation_probability": [80], "precipitation": [2],
                        "wind_speed_10m": [5], "weather_code": [61]}}
            layer = int(url.split("/")[-2])
            features = [] if layer else [{"attributes": {
                "objectid": 1, "AlertID": "example", "AlertType": "Pedestrian",
                "Subject": "Fixture work", "Status": "Approved",
                "Project_Alert_Status": "APPROVED",
                "Public_Impact_Date": int(CHECKED.timestamp() * 1000),
                "Public_Impact_End_Date": int((end + timedelta(days=1)).timestamp() * 1000),
            }, "geometry": {"x": target.longitude, "y": target.latitude}}]
            return {"geometryType": LAYERS[layer], "features": features,
                    "spatialReference": {"wkid": 4326}}

    http = HTTP()
    providers = (WeatherProvider(http, cache, utcnow=lambda: CHECKED),
                 ConstructionProvider(http, cache))
    expected = [provider.get(arrival, [target]) for provider in providers]
    assert all(result.status == "available" and result.alerts for result in expected)
    before = list(calls)
    elapsed[0] = age
    release = Event()

    class Occupied(Provider):
        def __init__(self, delegate):
            super().__init__(wait=release)
            self.delegate = delegate

        def get(self, arrival, targets):
            super().get(arrival, targets)
            return self.delegate.get(arrival, targets)

        def get_cached(self, arrival, targets):
            return self.delegate.get_cached(arrival, targets)

    weather, construction = [Occupied(provider) for provider in providers]
    service = TripAlertService(weather, construction)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            pending = pool.submit(service.get, arrival, [target])
            assert weather.started.wait(timeout=3) and construction.started.wait(timeout=3)
            try:
                cached = service.get(arrival, [target])
                assert all(result["status"] == status for result in cached.values())
                assert all(result["alerts"] for result in cached.values())
                assert calls == before
                for name, original in zip(("weather", "construction"), expected):
                    assert cached[name]["last_checked_at"] == original.last_checked_at
                    assert cached[name]["last_attempt_at"] == original.last_attempt_at
                    assert cached[name]["alerts"][0]["locations"][0]["location_id"] == (
                        target.location_id)
            finally:
                release.set()
            pending.result(timeout=3)
    finally:
        release.set()
        service.close()


def test_source_timeout_retains_slots_until_workers_finish(monkeypatch):
    import src.trip_alerts.service as module
    release = Event()
    service = TripAlertService(Provider("no_relevant", wait=release),
                               Provider("no_relevant", wait=release))
    monkeypatch.setattr(module, "ALERT_REQUEST_BUDGET_SECONDS", 0.01)
    submitted = []
    original = service._pool.submit

    def record(*args):
        future = original(*args)
        submitted.append(future)
        return future

    monkeypatch.setattr(service._pool, "submit", record)
    try:
        expired = service.get(CHECKED, [])
        assert all(item["status"] == "unavailable" for item in expired.values())
        assert all("budget expired" in item["limitations"][0]
                   for item in expired.values())
        busy = service.get(CHECKED, [])
        assert all("busy" in item["limitations"][0] for item in busy.values())
        completed = [Event() for _ in submitted]
        for future, done in zip(submitted, completed):
            future.add_done_callback(lambda _, done=done: done.set())
        release.set()
        assert all(done.wait(timeout=3) for done in completed)
        monkeypatch.setattr(module, "ALERT_REQUEST_BUDGET_SECONDS", 1)
        resumed = service.get(CHECKED, [])
        assert all(item["status"] == "no_relevant" for item in resumed.values())
    finally:
        release.set()
        service.close()


def test_alert_initialization_failure_does_not_stop_parking(build, tmp_path, monkeypatch):
    import src.api.main as module

    def broken():
        raise RuntimeError("optional HTTP client is unavailable")

    monkeypatch.setattr(module, "TripAlertService", lambda **kwargs: broken())
    with TestClient(create_app(dataset_path=tmp_path / "survey.csv")) as client:
        assert client.get("/readiness").status_code == 200
        response = client.post("/trip-alerts", json=REQUEST)
        assert response.status_code == 200
        assert response.json()["weather"]["status"] == "unavailable"
        parking = client.post("/recommendations", json={
            "arrival_time": "2026-11-03T10:00:00", "permit_type": "S",
            "destination": {"name": "Test"}})
        assert parking.status_code == 200 and parking.json()["status"] == "ready"


def test_lambda_adapter_exposes_same_contract_and_reuses_startup(build, monkeypatch):
    from src.api import lambda_handler, saved_model
    app, service = build()
    monkeypatch.setattr(saved_model, "create_configured_app", lambda: app)
    monkeypatch.setattr(lambda_handler, "_runtime", None)
    event = {
        "version": "2.0", "routeKey": "POST /trip-alerts", "rawPath": "/trip-alerts",
        "rawQueryString": "", "headers": {"host": "example.test",
                                              "content-type": "application/json"},
        "requestContext": {"stage": "$default", "requestId": "alerts-test",
            "http": {"method": "POST", "path": "/trip-alerts",
                     "sourceIp": "127.0.0.1", "protocol": "HTTP/1.1"}},
        "body": json.dumps(REQUEST), "isBase64Encoded": False,
    }
    try:
        for _ in range(2):
            response = lambda_handler.handler(event, SimpleNamespace())
            assert response["statusCode"] == 200
            TripAlertsResponse.model_validate_json(response["body"])
        assert len(service.providers["weather"].calls) == 2
    finally:
        runtime = lambda_handler._runtime
        if runtime:
            runtime.loop.run_until_complete(runtime.lifespan.__aexit__(None, None, None))
            runtime.loop.close()
