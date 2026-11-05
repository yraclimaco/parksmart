"""Driving and walking routes from a third-party routing provider.

The website and mobile app call the backend's POST /routes, never a provider
directly, so provider keys stay on the server. Two providers are supported:

* ``ors``: OpenRouteService (https://openrouteservice.org). Needs a free API
  key in ``ORS_API_KEY``; the free plan allows 2,000 directions requests a
  day and 40 a minute (checked 2026-11-04 on its plans page).
* ``osrm``: any OSRM server. The default is the public FOSSGIS servers at
  routing.openstreetmap.de, which need no key but allow only light use
  (about one request a second) and offer no uptime guarantee. Fine for
  development, demos and low traffic. Every request to them, from
  recommendations and POST /routes alike, goes through one shared
  per-process throttle (FOSSGIS_MIN_INTERVAL_SECONDS), and the in-memory
  cache keeps calls down. They accept TLS 1.3 only; a Python whose SSL
  library lacks it turns routing off at startup with a warning.

Routing works with no setup: without ``ORS_API_KEY`` the public OSRM servers
are used. Override with ``PARKSMART_ROUTING_PROVIDER`` (``ors``, ``osrm`` or
``none`` to turn routes off).
Neither provider uses live traffic, so durations are typical travel times and
are never described as traffic-aware. Routes are cached in memory so repeated
requests for the same trip do not use provider quota.
"""

from __future__ import annotations

import logging
import math
import os
import ssl
import threading
import time
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Literal, Protocol
from urllib.parse import urlsplit

import httpx

LOGGER = logging.getLogger(__name__)

TravelMode = Literal["driving", "walking"]
TRAVEL_MODES: tuple[TravelMode, ...] = ("driving", "walking")

#: Seconds to wait for a provider before reporting the route as unavailable.
PROVIDER_TIMEOUT_SECONDS = 8.0
#: Longest straight-line trip accepted per mode. Driving covers commutes from
#: across San Diego County; walking covers parking-to-building trips on
#: campus. Longer requests are rejected so the endpoint cannot be used as a
#: general-purpose router that spends the project's quota.
MAX_TRIP_KM: dict[str, float] = {"driving": 150.0, "walking": 5.0}
#: Coordinates are rounded to this many decimals (about 1 m) for caching.
CACHE_COORDINATE_DECIMALS = 5
CACHE_MAX_ENTRIES = 1024
EARTH_RADIUS_KM = 6371.0088
METERS_PER_MILE = 1609.344

#: Furthest a provider may move ("snap") a requested point to reach the
#: nearest mapped road or path. Registry points are building points, so some
#: snapping is normal (the 2026-11-05 check of all 46 supported locations in
#: docs/routing.md found at most 55 m walking and 60 m driving); further means
#: the route does not really start or end where asked, so it is rejected as
#: no route.
MAX_SNAP_METERS: dict[str, float] = {"driving": 250.0, "walking": 150.0}

#: Total time one recommendation request waits for routed walking times, over
#: all its routing rounds, before keeping straight-line estimates. Inside the
#: website's 20 s timeout. With an idle FOSSGIS throttle (1 request a second)
#: it covers the first 5 routes plus a check of the picks; with ORS (one per
#: 1.6 s) or a busy throttle, fewer, and the rest stay labeled unchecked.
WALK_ROUTING_BUDGET_SECONDS = 8.0
#: Parallel walking-route requests per recommendation. The FOSSGIS throttle
#: still spaces their starts one second apart; parallel requests only overlap
#: network time.
WALK_ROUTING_WORKERS = 3

#: Minimum seconds between request starts to the public FOSSGIS servers,
#: across both modes and all requests in this process (their usage policy
#: asks for at most about one request a second).
FOSSGIS_MIN_INTERVAL_SECONDS = 1.0
#: A request that would wait longer than this for its throttle slot fails
#: fast (as a provider error) rather than queueing behind a burst.
THROTTLE_MAX_WAIT_SECONDS = 6.0
#: Total time POST /routes may spend on one route (throttle wait plus
#: provider call), kept under the website's 12 s route timeout
#: (ROUTE_TIMEOUT_MS in frontend/src/api/routes.ts).
ROUTE_REQUEST_BUDGET_SECONDS = 10.0
#: A provider call is only started with at least this much budget left; a
#: shorter call would almost surely time out and just spend a FOSSGIS slot.
MIN_PROVIDER_SECONDS = 0.25
#: Minimum seconds between OpenRouteService requests in this process: its free
#: plan allows 40 directions a minute (checked 2026-11-04); 1.6 s allows at
#: most 38 in any rolling minute. Per process: several workers or Lambda
#: instances each get this budget, so keep one instance while on the free plan.
ORS_MIN_INTERVAL_SECONDS = 1.6
#: OpenRouteService error codes (sent with HTTP 404) that mean "no route":
#: 2009 route not found, 2010 no routable point near a coordinate. Any other
#: 404 is a configuration problem (wrong base URL or profile).
ORS_NO_ROUTE_CODES = frozenset({2009, 2010})
#: ORS omits the route summary only when start and end are the same point;
#: within this distance a missing summary means a 0 m route.
SAME_POINT_METERS = 1.0
#: POST /routes may start a provider call at most this often (process-wide)
#: when the provider is rate limited (public FOSSGIS or ORS). It shares the
#: provider's throttle with recommendations, so this keeps at least half of
#: the FOSSGIS capacity for recommendation walking routes even if someone
#: floods /routes. Cached routes and unthrottled self-hosted servers are not
#: limited.
ROUTES_ENDPOINT_MIN_INTERVAL_SECONDS = 2.0
#: How long "no route" answers (no path, or snapped too far) are remembered,
#: so an impossible trip does not spend a provider call on every search.
NO_ROUTE_CACHE_SECONDS = 3600.0
#: Longest an identical request waits for one already in progress when it has
#: no deadline of its own (throttle wait plus provider timeout).
IN_FLIGHT_WAIT_SECONDS = THROTTLE_MAX_WAIT_SECONDS + PROVIDER_TIMEOUT_SECONDS
#: Decimals of the route duration in minutes, shared by POST /routes and the
#: walking minutes used in ranking so the card and directions box agree.
ROUTE_MINUTES_DECIMALS = 1
#: OpenSSL reasons that mean the client and server share no TLS version, so
#: retrying cannot help. Certificate and other SSL failures are not here.
TLS_PROTOCOL_REASONS = frozenset({
    "UNSUPPORTED_PROTOCOL", "TLSV1_ALERT_PROTOCOL_VERSION",
    "NO_PROTOCOLS_AVAILABLE", "WRONG_SSL_VERSION", "VERSION_TOO_LOW",
})

ORS_BASE_URL = "https://api.openrouteservice.org"
ORS_PROFILES = {"driving": "driving-car", "walking": "foot-walking"}
#: FOSSGIS runs one OSRM server per profile; each serves the path "driving".
FOSSGIS_OSRM_URLS = {
    "driving": "https://routing.openstreetmap.de/routed-car",
    "walking": "https://routing.openstreetmap.de/routed-foot",
}
#: Identifies ParkSmart to public servers, as the FOSSGIS usage policy asks.
USER_AGENT = "ParkSmart/0.2 (UCSD DS3 student project; github.com/yraclimaco/parksmart)"

PROVIDER_LABELS = {"ors": "OpenRouteService", "osrm": "OSRM (OpenStreetMap data)"}
FOSSGIS_HOST = urlsplit(FOSSGIS_OSRM_URLS["walking"]).hostname
TLS13_MISSING = (
    "This Python's SSL library ({version}) has no TLS 1.3, which the public "
    "OSRM servers at {host} require, so routes are turned off. Use Python 3.11+ "
    "built with OpenSSL (see docs/backend.md), or set ORS_API_KEY or a "
    "self-hosted OSRM_*_URL."
)


class RoutingError(Exception):
    """A provider failed, timed out or returned something unreadable."""


class NoRouteFound(Exception):
    """The provider answered but found no route between the two points."""


class TlsUnsupported(RoutingError):
    """Confirmed: this Python and the provider share no TLS version."""


class DeadlineExceeded(RoutingError):
    """The request's time budget ran out before the provider was contacted."""


class RequestThrottle:
    """Spaces request starts at least ``min_interval`` seconds apart.

    Thread-safe; callers reserve the next free slot and sleep until it.

    Args:
        min_interval: seconds between request starts.
        max_wait: longest a caller may wait for a slot.
        clock, sleep: injectable for tests.
    """

    def __init__(self, min_interval: float,
                 max_wait: float = THROTTLE_MAX_WAIT_SECONDS,
                 clock=time.monotonic, sleep=time.sleep):
        self.min_interval = min_interval
        self.max_wait = max_wait
        self._clock = clock
        self._sleep = sleep
        self._next_start = -math.inf
        self._lock = threading.Lock()

    def acquire(self, deadline: float | None = None) -> None:
        """Wait for this caller's slot.

        Args:
            deadline: optional time (same clock) by which the request must
                start; a slot at or after it is refused without being
                reserved, so expired work never delays later searches.
        Raises:
            DeadlineExceeded: the next slot is at or after ``deadline``.
            RoutingError: the slot is more than ``max_wait`` seconds away.
        """
        with self._lock:
            now = self._clock()
            start = max(now, self._next_start)
            if deadline is not None and start >= deadline:
                raise DeadlineExceeded(
                    f"Next routing slot is {start - now:.1f} s away, after this "
                    "request's deadline.")
            if start - now > self.max_wait:
                raise RoutingError(
                    f"Routing provider is busy (next request slot in "
                    f"{start - now:.1f} s).")
            self._next_start = start + self.min_interval
        if start > now:
            self._sleep(start - now)


_SHARED_THROTTLES: dict[str, RequestThrottle] = {}
_SHARED_THROTTLES_LOCK = threading.Lock()


def shared_throttle(host: str, min_interval: float) -> RequestThrottle:
    """Return the one process-wide throttle for ``host``, creating it once."""
    with _SHARED_THROTTLES_LOCK:
        if host not in _SHARED_THROTTLES:
            _SHARED_THROTTLES[host] = RequestThrottle(min_interval)
        return _SHARED_THROTTLES[host]


def tls13_supported() -> bool:
    """True when this Python's SSL library can negotiate TLS 1.3."""
    return bool(getattr(ssl, "HAS_TLSv1_3", False))


def _ssl_cause(error: BaseException) -> ssl.SSLError | None:
    """The ssl.SSLError behind an httpx error, if any."""
    seen = set()
    while error is not None and id(error) not in seen:
        if isinstance(error, ssl.SSLError):
            return error
        seen.add(id(error))
        error = error.__cause__ or error.__context__
    return None


def tls_problem(error: BaseException) -> str | None:
    """Classify an SSL failure behind a request error.

    Returns:
        ``"unsupported"`` only when the client and server confirmably share
        no TLS version (a protocol-version reason, or a handshake failure on
        a Python without TLS 1.3); ``"certificate"`` for a failed certificate
        check; ``"other"`` for any other SSL error, which may be temporary;
        None when SSL was not involved.
    """
    cause = _ssl_cause(error)
    if cause is None:
        return None
    if isinstance(cause, ssl.SSLCertVerificationError):
        return "certificate"
    text = f"{getattr(cause, 'reason', '') or ''} {cause}".upper()
    if any(reason in text for reason in TLS_PROTOCOL_REASONS):
        return "unsupported"
    if "HANDSHAKE_FAILURE" in text and not tls13_supported():
        return "unsupported"
    return "other"


def _request_error(error: httpx.HTTPError, provider: str) -> RoutingError:
    """Turn an httpx failure into the matching RoutingError, naming the cause.

    Certificates are always verified; a certificate failure is reported as
    such and never retried without verification.
    """
    problem = tls_problem(error)
    if problem == "unsupported":
        return TlsUnsupported(
            f"{provider} and this Python's SSL library ({ssl.OPENSSL_VERSION}) "
            f"share no TLS version: {error!r}")
    if problem == "certificate":
        return RoutingError(f"{provider} TLS certificate check failed: {error!r}")
    if problem == "other":
        return RoutingError(f"{provider} TLS connection failed: {error!r}")
    return RoutingError(f"{provider} request failed: {error!r}")


def _time_left(deadline: float | None) -> float:
    """Provider timeout for a request: PROVIDER_TIMEOUT_SECONDS, capped by
    the time left before ``deadline`` (a time.monotonic() value).

    httpx applies it to each network step (connect, send, each read), so a
    slow call can run somewhat past the deadline; callers never wait for it
    beyond the deadline, and it never starts a new request.

    Raises:
        DeadlineExceeded: less than MIN_PROVIDER_SECONDS is left.
    """
    if deadline is None:
        return PROVIDER_TIMEOUT_SECONDS
    left = deadline - time.monotonic()
    if left < MIN_PROVIDER_SECONDS:
        raise DeadlineExceeded("This request's routing time budget has run out.")
    return min(PROVIDER_TIMEOUT_SECONDS, left)


@dataclass(frozen=True)
class Point:
    """A WGS84 coordinate in decimal degrees."""

    latitude: float
    longitude: float


@dataclass(frozen=True)
class Route:
    """One provider route.

    Attributes:
        mode: ``driving`` or ``walking``.
        distance_meters: route length along the path.
        duration_seconds: typical travel time; never traffic-aware.
        geometry: GeoJSON-order ``[longitude, latitude]`` pairs from origin
            to destination, ready for a map line layer.
        provider: key from PROVIDER_LABELS.
    """

    mode: TravelMode
    distance_meters: float
    duration_seconds: float
    geometry: list[list[float]] = field(repr=False)
    provider: str


class RoutingProvider(Protocol):
    """Anything that can turn two points into a Route."""

    name: str

    def route(self, mode: TravelMode, origin: Point, destination: Point,
              deadline: float | None = None) -> Route:
        """Return a route, or raise NoRouteFound or RoutingError.

        ``deadline`` is an optional time.monotonic() value: no request may
        start after it, and the provider timeout is capped by it.
        """
        ...


def straight_line_km(origin: Point, destination: Point) -> float:
    """Great-circle (haversine) distance in kilometres between two points."""
    lat1, lat2 = math.radians(origin.latitude), math.radians(destination.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(destination.longitude - origin.longitude)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2)
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def _check_geometry(raw) -> list[list[float]]:
    """Validate a GeoJSON LineString coordinate list from a provider.

    Every point must be a ``[longitude, latitude]`` pair of finite numbers in
    range; anything else is a provider error, never drawn on the map.
    """
    if not isinstance(raw, list) or len(raw) < 2:
        raise RoutingError("Route geometry is missing.")
    line = []
    for pair in raw:
        if not isinstance(pair, (list, tuple)) or len(pair) < 2:
            raise RoutingError("Route geometry is unreadable.")
        try:
            longitude, latitude = float(pair[0]), float(pair[1])
        except (TypeError, ValueError) as error:
            raise RoutingError("Route geometry is unreadable.") from error
        if not (math.isfinite(longitude) and math.isfinite(latitude)
                and -180 <= longitude <= 180 and -90 <= latitude <= 90):
            raise RoutingError("Route geometry has an invalid coordinate.")
        line.append([longitude, latitude])
    return line


def _number(value, label: str) -> float:
    """Return a finite, non-negative provider number or raise RoutingError."""
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise RoutingError(f"Route {label} is unreadable.") from error
    if not math.isfinite(number) or number < 0:
        raise RoutingError(f"Route {label} is invalid.")
    return number


def _wait_for_slot(throttle: RequestThrottle | None, deadline: float | None) -> float:
    """Take a throttle slot (if any) within the deadline; return the timeout.

    Checks the deadline before taking a slot, only takes a slot that leaves
    MIN_PROVIDER_SECONDS, and checks again right before the caller sends.

    Raises:
        DeadlineExceeded: not enough budget left.
        RoutingError: the throttle is too busy.
    """
    _time_left(deadline)
    if throttle is not None:
        throttle.acquire(None if deadline is None else deadline - MIN_PROVIDER_SECONDS)
    return _time_left(deadline)


def route_minutes(route: Route) -> float:
    """Route duration in minutes, as POST /routes reports it."""
    return round(route.duration_seconds / 60, ROUTE_MINUTES_DECIMALS)


def display_minutes(route: Route) -> int:
    """Whole walking minutes, rounded up with a 1-minute floor, exactly as the
    website's directions box shows ``route_minutes`` (formatDuration)."""
    return max(1, math.ceil(route_minutes(route)))


def _ors_error_code(response: httpx.Response) -> int | None:
    """The numeric ``error.code`` from an ORS error body, if readable."""
    try:
        code = response.json()["error"]["code"]
        return int(code)
    except (ValueError, KeyError, TypeError):
        return None


class OpenRouteServiceProvider:
    """OpenRouteService directions (GeoJSON endpoint).

    Args:
        api_key: ORS key; sent only in the Authorization header.
        client: optional httpx.Client (tests pass a mock transport).
        base_url: API root, overridable for a self-hosted ORS.
        throttle: ``"auto"`` (default) shares one throttle per ORS host,
            ORS_MIN_INTERVAL_SECONDS apart, to stay under the free plan's
            per-minute limit; or pass a RequestThrottle, or None.
    """

    name = "ors"

    def __init__(self, api_key: str, client: httpx.Client | None = None,
                 base_url: str = ORS_BASE_URL, throttle="auto"):
        if not api_key:
            raise ValueError("OpenRouteService needs an API key (ORS_API_KEY).")
        self._key = api_key
        self._client = client or httpx.Client(timeout=PROVIDER_TIMEOUT_SECONDS)
        self._base_url = base_url.rstrip("/")
        self._throttle = (shared_throttle(urlsplit(self._base_url).hostname or "ors",
                                          ORS_MIN_INTERVAL_SECONDS)
                          if throttle == "auto" else throttle)

    @property
    def rate_limited(self) -> bool:
        """True when requests go through a throttle (always, by default)."""
        return self._throttle is not None

    def route(self, mode: TravelMode, origin: Point, destination: Point,
              deadline: float | None = None) -> Route:
        """Request one route; see RoutingProvider.route."""
        url = f"{self._base_url}/v2/directions/{ORS_PROFILES[mode]}/geojson"
        body = {"coordinates": [[origin.longitude, origin.latitude],
                                [destination.longitude, destination.latitude]]}
        timeout = _wait_for_slot(self._throttle, deadline)
        try:
            response = self._client.post(url, json=body, headers={
                "Authorization": self._key, "User-Agent": USER_AGENT,
                "Accept": "application/geo+json, application/json",
            }, timeout=timeout)
        except httpx.HTTPError as error:
            raise _request_error(error, "OpenRouteService") from error
        if response.status_code == 404:
            code = _ors_error_code(response)
            if code in ORS_NO_ROUTE_CODES:
                raise NoRouteFound("No road or path was found near one of the points.")
            raise RoutingError(
                f"OpenRouteService returned HTTP 404 (error code {code}); check "
                "the ORS base URL and profile.")
        if response.status_code != 200:
            raise RoutingError(
                f"OpenRouteService returned HTTP {response.status_code}.")
        try:
            feature = response.json()["features"][0]
            summary = feature["properties"].get("summary")
            geometry = feature["geometry"]["coordinates"]
            if summary is None and (straight_line_km(origin, destination) * 1000
                                    <= SAME_POINT_METERS):
                summary = {}  # ORS omits it when start and end coincide
            if not isinstance(summary, dict):
                raise TypeError("summary is missing or not an object")
        except (ValueError, KeyError, IndexError, TypeError, AttributeError) as error:
            raise RoutingError("OpenRouteService response is unreadable.") from error
        return Route(
            mode=mode,
            # ORS omits distance/duration when origin and destination coincide
            distance_meters=_number(summary.get("distance", 0), "distance"),
            duration_seconds=_number(summary.get("duration", 0), "duration"),
            geometry=_check_geometry(geometry),
            provider=self.name,
        )


class OsrmProvider:
    """OSRM route service, by default the public FOSSGIS servers.

    Args:
        base_urls: server root per mode; each must serve
            ``/route/v1/driving/{lon},{lat};{lon},{lat}``.
        client: optional httpx.Client (tests pass a mock transport).
        throttle: ``"auto"`` (default) applies the shared FOSSGIS throttle to
            requests for the public servers and none to other hosts; or pass
            a RequestThrottle, or None for no throttling.
    """

    name = "osrm"

    def __init__(self, base_urls: dict[str, str] | None = None,
                 client: httpx.Client | None = None, throttle="auto"):
        urls = base_urls or FOSSGIS_OSRM_URLS
        self._urls = {mode: urls[mode].rstrip("/") for mode in TRAVEL_MODES}
        self._client = client or httpx.Client(timeout=PROVIDER_TIMEOUT_SECONDS)
        self._throttles = {}
        for mode, url in self._urls.items():
            if throttle == "auto":
                public = urlsplit(url).hostname == FOSSGIS_HOST
                self._throttles[mode] = (shared_throttle(
                    FOSSGIS_HOST, FOSSGIS_MIN_INTERVAL_SECONDS) if public else None)
            else:
                self._throttles[mode] = throttle

    @property
    def rate_limited(self) -> bool:
        """True when any mode goes through a throttle (the public servers)."""
        return any(throttle is not None for throttle in self._throttles.values())

    @property
    def uses_public_servers(self) -> bool:
        """True when any mode is served by the public FOSSGIS servers."""
        return any(urlsplit(url).hostname == FOSSGIS_HOST
                   for url in self._urls.values())

    def route(self, mode: TravelMode, origin: Point, destination: Point,
              deadline: float | None = None) -> Route:
        """Request one route; see RoutingProvider.route.

        With a deadline, the throttle refuses slots that would leave less than
        MIN_PROVIDER_SECONDS, the deadline is checked again right before the
        request is sent, and the provider timeout is capped at the time left.
        """
        points = (f"{origin.longitude},{origin.latitude};"
                  f"{destination.longitude},{destination.latitude}")
        url = f"{self._urls[mode]}/route/v1/driving/{points}"
        timeout = _wait_for_slot(self._throttles[mode], deadline)
        try:
            response = self._client.get(
                url, params={"overview": "full", "geometries": "geojson"},
                headers={"User-Agent": USER_AGENT}, timeout=timeout,
            )
            data = response.json()
        except httpx.HTTPError as error:
            raise _request_error(error, f"OSRM ({urlsplit(url).hostname})") from error
        except ValueError as error:
            raise RoutingError(f"OSRM returned HTTP {response.status_code}.") from error
        code = data.get("code") if isinstance(data, dict) else None
        if code in ("NoRoute", "NoSegment"):
            raise NoRouteFound("No road or path was found between these points.")
        if response.status_code != 200 or code != "Ok":
            raise RoutingError(f"OSRM returned HTTP {response.status_code} ({code}).")
        try:
            best = data["routes"][0]
            geometry = best["geometry"]["coordinates"]
        except (KeyError, IndexError, TypeError) as error:
            raise RoutingError("OSRM response is unreadable.") from error
        return Route(
            mode=mode,
            distance_meters=_number(best.get("distance"), "distance"),
            duration_seconds=_number(best.get("duration"), "duration"),
            geometry=_check_geometry(geometry),
            provider=self.name,
        )


class RouteService:
    """Validates trips, caches routes and calls one provider.

    Args:
        provider: configured provider, or None when routing is turned off.
        max_entries: cache size; least recently used routes are dropped.
    """

    def __init__(self, provider: RoutingProvider | None,
                 max_entries: int = CACHE_MAX_ENTRIES):
        self.provider = provider
        #: Why routing was turned off after startup (TLS failure), else None.
        self.disabled_reason: str | None = None
        self._cache: OrderedDict[tuple, Route] = OrderedDict()
        #: "No route" answers by trip key: (expiry on time.monotonic, message)
        self._no_route: OrderedDict[tuple, tuple[float, str]] = OrderedDict()
        #: Trips being fetched now; identical requests wait for the first one
        self._in_flight: dict[tuple, threading.Event] = {}
        self._max_entries = max_entries
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        """True when a provider is configured."""
        return self.provider is not None

    @property
    def rate_limited(self) -> bool:
        """True when the provider throttles its requests (FOSSGIS or ORS)."""
        return bool(getattr(self.provider, "rate_limited", False))

    def route(self, mode: TravelMode, origin: Point, destination: Point,
              deadline: float | None = None,
              gate: RequestThrottle | None = None) -> Route:
        """Return a (possibly cached) route.

        Args:
            mode, origin, destination: the trip.
            deadline: optional time.monotonic() value; cached routes are
                returned regardless, but no provider request starts after it.
            gate: optional extra throttle taken only when the provider must be
                called (POST /routes uses it to cap its share of provider calls).

        Raises:
            ValueError: unknown mode or a trip longer than MAX_TRIP_KM.
            RuntimeError: routing is not configured, or was turned off after
                a confirmed unsupported-TLS failure (logged once). Certificate
                and other SSL errors are RoutingError and leave routing on.
            NoRouteFound: no route, or the provider moved a point more than
                MAX_SNAP_METERS to reach a road or path (remembered for
                NO_ROUTE_CACHE_SECONDS).
            RoutingError: the provider failed (not cached).
        """
        if mode not in TRAVEL_MODES:
            raise ValueError(f"Unknown travel mode {mode!r}.")
        limit = MAX_TRIP_KM[mode]
        if straight_line_km(origin, destination) > limit:
            raise ValueError(
                f"{mode.capitalize()} routes are limited to {limit:g} km "
                "in a straight line."
            )
        provider = self.provider
        if provider is None:
            raise RuntimeError(self.disabled_reason
                               or "Routing is not configured on this server.")
        coordinates = (origin.latitude, origin.longitude,
                       destination.latitude, destination.longitude)
        key = (mode, *(round(value, CACHE_COORDINATE_DECIMALS)
                       for value in coordinates))
        while True:
            with self._lock:
                cached = self._cached(key)
                if cached is not None:
                    return cached
                waiting = self._in_flight.get(key)
                if waiting is None:
                    done = self._in_flight[key] = threading.Event()
                    break
            # The same trip is being fetched; use its answer instead of a new call
            wait_for = (IN_FLIGHT_WAIT_SECONDS if deadline is None
                        else deadline - time.monotonic())
            if wait_for <= 0 or not waiting.wait(wait_for):
                raise DeadlineExceeded("The same route is still being fetched.")
        try:
            return self._fetch(provider, key, mode, origin, destination,
                               deadline, gate)
        finally:
            with self._lock:
                self._in_flight.pop(key, None)
            done.set()

    def _cached(self, key: tuple) -> Route | None:
        """Cached route, or raise a remembered NoRouteFound; call under _lock."""
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        known = self._no_route.get(key)
        if known is not None:
            if known[0] > time.monotonic():
                raise NoRouteFound(known[1])
            del self._no_route[key]
        return None

    def _fetch(self, provider, key, mode, origin, destination, deadline, gate):
        """Call the provider once and cache the answer (see route)."""
        if gate is not None:
            # Same rule as the provider throttle: leave time for the call itself
            gate.acquire(None if deadline is None else deadline - MIN_PROVIDER_SECONDS)
        try:
            route = provider.route(mode, origin, destination, deadline=deadline)
            _check_snapping(route, origin, destination)
        except TlsUnsupported as error:
            self._disable(f"Routes turned off: {error}. Use Python 3.11+ built "
                          "with OpenSSL (see docs/backend.md).")
            raise RuntimeError(self.disabled_reason) from error
        except NoRouteFound as error:
            with self._lock:
                self._no_route[key] = (time.monotonic() + NO_ROUTE_CACHE_SECONDS,
                                       str(error))
                while len(self._no_route) > self._max_entries:
                    self._no_route.popitem(last=False)
            raise
        with self._lock:
            self._cache[key] = route
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)
        return route

    def _disable(self, reason: str) -> None:
        """Turn routing off for this process and warn once."""
        with self._lock:
            if self.provider is None:
                return
            self.provider = None
            self.disabled_reason = reason
        LOGGER.warning(reason)


def _check_snapping(route: Route, origin: Point, destination: Point) -> None:
    """Reject a route whose ends were moved too far from the requested points.

    Raises:
        NoRouteFound: an end is more than MAX_SNAP_METERS[route.mode] away.
    """
    limit = MAX_SNAP_METERS[route.mode]
    ends = (("start", origin, route.geometry[0]),
            ("end", destination, route.geometry[-1]))
    for label, requested, (longitude, latitude) in ends:
        meters = straight_line_km(requested, Point(latitude, longitude)) * 1000
        if meters > limit:
            path = "road" if route.mode == "driving" else "path"
            raise NoRouteFound(
                f"The nearest mapped {path} is {meters:.0f} m from the {label} "
                f"point (limit {limit:g} m), so no route was returned.")


def provider_from_env(environ: dict[str, str] | None = None) -> RoutingProvider | None:
    """Build the provider named by PARKSMART_ROUTING_PROVIDER.

    Args:
        environ: mapping to read (defaults to os.environ).
    Returns:
        A provider, or None for ``none``, when ``ors`` has no key, or when
        ``osrm`` would use the public servers from a Python without TLS 1.3
        (both logged as warnings). Unset means ``ors`` when ORS_API_KEY is
        present, else ``osrm`` (the public servers), so routes work with no
        configuration.
    Raises:
        ValueError: unknown provider name.
    """
    env = os.environ if environ is None else environ
    key = env.get("ORS_API_KEY", "").strip()
    name = env.get("PARKSMART_ROUTING_PROVIDER", "").strip().lower()
    name = name or ("ors" if key else "osrm")
    if name == "none":
        return None
    if name == "ors":
        if not key:
            LOGGER.warning("PARKSMART_ROUTING_PROVIDER=ors but ORS_API_KEY is empty; "
                           "routes are disabled.")
            return None
        return OpenRouteServiceProvider(key)
    if name == "osrm":
        # A self-hosted OSRM serves one profile per server, so each mode has its own URL
        urls = {mode: (env.get(f"OSRM_{mode.upper()}_URL", "").strip()
                       or FOSSGIS_OSRM_URLS[mode])
                for mode in TRAVEL_MODES}
        provider = OsrmProvider(urls)
        if provider.uses_public_servers and not tls13_supported():
            LOGGER.warning(TLS13_MISSING.format(version=ssl.OPENSSL_VERSION,
                                                host=FOSSGIS_HOST))
            return None
        return provider
    raise ValueError(
        f"Unknown PARKSMART_ROUTING_PROVIDER {name!r}; use ors, osrm or none.")


def walk_router(service: RouteService,
                budget_seconds: float = WALK_ROUTING_BUDGET_SECONDS,
                workers: int = WALK_ROUTING_WORKERS):
    """Build the ``walk_router`` callable that ``src.ranking.recommend`` accepts.

    Build one per recommendation request: the budget is shared by every call
    the ranking makes (it routes the top locations, then checks the picks).

    Args:
        service: RouteService; None or disabled returns None (no routing).
        budget_seconds: total wait for all routes of one request, starting at
            the first call; routes not finished by then are treated as
            unavailable, and later calls return nothing.
        workers: parallel requests per call.
    Returns:
        ``route_walks(origins, destination) -> {location_id: minutes}`` with
        whole minutes from display_minutes (matching the website's directions
        box), or
        None when routing is off. Failed or too-long trips are left out; when
        every route in a call fails, one warning is logged.
    """
    if service is None or not service.enabled:
        return None
    deadline = None

    def route_walks(origins: dict, destination: dict) -> dict:
        """Route each origin to the destination within the remaining budget."""
        nonlocal deadline
        if not origins:
            return {}
        now = time.monotonic()
        if deadline is None:
            deadline = now + budget_seconds
        remaining = deadline - now
        if remaining <= 0:
            LOGGER.warning("Walking-route budget (%g s) used up; %d location(s) keep "
                           "straight-line estimates.", budget_seconds, len(origins))
            return {}
        end = Point(destination["latitude"], destination["longitude"])
        pool = ThreadPoolExecutor(max_workers=max(1, min(workers, len(origins))))
        futures = {
            pool.submit(service.route, "walking",
                        Point(start["latitude"], start["longitude"]), end,
                        deadline=deadline): location_id
            for location_id, start in origins.items()
        }
        done, pending = wait(futures, timeout=remaining)
        # Never block the request on stragglers. Queued ones are cancelled; a
        # worker waiting for a throttle slot only holds one before the deadline
        # and rechecks it before sending; an in-flight call is not aborted, but
        # its timeout was capped and a late route is still cached.
        pool.shutdown(wait=False, cancel_futures=True)
        minutes, problems = {}, []
        for future in done:
            try:
                route = future.result()
            except (ValueError, RuntimeError, NoRouteFound, RoutingError) as error:
                LOGGER.info("Walking route unavailable for %s: %s",
                            futures[future], error)
                problems.append(f"{futures[future]}: {error}")
                continue
            except Exception as error:  # one bad answer must not lose the others
                LOGGER.exception("Unexpected walking-route error for %s",
                                 futures[future])
                problems.append(f"{futures[future]}: {type(error).__name__}")
                continue
            minutes[futures[future]] = display_minutes(route)
        if pending:
            problems.append(f"{len(pending)} not finished within {budget_seconds:g} s")
        if not minutes:
            LOGGER.warning("All %d walking-route attempts failed; using straight-line "
                           "estimates (%s).", len(origins), "; ".join(problems))
        return minutes

    return route_walks
