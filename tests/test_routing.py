"""Tests for src.routing providers, caching and the POST /routes endpoint.

No test reaches a real routing provider: httpx.MockTransport stands in for
OpenRouteService and OSRM, and endpoint tests inject a fake provider.
"""

import json
import math

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

    def route(self, mode, origin, destination, deadline=None):
        self.calls += 1
        if self.error:
            raise self.error
        line = [[origin.longitude, origin.latitude],
                [destination.longitude, destination.latitude]]
        return Route(mode=mode, distance_meters=812.4, duration_seconds=583.0,
                     geometry=line, provider=self.name)


# Providers ---------------------------------------------------------------

def test_ors_sends_key_in_header_and_lon_lat_order():
    seen = []
    provider = OpenRouteServiceProvider("secret-key", client_returning(200, ors_body(), seen),
                                        throttle=None)
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
    OpenRouteServiceProvider("k", client_returning(200, ors_body(), seen), throttle=None).route(
        "driving", DOWNTOWN, GILMAN)
    assert seen[0].url.path == "/v2/directions/driving-car/geojson"


def test_ors_requires_a_key():
    with pytest.raises(ValueError, match="ORS_API_KEY"):
        OpenRouteServiceProvider("")


def test_ors_404_means_no_route():
    provider = OpenRouteServiceProvider("k", client_returning(404, {"error": {"code": 2010}}),
                                        throttle=None)
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
    provider = OpenRouteServiceProvider("k", client_returning(status, body), throttle=None)
    with pytest.raises(RoutingError):
        provider.route("walking", GILMAN, GEISEL)


def test_ors_network_failure_raises_routing_error():
    def handler(request):
        raise httpx.ConnectTimeout("timed out", request=request)
    provider = OpenRouteServiceProvider("k", httpx.Client(transport=httpx.MockTransport(handler)),
                                        throttle=None)
    with pytest.raises(RoutingError):
        provider.route("walking", GILMAN, GEISEL)


def test_osrm_uses_one_server_per_mode_and_geojson():
    seen = []
    provider = OsrmProvider(client=client_returning(200, osrm_body(), seen), throttle=None)
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
    provider = OsrmProvider(client=client_returning(400, {"code": "NoRoute"}), throttle=None)
    with pytest.raises(NoRouteFound):
        provider.route("walking", GILMAN, GEISEL)


@pytest.mark.parametrize("status, body", [
    (429, "Too Many Requests"),
    (500, {"code": "InvalidQuery"}),
    (200, {"code": "Ok", "routes": []}),
    (200, osrm_body(distance=float("nan"))),
])
def test_osrm_problems_raise_routing_error(status, body):
    provider = OsrmProvider(client=client_returning(status, body), throttle=None)
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
        def route(self, mode, origin, destination, deadline=None):
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


# Review fixes: TLS, throttling, snapping, budget, logging -----------------

import logging  # noqa: E402
import ssl  # noqa: E402

from src import routing  # noqa: E402
from src.routing import (  # noqa: E402
    FOSSGIS_HOST, MAX_SNAP_METERS, RequestThrottle, TlsUnsupported,
)


class FakeClock:
    """Monotonic clock whose sleep just advances time."""

    def __init__(self):
        self.now = 100.0
        self.sleeps = []

    def __call__(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_throttle_spaces_request_starts():
    clock = FakeClock()
    throttle = RequestThrottle(1.0, max_wait=5, clock=clock, sleep=clock.sleep)
    for _ in range(3):
        throttle.acquire()
    assert clock.sleeps == [1.0, 1.0]


def test_throttle_fails_fast_when_queue_is_too_long():
    clock = FakeClock()
    throttle = RequestThrottle(1.0, max_wait=1.5, clock=clock, sleep=lambda s: None)
    throttle.acquire()  # now
    throttle.acquire()  # +1 s
    with pytest.raises(RoutingError, match="busy"):
        throttle.acquire()  # would be +2 s


def test_public_osrm_shares_one_throttle_across_modes_and_providers():
    first, second = OsrmProvider(), OsrmProvider()
    throttles = {id(t) for p in (first, second) for t in p._throttles.values()}
    assert len(throttles) == 1
    assert first._throttles["walking"].min_interval == routing.FOSSGIS_MIN_INTERVAL_SECONDS


def test_self_hosted_osrm_is_not_throttled():
    provider = OsrmProvider({"driving": "http://osrm-car:5000",
                             "walking": "http://osrm-foot:5000"})
    assert provider._throttles == {"driving": None, "walking": None}
    assert not provider.uses_public_servers


def test_throttle_is_used_for_every_osrm_request():
    acquired = []

    class CountingThrottle:
        def acquire(self, deadline=None):
            acquired.append(1)

    provider = OsrmProvider(client=client_returning(200, osrm_body()),
                            throttle=CountingThrottle())
    provider.route("walking", GILMAN, GEISEL)
    provider.route("driving", DOWNTOWN, GILMAN)
    assert len(acquired) == 2


def test_public_osrm_without_tls13_turns_routing_off_with_warning(monkeypatch, caplog):
    monkeypatch.setattr(routing, "tls13_supported", lambda: False)
    with caplog.at_level(logging.WARNING, logger="src.routing"):
        assert provider_from_env({}) is None
    assert "TLS 1.3" in caplog.text and FOSSGIS_HOST in caplog.text
    # Self-hosted OSRM and ORS do not need TLS 1.3
    assert provider_from_env({"OSRM_DRIVING_URL": "http://a", "OSRM_WALKING_URL": "http://b",
                              "PARKSMART_ROUTING_PROVIDER": "osrm"}) is not None
    assert provider_from_env({"ORS_API_KEY": "k"}) is not None


def _ssl_error(reason, cls=ssl.SSLError):
    """An SSL error like OpenSSL raises, with ``reason`` set."""
    error = cls(1, f"[SSL: {reason}] {reason.lower()} (_ssl.c:1000)")
    error.reason = reason
    return error


def _tls_failing_client(reason="TLSV1_ALERT_PROTOCOL_VERSION", cls=ssl.SSLError):
    """httpx client whose every request fails with this SSL error."""
    def handler(request):
        raise httpx.ConnectError("TLS failed") from _ssl_error(reason, cls)
    return httpx.Client(transport=httpx.MockTransport(handler))


def test_tls_handshake_failure_is_recognized():
    provider = OsrmProvider(client=_tls_failing_client(), throttle=None)
    with pytest.raises(TlsUnsupported):
        provider.route("walking", GILMAN, GEISEL)


def test_tls_failure_turns_routing_off_once_instead_of_failing_repeatedly(caplog):
    provider = OsrmProvider(client=_tls_failing_client(), throttle=None)
    calls = []
    original = provider.route
    provider.route = lambda *args, **kwargs: calls.append(1) or original(*args, **kwargs)
    service = RouteService(provider)
    with caplog.at_level(logging.WARNING, logger="src.routing"):
        for _ in range(3):
            with pytest.raises(RuntimeError, match="TLS"):
                service.route("walking", GILMAN, GEISEL)
    assert len(calls) == 1
    assert not service.enabled
    assert caplog.text.count("Routes turned off") == 1


def test_routes_endpoint_says_unavailable_after_tls_failure(tmp_path):
    service = RouteService(OsrmProvider(client=_tls_failing_client(), throttle=None))
    with api(service, tmp_path) as client:
        first = client.post("/routes", json=trip())
        second = client.post("/routes", json=trip())
    assert first.status_code == second.status_code == 503
    assert "SSL" not in first.text


class SnappingProvider(FakeProvider):
    """Provider whose route starts ``offset`` degrees of latitude off."""

    def __init__(self, offset):
        super().__init__()
        self.offset = offset

    def route(self, mode, origin, destination, deadline=None):
        self.calls += 1
        line = [[origin.longitude, origin.latitude + self.offset],
                [destination.longitude, destination.latitude]]
        return Route(mode=mode, distance_meters=900.0, duration_seconds=600.0,
                     geometry=line, provider=self.name)


def test_small_snapping_is_accepted():
    service = RouteService(SnappingProvider(offset=0.0005))  # about 56 m
    assert service.route("walking", GILMAN, GEISEL).duration_seconds == 600.0


def test_excessive_snapping_is_rejected_and_remembered():
    provider = SnappingProvider(offset=0.005)  # about 556 m
    service = RouteService(provider)
    with pytest.raises(NoRouteFound, match=r"556 m from the start point"):
        service.route("walking", GILMAN, GEISEL)
    with pytest.raises(NoRouteFound, match=r"556 m"):
        service.route("walking", GILMAN, GEISEL)
    assert provider.calls == 1  # the impossible trip is not asked again
    assert MAX_SNAP_METERS["walking"] < 556 < 1000


def test_routes_endpoint_reports_excessive_snapping_as_no_route(tmp_path):
    with api(RouteService(SnappingProvider(offset=0.005)), tmp_path) as client:
        response = client.post("/routes", json=trip())
    assert response.status_code == 404
    assert "nearest mapped path" in response.json()["detail"]


def test_walk_router_budget_is_shared_by_every_call():
    route_walks = walk_router(RouteService(FakeProvider()), budget_seconds=0.2)
    assert route_walks(ORIGINS, DEST) == {"gilman-ps": 10}
    import time
    time.sleep(0.25)
    other = {"scholars": {"latitude": 32.8789, "longitude": -117.2416}}
    assert route_walks(other, DEST) == {}


def test_walk_router_warns_when_every_route_fails(caplog):
    route_walks = walk_router(RouteService(FakeProvider(error=RoutingError("HTTP 500"))))
    with caplog.at_level(logging.WARNING, logger="src.routing"):
        assert route_walks(ORIGINS, DEST) == {}
    assert "All 1 walking-route attempts failed" in caplog.text
    assert "HTTP 500" in caplog.text


def test_walk_router_does_not_warn_when_some_routes_work(caplog):
    route_walks = walk_router(RouteService(FakeProvider()))
    with caplog.at_level(logging.WARNING, logger="src.routing"):
        route_walks(ORIGINS, DEST)
    assert "walking-route attempts failed" not in caplog.text


# Second review: request deadlines, SSL classification, geometry, snapping ---

import time  # noqa: E402

from src.routing import (  # noqa: E402
    ROUTE_REQUEST_BUDGET_SECONDS, DeadlineExceeded, tls_problem,
)


def test_throttle_refuses_slots_after_the_deadline_without_reserving_them():
    clock = FakeClock()
    throttle = RequestThrottle(1.0, max_wait=10, clock=clock, sleep=lambda s: None)
    throttle.acquire()                       # slot at t
    with pytest.raises(DeadlineExceeded):
        throttle.acquire(deadline=clock.now + 0.5)  # next slot t+1 is too late
    throttle.acquire()                       # the refused call reserved nothing
    assert throttle._next_start == pytest.approx(clock.now + 2.0)


def _timed_osrm(starts, interval):
    """OSRM provider on a mock server that records when each request starts."""
    def handler(request):
        starts.append(time.monotonic())
        return httpx.Response(200, text=json.dumps(osrm_body(line=[
            [GILMAN.longitude, GILMAN.latitude], [GEISEL.longitude, GEISEL.latitude]])))
    return OsrmProvider(client=httpx.Client(transport=httpx.MockTransport(handler)),
                        throttle=RequestThrottle(interval))


def test_queued_walking_routes_never_start_after_the_request_deadline():
    # Reproduces the review: a 0.8 s budget with a 0.5 s throttle used to keep
    # starting queued calls after the request had returned.
    starts = []
    provider = _timed_osrm(starts, interval=0.5)
    service = RouteService(provider)
    origins = {f"lot{i}": {"latitude": GILMAN.latitude + i * 0.0005,
                           "longitude": GILMAN.longitude} for i in range(5)}
    began = time.monotonic()
    walk_router(service, budget_seconds=0.8, workers=3)(origins, DEST)
    deadline = began + 0.8
    time.sleep(1.5)  # give any straggler time to (wrongly) start
    assert starts and all(start < deadline for start in starts)
    assert len(starts) == 2  # slots at 0 and 0.5 s; 1.0 s is past the deadline
    # Expired work reserved nothing: the next search's slot is right after the last
    throttle = provider._throttles["walking"]
    assert throttle._next_start <= max(starts) + 0.5 + 0.05


def test_provider_timeout_is_capped_by_the_deadline():
    seen = []
    provider = OsrmProvider(client=client_returning(200, osrm_body(), seen), throttle=None)
    provider.route("walking", GILMAN, GEISEL, deadline=time.monotonic() + 2.0)
    assert seen[0].extensions["timeout"]["read"] <= 2.0
    provider.route("walking", GILMAN, GEISEL)
    assert seen[1].extensions["timeout"]["read"] == routing.PROVIDER_TIMEOUT_SECONDS


def test_expired_deadline_sends_nothing():
    seen = []
    provider = OsrmProvider(client=client_returning(200, osrm_body(), seen),
                            throttle=RequestThrottle(1.0))
    with pytest.raises(DeadlineExceeded):
        provider.route("walking", GILMAN, GEISEL, deadline=time.monotonic() - 0.1)
    assert seen == []


def test_routes_endpoint_gives_each_route_a_bounded_deadline(tmp_path):
    deadlines = []

    class DeadlineProvider(FakeProvider):
        def route(self, mode, origin, destination, deadline=None):
            deadlines.append(deadline - time.monotonic())
            return super().route(mode, origin, destination)

    with api(RouteService(DeadlineProvider()), tmp_path) as client:
        assert client.post("/routes", json=trip()).status_code == 200
    assert 0 < deadlines[0] <= ROUTE_REQUEST_BUDGET_SECONDS
    # Within the website's 12 s route timeout (frontend/src/api/routes.ts)
    assert ROUTE_REQUEST_BUDGET_SECONDS < 12


def _flaky_client(first_error):
    """Fails the first request with ``first_error``, then answers normally."""
    calls = []

    def handler(request):
        calls.append(request)
        if len(calls) == 1:
            raise httpx.ConnectError("TLS failed") from first_error
        return httpx.Response(200, text=json.dumps(osrm_body(line=[
            [GILMAN.longitude, GILMAN.latitude], [GEISEL.longitude, GEISEL.latitude]])))
    return httpx.Client(transport=httpx.MockTransport(handler))


@pytest.mark.parametrize("error, wording", [
    (_ssl_error("CERTIFICATE_VERIFY_FAILED", ssl.SSLCertVerificationError),
     "certificate check failed"),
    (_ssl_error("DECRYPTION_FAILED_OR_BAD_RECORD_MAC"), "TLS connection failed"),
    (_ssl_error("SSLV3_ALERT_HANDSHAKE_FAILURE"), "TLS connection failed"),
])
def test_certificate_and_temporary_ssl_errors_keep_routing_on(error, wording, caplog):
    service = RouteService(OsrmProvider(client=_flaky_client(error), throttle=None))
    with caplog.at_level(logging.WARNING, logger="src.routing"):
        with pytest.raises(RoutingError, match=wording) as raised:
            service.route("walking", GILMAN, GEISEL)
    assert not isinstance(raised.value, TlsUnsupported)
    assert "Python" not in str(raised.value)  # no "upgrade Python" advice
    assert service.enabled
    assert "Routes turned off" not in caplog.text
    # The next request works
    assert service.route("walking", GILMAN, GEISEL).duration_seconds == 583.0


def test_routes_endpoint_recovers_after_a_certificate_error(tmp_path):
    error = _ssl_error("CERTIFICATE_VERIFY_FAILED", ssl.SSLCertVerificationError)
    service = RouteService(OsrmProvider(client=_flaky_client(error), throttle=None))
    with api(service, tmp_path) as client:
        assert client.post("/routes", json=trip()).status_code == 502
        assert client.post("/routes", json=trip()).status_code == 200


def test_handshake_failure_only_counts_as_unsupported_without_tls13(monkeypatch):
    failure = httpx.ConnectError("x")
    failure.__cause__ = _ssl_error("SSLV3_ALERT_HANDSHAKE_FAILURE")
    assert tls_problem(failure) == "other"
    monkeypatch.setattr(routing, "tls13_supported", lambda: False)
    assert tls_problem(failure) == "unsupported"


def test_tls_problem_classes():
    def wrapped(cause):
        error = httpx.ConnectError("x")
        error.__cause__ = cause
        return error
    assert tls_problem(httpx.ConnectError("no ssl")) is None
    assert tls_problem(wrapped(_ssl_error("UNSUPPORTED_PROTOCOL"))) == "unsupported"
    assert tls_problem(wrapped(_ssl_error(
        "CERTIFICATE_VERIFY_FAILED", ssl.SSLCertVerificationError))) == "certificate"


def test_certificates_are_always_verified():
    # Providers never build clients with verification turned off
    import inspect
    assert "verify=False" not in inspect.getsource(routing)


@pytest.mark.parametrize("line", [
    [[GILMAN.longitude, GILMAN.latitude], [float("nan"), GEISEL.latitude]],
    [[GILMAN.longitude, GILMAN.latitude], [GEISEL.longitude, float("inf")]],
    [[GILMAN.longitude, GILMAN.latitude], [200.0, GEISEL.latitude]],
    [[GILMAN.longitude, GILMAN.latitude], [GEISEL.longitude]],
    [[GILMAN.longitude, GILMAN.latitude], "not a pair"],
    [[GILMAN.longitude, GILMAN.latitude], [None, GEISEL.latitude]],
])
def test_malformed_or_non_finite_geometry_is_rejected(line):
    body = json.dumps(osrm_body(line=line)).replace("NaN", "NaN")
    provider = OsrmProvider(client=client_returning(200, body), throttle=None)
    with pytest.raises(RoutingError, match="geometry"):
        provider.route("walking", GILMAN, GEISEL)


METERS_PER_DEGREE_LATITUDE = 111_195


@pytest.mark.parametrize("mode", ["walking", "driving"])
@pytest.mark.parametrize("margin, accepted", [(-5, True), (5, False)])
def test_snapping_limit_boundary_for_each_mode(mode, margin, accepted):
    offset = (MAX_SNAP_METERS[mode] + margin) / METERS_PER_DEGREE_LATITUDE
    service = RouteService(SnappingProvider(offset=offset))
    if accepted:
        assert service.route(mode, GILMAN, GEISEL)
    else:
        with pytest.raises(NoRouteFound, match="nearest mapped"):
            service.route(mode, GILMAN, GEISEL)


def test_no_call_starts_with_almost_no_budget_left():
    seen = []
    throttle = RequestThrottle(1.0)
    provider = OsrmProvider(client=client_returning(200, osrm_body(), seen), throttle=throttle)
    nearly_over = time.monotonic() + routing.MIN_PROVIDER_SECONDS / 2
    with pytest.raises(DeadlineExceeded):
        provider.route("walking", GILMAN, GEISEL, deadline=nearly_over)
    assert seen == [] and throttle._next_start == -math.inf  # no slot taken



# Code review fixes ------------------------------------------------------------

from src.routing import display_minutes, route_minutes  # noqa: E402


def _route_of(seconds):
    return Route(mode="walking", distance_meters=500.0, duration_seconds=seconds,
                 geometry=LINE, provider="osrm")


@pytest.mark.parametrize("seconds, minutes", [(421, 7), (7 * 60 + 4, 8), (30, 1), (0, 1)])
def test_card_minutes_match_the_directions_box(seconds, minutes):
    # The website shows max(1, ceil(duration_minutes)) from POST /routes
    route = _route_of(seconds)
    assert display_minutes(route) == max(1, math.ceil(route_minutes(route))) == minutes


def test_routes_endpoint_and_ranking_use_the_same_minutes(tmp_path):
    class SecondsProvider(FakeProvider):
        def route(self, mode, origin, destination, deadline=None):
            line = [[origin.longitude, origin.latitude],
                    [destination.longitude, destination.latitude]]
            return Route(mode=mode, distance_meters=500.0, duration_seconds=422.0,
                         geometry=line, provider=self.name)

    service = RouteService(SecondsProvider())
    with api(service, tmp_path) as client:
        shown = client.post("/routes", json=trip()).json()["duration_minutes"]
    assert walk_router(service)(ORIGINS, DEST)["gilman-ps"] == max(1, math.ceil(shown))


def test_no_route_answers_are_remembered_then_expire(monkeypatch):
    provider = FakeProvider(error=NoRouteFound("no path"))
    service = RouteService(provider)
    for _ in range(3):
        with pytest.raises(NoRouteFound, match="no path"):
            service.route("walking", GILMAN, GEISEL)
    assert provider.calls == 1
    monkeypatch.setattr(routing, "NO_ROUTE_CACHE_SECONDS", -1.0)
    service._no_route.clear()
    for _ in range(2):
        with pytest.raises(NoRouteFound):
            service.route("walking", GILMAN, GEISEL)
    assert provider.calls == 3  # expired entries are asked again


def test_provider_errors_are_not_remembered():
    provider = FakeProvider(error=RoutingError("HTTP 500"))
    service = RouteService(provider)
    for _ in range(2):
        with pytest.raises(RoutingError):
            service.route("walking", GILMAN, GEISEL)
    assert provider.calls == 2


def test_gate_is_only_taken_when_the_provider_is_called():
    taken = []

    class CountingGate:
        def acquire(self, deadline=None):
            taken.append(deadline)

    service = RouteService(FakeProvider())
    for _ in range(3):
        service.route("walking", GILMAN, GEISEL, gate=CountingGate())
    assert len(taken) == 1  # repeats come from the cache


def test_routes_endpoint_caps_its_share_of_provider_calls(tmp_path, monkeypatch):
    monkeypatch.setattr("src.api.main.ROUTES_ENDPOINT_MIN_INTERVAL_SECONDS", 0.4)
    provider = FakeProvider()
    provider.rate_limited = True  # like the public FOSSGIS servers
    with api(RouteService(provider), tmp_path) as client:
        began = time.monotonic()
        for i in range(3):  # distinct, uncached trips
            body = trip(origin=Point(GILMAN.latitude + i * 0.0003, GILMAN.longitude))
            assert client.post("/routes", json=body).status_code == 200
        elapsed = time.monotonic() - began
        again = time.monotonic()
        assert client.post("/routes", json=trip(
            origin=Point(GILMAN.latitude, GILMAN.longitude))).status_code == 200
        cached = time.monotonic() - again
    assert elapsed >= 0.8 - 0.05  # 3 provider calls, 0.4 s apart
    assert cached < 0.2  # cached trips are not gated


def test_ors_shares_a_quota_throttle_and_respects_the_deadline():
    first = OpenRouteServiceProvider("k", client_returning(200, ors_body()))
    second = OpenRouteServiceProvider("k", client_returning(200, ors_body()))
    assert first._throttle is second._throttle
    assert first._throttle.min_interval == routing.ORS_MIN_INTERVAL_SECONDS
    seen = []
    provider = OpenRouteServiceProvider("k", client_returning(200, ors_body(), seen),
                                        throttle=RequestThrottle(1.0))
    with pytest.raises(DeadlineExceeded):
        provider.route("walking", GILMAN, GEISEL, deadline=time.monotonic() - 1)
    assert seen == []


@pytest.mark.parametrize("summary", [None, "oops", 5, 0, ""])
def test_ors_missing_or_odd_summary_between_different_points_is_an_error(summary):
    body = ors_body()
    body["features"][0]["properties"]["summary"] = summary
    provider = OpenRouteServiceProvider("k", client_returning(200, body), throttle=None)
    with pytest.raises(RoutingError, match="unreadable"):
        provider.route("walking", GILMAN, GEISEL)


def test_ors_missing_summary_for_the_same_point_is_a_zero_route():
    body = ors_body(line=[[GILMAN.longitude, GILMAN.latitude]] * 2)
    del body["features"][0]["properties"]["summary"]
    provider = OpenRouteServiceProvider("k", client_returning(200, body), throttle=None)
    assert provider.route("walking", GILMAN, GILMAN).duration_seconds == 0


def test_one_unexpected_route_error_keeps_the_other_routes():
    class OneBadProvider(FakeProvider):
        def route(self, mode, origin, destination, deadline=None):
            if origin.latitude > GILMAN.latitude:
                raise AttributeError("bad provider answer")
            return super().route(mode, origin, destination)

    origins = {**ORIGINS, "bad": {"latitude": GILMAN.latitude + 0.001,
                                  "longitude": GILMAN.longitude}}
    minutes = walk_router(RouteService(OneBadProvider()))(origins, DEST)
    assert minutes == {"gilman-ps": 10}



# Second code review --------------------------------------------------------

@pytest.mark.parametrize("code, error", [(2010, NoRouteFound), (2009, NoRouteFound),
                                         (None, RoutingError), (1006, RoutingError)])
def test_only_ors_no_route_codes_mean_no_route(code, error):
    body = {"error": {"code": code}} if code else "<html>Not Found</html>"
    provider = OpenRouteServiceProvider("k", client_returning(404, body), throttle=None)
    with pytest.raises(error) as raised:
        provider.route("walking", GILMAN, GEISEL)
    if error is RoutingError:
        assert not isinstance(raised.value, NoRouteFound)
        assert "base URL" in str(raised.value)


def test_misconfigured_ors_404_is_not_remembered():
    seen = []
    provider = OpenRouteServiceProvider("k", client_returning(404, "nope", seen), throttle=None)
    service = RouteService(provider)
    for _ in range(2):
        with pytest.raises(RoutingError):
            service.route("walking", GILMAN, GEISEL)
    assert len(seen) == 2


def test_ors_interval_leaves_room_under_forty_a_minute():
    assert 60 / routing.ORS_MIN_INTERVAL_SECONDS + 1 < 40


def test_unthrottled_providers_skip_the_routes_gate(tmp_path, monkeypatch):
    monkeypatch.setattr("src.api.main.ROUTES_ENDPOINT_MIN_INTERVAL_SECONDS", 5.0)
    selfhosted = OsrmProvider({"driving": "http://osrm-car:5000",
                               "walking": "http://osrm-foot:5000"},
                              client=client_returning(200, osrm_body()))
    assert not selfhosted.rate_limited
    assert OsrmProvider(client=client_returning(200, osrm_body())).rate_limited
    assert OpenRouteServiceProvider("k", client_returning(200, ors_body())).rate_limited
    with api(RouteService(FakeProvider()), tmp_path) as client:
        began = time.monotonic()
        for i in range(3):
            body = trip(origin=Point(GILMAN.latitude + i * 0.0003, GILMAN.longitude))
            assert client.post("/routes", json=body).status_code == 200
    assert time.monotonic() - began < 1.0


def test_gate_leaves_time_for_the_call():
    taken = []

    class RecordingGate:
        def acquire(self, deadline=None):
            taken.append(deadline)

    deadline = time.monotonic() + 5
    RouteService(FakeProvider()).route("walking", GILMAN, GEISEL, deadline=deadline,
                                       gate=RecordingGate())
    assert taken == [pytest.approx(deadline - routing.MIN_PROVIDER_SECONDS)]


def test_identical_requests_at_once_share_one_provider_call():
    import threading
    release = threading.Event()

    class SlowProvider(FakeProvider):
        def route(self, mode, origin, destination, deadline=None):
            release.wait(2)
            return super().route(mode, origin, destination)

    provider = SlowProvider()
    service = RouteService(provider)
    results = []
    threads = [threading.Thread(target=lambda: results.append(
        service.route("walking", GILMAN, GEISEL, deadline=time.monotonic() + 3)))
        for _ in range(3)]
    for thread in threads:
        thread.start()
    time.sleep(0.2)
    release.set()
    for thread in threads:
        thread.join()
    assert provider.calls == 1 and len(results) == 3


def test_failed_in_flight_request_lets_the_next_one_try():
    provider = FakeProvider(error=RoutingError("HTTP 500"))
    service = RouteService(provider)
    with pytest.raises(RoutingError):
        service.route("walking", GILMAN, GEISEL)
    provider.error = None
    assert service.route("walking", GILMAN, GEISEL)
    assert service._in_flight == {}
