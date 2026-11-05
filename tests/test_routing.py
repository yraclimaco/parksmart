"""Tests for src.routing providers, caching and the POST /routes endpoint.

No test reaches a real routing provider: httpx.MockTransport stands in for
OpenRouteService and OSRM, and endpoint tests inject a fake provider.
"""

import json

import httpx
import pytest
from fastapi.testclient import TestClient

from src.api.main import create_app
from src.routing import (
    FOSSGIS_OSRM_URLS, MAX_TRIP_KM, NoRouteFound, OpenRouteServiceProvider,
    OsrmProvider, Point, Route, RouteService, RoutingError, provider_from_env,
    straight_line_km,
)

GILMAN = Point(32.87756239, -117.23365383)
GEISEL = Point(32.8811, -117.2376)
DOWNTOWN = Point(32.7157, -117.1611)
LOS_ANGELES = Point(34.0522, -118.2437)
LINE = [[GILMAN.longitude, GILMAN.latitude], [GEISEL.longitude, GEISEL.latitude]]


def client_returning(status, body, seen=None):
    """httpx.Client whose every request gets one canned response."""
    def handler(request):
        if seen is not None:
            seen.append(request)
        content = body if isinstance(body, str) else json.dumps(body)
        return httpx.Response(status, text=content)
    return httpx.Client(transport=httpx.MockTransport(handler))


def ors_body(distance=812.4, duration=583.0, line=LINE):
    """Minimal OpenRouteService GeoJSON directions response."""
    return {"type": "FeatureCollection", "features": [{
        "geometry": {"type": "LineString", "coordinates": line},
        "properties": {"summary": {"distance": distance, "duration": duration}},
    }]}


def osrm_body(distance=812.4, duration=583.0, line=LINE, code="Ok"):
    """Minimal OSRM route response."""
    return {"code": code, "routes": [{
        "distance": distance, "duration": duration,
        "geometry": {"type": "LineString", "coordinates": line},
    }]}


class FakeProvider:
    """Provider double that counts calls and returns or raises on demand."""

    name = "osrm"

    def __init__(self, error=None):
        self.calls = 0
        self.error = error

    def route(self, mode, origin, destination):
        self.calls += 1
        if self.error:
            raise self.error
        return Route(mode=mode, distance_meters=812.4, duration_seconds=583.0,
                     geometry=LINE, provider=self.name)


# Providers ---------------------------------------------------------------

def test_ors_sends_key_in_header_and_lon_lat_order():
    seen = []
    provider = OpenRouteServiceProvider("secret-key", client_returning(200, ors_body(), seen))
    route = provider.route("walking", GILMAN, GEISEL)
    request = seen[0]
    assert request.url.path == "/v2/directions/foot-walking/geojson"
    assert request.headers["Authorization"] == "secret-key"
    assert "secret-key" not in str(request.url)
    assert json.loads(request.content)["coordinates"] == LINE
    assert (route.distance_meters, route.duration_seconds) == (812.4, 583.0)
    assert route.geometry == LINE and route.mode == "walking"


def test_ors_uses_driving_profile():
    seen = []
    OpenRouteServiceProvider("k", client_returning(200, ors_body(), seen)).route(
        "driving", DOWNTOWN, GILMAN)
    assert seen[0].url.path == "/v2/directions/driving-car/geojson"


def test_ors_requires_a_key():
    with pytest.raises(ValueError, match="ORS_API_KEY"):
        OpenRouteServiceProvider("")


def test_ors_404_means_no_route():
    provider = OpenRouteServiceProvider("k", client_returning(404, {"error": {"code": 2010}}))
    with pytest.raises(NoRouteFound):
        provider.route("walking", GILMAN, GEISEL)


@pytest.mark.parametrize("status, body", [
    (403, {"error": "Access to this API has been disallowed"}),
    (429, {"error": "Rate limit exceeded"}),
    (500, "oops"),
    (200, "not json"),
    (200, {"features": []}),
    (200, ors_body(line=[LINE[0]])),
    (200, ors_body(distance=-1)),
    (200, ors_body(duration="soon")),
])
def test_ors_problems_raise_routing_error(status, body):
    provider = OpenRouteServiceProvider("k", client_returning(status, body))
    with pytest.raises(RoutingError):
        provider.route("walking", GILMAN, GEISEL)


def test_ors_network_failure_raises_routing_error():
    def handler(request):
        raise httpx.ConnectTimeout("timed out", request=request)
    provider = OpenRouteServiceProvider("k", httpx.Client(transport=httpx.MockTransport(handler)))
    with pytest.raises(RoutingError):
        provider.route("walking", GILMAN, GEISEL)


def test_osrm_uses_one_server_per_mode_and_geojson():
    seen = []
    provider = OsrmProvider(client=client_returning(200, osrm_body(), seen))
    provider.route("walking", GILMAN, GEISEL)
    provider.route("driving", DOWNTOWN, GILMAN)
    walk, drive = seen
    assert str(walk.url).startswith(FOSSGIS_OSRM_URLS["walking"] + "/route/v1/driving/")
    points = f"{GILMAN.longitude},{GILMAN.latitude};{GEISEL.longitude},{GEISEL.latitude}"
    assert points in walk.url.path
    assert walk.url.params["geometries"] == "geojson"
    assert walk.url.params["overview"] == "full"
    assert str(drive.url).startswith(FOSSGIS_OSRM_URLS["driving"])
    assert "ParkSmart" in walk.headers["User-Agent"]


def test_osrm_no_route():
    provider = OsrmProvider(client=client_returning(400, {"code": "NoRoute"}))
    with pytest.raises(NoRouteFound):
        provider.route("walking", GILMAN, GEISEL)


@pytest.mark.parametrize("status, body", [
    (429, "Too Many Requests"),
    (500, {"code": "InvalidQuery"}),
    (200, {"code": "Ok", "routes": []}),
    (200, osrm_body(distance=float("nan"))),
])
def test_osrm_problems_raise_routing_error(status, body):
    provider = OsrmProvider(client=client_returning(status, body))
    with pytest.raises(RoutingError):
        provider.route("walking", GILMAN, GEISEL)


# Service -----------------------------------------------------------------

def test_straight_line_distance_is_sensible():
    assert straight_line_km(GILMAN, GEISEL) == pytest.approx(0.53, abs=0.05)
    assert straight_line_km(GEISEL, GEISEL) == 0


def test_service_caches_repeat_trips():
    provider = FakeProvider()
    service = RouteService(provider)
    first = service.route("walking", GILMAN, GEISEL)
    # Differences below about a metre reuse the cached route
    again = service.route("walking", Point(GILMAN.latitude + 1e-7, GILMAN.longitude), GEISEL)
    assert again is first and provider.calls == 1
    service.route("driving", GILMAN, GEISEL)
    assert provider.calls == 2


def test_service_cache_drops_least_recent():
    provider = FakeProvider()
    service = RouteService(provider, max_entries=1)
    service.route("walking", GILMAN, GEISEL)
    service.route("walking", GEISEL, GILMAN)
    service.route("walking", GILMAN, GEISEL)
    assert provider.calls == 3


def test_service_does_not_cache_failures():
    provider = FakeProvider(error=RoutingError("down"))
    service = RouteService(provider)
    for _ in range(2):
        with pytest.raises(RoutingError):
            service.route("walking", GILMAN, GEISEL)
    assert provider.calls == 2


def test_service_limits_trip_length_per_mode():
    provider = FakeProvider()
    service = RouteService(provider)
    with pytest.raises(ValueError, match="Walking routes are limited"):
        service.route("walking", DOWNTOWN, GILMAN)
    with pytest.raises(ValueError, match="Driving routes are limited"):
        service.route("driving", LOS_ANGELES, GILMAN)
    assert straight_line_km(DOWNTOWN, GILMAN) < MAX_TRIP_KM["driving"]
    service.route("driving", DOWNTOWN, GILMAN)
    assert provider.calls == 1


def test_service_without_provider():
    service = RouteService(None)
    assert not service.enabled
    with pytest.raises(RuntimeError):
        service.route("walking", GILMAN, GEISEL)


# Configuration -----------------------------------------------------------

def test_provider_from_env_defaults_to_public_osrm_without_key():
    provider = provider_from_env({})
    assert isinstance(provider, OsrmProvider)
    assert provider._urls == FOSSGIS_OSRM_URLS


def test_provider_from_env_uses_ors_when_key_present():
    assert isinstance(provider_from_env({"ORS_API_KEY": "k"}), OpenRouteServiceProvider)


def test_provider_from_env_ors_without_key_is_off():
    assert provider_from_env({"PARKSMART_ROUTING_PROVIDER": "ors"}) is None


def test_provider_from_env_osrm_only_when_chosen():
    provider = provider_from_env({"PARKSMART_ROUTING_PROVIDER": "OSRM",
                                  "OSRM_WALKING_URL": "http://localhost:5001/"})
    assert isinstance(provider, OsrmProvider)
    assert provider._urls["walking"] == "http://localhost:5001"
    assert provider._urls["driving"] == FOSSGIS_OSRM_URLS["driving"]


def test_provider_from_env_none_and_unknown():
    assert provider_from_env({"PARKSMART_ROUTING_PROVIDER": "none", "ORS_API_KEY": "k"}) is None
    with pytest.raises(ValueError, match="Unknown"):
        provider_from_env({"PARKSMART_ROUTING_PROVIDER": "google"})


# Endpoint ----------------------------------------------------------------

def api(service, tmp_path):
    """TestClient with no dataset (recommendations 503) and the given routes."""
    app = create_app(dataset_path=tmp_path / "missing.csv", route_service=service)
    return TestClient(app)


def trip(mode="walking", origin=GILMAN, destination=GEISEL):
    """POST /routes JSON body."""
    return {"mode": mode,
            "origin": {"latitude": origin.latitude, "longitude": origin.longitude},
            "destination": {"latitude": destination.latitude, "longitude": destination.longitude}}


def test_routes_endpoint_returns_drawable_route(tmp_path):
    with api(RouteService(FakeProvider()), tmp_path) as client:
        response = client.post("/routes", json=trip())
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "walking"
    assert body["geometry"] == LINE
    assert body["distance_meters"] == 812.4
    assert body["distance_miles"] == pytest.approx(0.5, abs=0.01)
    assert body["duration_minutes"] == pytest.approx(9.7)
    assert body["traffic_aware"] is False
    assert "OpenStreetMap" in body["attribution"]
    assert any("pedestrian exit" in note for note in body["limitations"])


def test_driving_route_says_no_live_traffic(tmp_path):
    with api(RouteService(FakeProvider()), tmp_path) as client:
        body = client.post("/routes", json=trip("driving", DOWNTOWN, GILMAN)).json()
    assert any("without live traffic" in note for note in body["limitations"])
    assert any("vehicle entrance" in note for note in body["limitations"])


@pytest.mark.parametrize("service, body, status", [
    (RouteService(None), trip(), 503),
    (RouteService(FakeProvider()), trip(origin=DOWNTOWN), 400),
    (RouteService(FakeProvider(error=NoRouteFound("none"))), trip(), 404),
    (RouteService(FakeProvider(error=RoutingError("down"))), trip(), 502),
    (RouteService(FakeProvider()), {**trip(), "mode": "flying"}, 422),
    (RouteService(FakeProvider()), {**trip(), "origin": {"latitude": 95, "longitude": 0}}, 422),
])
def test_routes_endpoint_errors(service, body, status, tmp_path):
    with api(service, tmp_path) as client:
        response = client.post("/routes", json=body)
    assert response.status_code == status
    assert response.json()["detail"]


def test_provider_errors_are_not_leaked(tmp_path):
    service = RouteService(FakeProvider(error=RoutingError("HTTP 403 key=abc123")))
    with api(service, tmp_path) as client:
        detail = client.post("/routes", json=trip()).json()["detail"]
    assert "abc123" not in detail


def test_app_reads_routing_config_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv("PARKSMART_ROUTING_PROVIDER", "none")
    app = create_app(dataset_path=tmp_path / "missing.csv")
    with TestClient(app) as client:
        assert client.post("/routes", json=trip()).status_code == 503
        # Recommendations' health is independent of routing
        assert client.get("/health").status_code == 200


def test_bad_routing_config_disables_routes_only(tmp_path, monkeypatch):
    monkeypatch.setenv("PARKSMART_ROUTING_PROVIDER", "google")
    app = create_app(dataset_path=tmp_path / "missing.csv")
    with TestClient(app) as client:
        assert client.post("/routes", json=trip()).status_code == 503
        assert client.get("/health").status_code == 200


# walk_router (routed walking for ranking) ---------------------------------

from src.routing import walk_router  # noqa: E402

ORIGINS = {"gilman-ps": {"latitude": GILMAN.latitude, "longitude": GILMAN.longitude}}
DEST = {"latitude": GEISEL.latitude, "longitude": GEISEL.longitude}


def test_walk_router_is_none_when_routing_is_off():
    assert walk_router(None) is None
    assert walk_router(RouteService(None)) is None


def test_walk_router_rounds_minutes_up():
    route_walks = walk_router(RouteService(FakeProvider()))
    assert route_walks(ORIGINS, DEST) == {"gilman-ps": 10}  # 583 s = 9.7 min


def test_walk_router_leaves_out_failures():
    for error in (NoRouteFound("x"), RoutingError("x")):
        route_walks = walk_router(RouteService(FakeProvider(error=error)))
        assert route_walks(ORIGINS, DEST) == {}


def test_walk_router_gives_up_after_budget():
    import threading
    release = threading.Event()

    class SlowProvider(FakeProvider):
        def route(self, mode, origin, destination):
            release.wait(5)
            return super().route(mode, origin, destination)

    route_walks = walk_router(RouteService(SlowProvider()), budget_seconds=0.1)
    assert route_walks(ORIGINS, DEST) == {}
    release.set()


def test_recommendations_use_routed_walks_when_routing_is_on(tmp_path):
    """End to end through the API with the real registry and a fake provider."""
    from pathlib import Path
    dataset = Path("data/processed/pipeline/analysis_dataset.csv")
    if not dataset.exists():
        pytest.skip("integrated dataset not built")
    provider = FakeProvider()
    app = create_app(route_service=RouteService(provider))
    body = {"destination": {"name": "Geisel", "coordinates": {
                "latitude": GEISEL.latitude, "longitude": GEISEL.longitude}},
            "arrival_time": "2026-11-10T10:00:00", "permit_type": "S"}
    with TestClient(app) as client:
        data = client.post("/recommendations", json=body).json()
    assert data["status"] == "ready"
    assert data["first_choice"]["estimated_walking_minutes"] == 10
    assert "walking route" in data["first_choice"]["explanation"]
    assert 0 < provider.calls <= 5
