"""Driving and walking routes from a third-party routing provider.

The website and mobile app call the backend's POST /routes, never a provider
directly, so provider keys stay on the server. Two providers are supported:

* ``ors``: OpenRouteService (https://openrouteservice.org). Needs a free API
  key in ``ORS_API_KEY``; the free plan allows 2,000 directions requests a
  day and 40 a minute (checked 2026-11-04 on its plans page).
* ``osrm``: any OSRM server. The default is the public FOSSGIS servers at
  routing.openstreetmap.de, which need no key but allow only light use
  (about one request a second) and offer no uptime guarantee. Fine for
  development, demos and low traffic; the in-memory cache keeps calls down.

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
import threading
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from typing import Literal, Protocol

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

#: Total time recommendations wait for routed walking times before falling
#: back to straight-line estimates, well inside the website's 20 s timeout.
WALK_ROUTING_BUDGET_SECONDS = 6.0
#: Parallel walking-route requests per recommendation. Kept low because the
#: public OSRM servers ask for about one request a second.
WALK_ROUTING_WORKERS = 3

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


class RoutingError(Exception):
    """A provider failed, timed out or returned something unreadable."""


class NoRouteFound(Exception):
    """The provider answered but found no route between the two points."""


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

    def route(self, mode: TravelMode, origin: Point, destination: Point) -> Route:
        """Return a route, or raise NoRouteFound or RoutingError."""
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
    """Validate a GeoJSON LineString coordinate list from a provider."""
    if not isinstance(raw, list) or len(raw) < 2:
        raise RoutingError("Route geometry is missing.")
    try:
        return [[float(pair[0]), float(pair[1])] for pair in raw]
    except (TypeError, ValueError, IndexError) as error:
        raise RoutingError("Route geometry is unreadable.") from error


def _number(value, label: str) -> float:
    """Return a finite, non-negative provider number or raise RoutingError."""
    try:
        number = float(value)
    except (TypeError, ValueError) as error:
        raise RoutingError(f"Route {label} is unreadable.") from error
    if not math.isfinite(number) or number < 0:
        raise RoutingError(f"Route {label} is invalid.")
    return number


class OpenRouteServiceProvider:
    """OpenRouteService directions (GeoJSON endpoint).

    Args:
        api_key: ORS key; sent only in the Authorization header.
        client: optional httpx.Client (tests pass a mock transport).
        base_url: API root, overridable for a self-hosted ORS.
    """

    name = "ors"

    def __init__(self, api_key: str, client: httpx.Client | None = None,
                 base_url: str = ORS_BASE_URL):
        if not api_key:
            raise ValueError("OpenRouteService needs an API key (ORS_API_KEY).")
        self._key = api_key
        self._client = client or httpx.Client(timeout=PROVIDER_TIMEOUT_SECONDS)
        self._base_url = base_url.rstrip("/")

    def route(self, mode: TravelMode, origin: Point, destination: Point) -> Route:
        """Request one route; see RoutingProvider.route."""
        url = f"{self._base_url}/v2/directions/{ORS_PROFILES[mode]}/geojson"
        body = {"coordinates": [[origin.longitude, origin.latitude],
                                [destination.longitude, destination.latitude]]}
        try:
            response = self._client.post(url, json=body, headers={
                "Authorization": self._key, "User-Agent": USER_AGENT,
                "Accept": "application/geo+json, application/json",
            })
        except httpx.HTTPError as error:
            raise RoutingError(f"OpenRouteService request failed: {error!r}") from error
        if response.status_code == 404:
            # ORS answers 404 (error code 2010) when a point is far from any road
            raise NoRouteFound("No road or path was found near one of the points.")
        if response.status_code != 200:
            raise RoutingError(
                f"OpenRouteService returned HTTP {response.status_code}.")
        try:
            feature = response.json()["features"][0]
            summary = feature["properties"]["summary"]
            geometry = feature["geometry"]["coordinates"]
        except (ValueError, KeyError, IndexError, TypeError) as error:
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
    """

    name = "osrm"

    def __init__(self, base_urls: dict[str, str] | None = None,
                 client: httpx.Client | None = None):
        urls = base_urls or FOSSGIS_OSRM_URLS
        self._urls = {mode: urls[mode].rstrip("/") for mode in TRAVEL_MODES}
        self._client = client or httpx.Client(timeout=PROVIDER_TIMEOUT_SECONDS)

    def route(self, mode: TravelMode, origin: Point, destination: Point) -> Route:
        """Request one route; see RoutingProvider.route."""
        points = (f"{origin.longitude},{origin.latitude};"
                  f"{destination.longitude},{destination.latitude}")
        url = f"{self._urls[mode]}/route/v1/driving/{points}"
        try:
            response = self._client.get(
                url, params={"overview": "full", "geometries": "geojson"},
                headers={"User-Agent": USER_AGENT},
            )
            data = response.json()
        except httpx.HTTPError as error:
            raise RoutingError(f"OSRM request failed: {error!r}") from error
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
        self._cache: OrderedDict[tuple, Route] = OrderedDict()
        self._max_entries = max_entries
        self._lock = threading.Lock()

    @property
    def enabled(self) -> bool:
        """True when a provider is configured."""
        return self.provider is not None

    def route(self, mode: TravelMode, origin: Point, destination: Point) -> Route:
        """Return a (possibly cached) route.

        Raises:
            ValueError: unknown mode or a trip longer than MAX_TRIP_KM.
            RuntimeError: routing is not configured.
            NoRouteFound / RoutingError: from the provider (not cached).
        """
        if mode not in TRAVEL_MODES:
            raise ValueError(f"Unknown travel mode {mode!r}.")
        limit = MAX_TRIP_KM[mode]
        if straight_line_km(origin, destination) > limit:
            raise ValueError(
                f"{mode.capitalize()} routes are limited to {limit:g} km "
                "in a straight line."
            )
        if self.provider is None:
            raise RuntimeError("Routing is not configured on this server.")
        coordinates = (origin.latitude, origin.longitude,
                       destination.latitude, destination.longitude)
        key = (mode, *(round(value, CACHE_COORDINATE_DECIMALS) for value in coordinates))
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
                return self._cache[key]
        route = self.provider.route(mode, origin, destination)
        with self._lock:
            self._cache[key] = route
            self._cache.move_to_end(key)
            while len(self._cache) > self._max_entries:
                self._cache.popitem(last=False)
        return route


def provider_from_env(environ: dict[str, str] | None = None) -> RoutingProvider | None:
    """Build the provider named by PARKSMART_ROUTING_PROVIDER.

    Args:
        environ: mapping to read (defaults to os.environ).
    Returns:
        A provider, or None for ``none`` or when ``ors`` has no key (logged).
        Unset means ``ors`` when ORS_API_KEY is present, else ``osrm`` (the
        public servers), so routes work with no configuration.
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
        return OsrmProvider(urls)
    raise ValueError(
        f"Unknown PARKSMART_ROUTING_PROVIDER {name!r}; use ors, osrm or none.")


def walk_router(service: RouteService, budget_seconds: float = WALK_ROUTING_BUDGET_SECONDS,
                workers: int = WALK_ROUTING_WORKERS):
    """Build the ``walk_router`` callable that ``src.ranking.recommend`` accepts.

    Args:
        service: RouteService; None or disabled returns None (no routing).
        budget_seconds: total wait for all routes of one request; routes not
            finished by then are treated as unavailable.
        workers: parallel requests.
    Returns:
        ``route_walks(origins, destination) -> {location_id: minutes}`` with
        whole minutes rounded up (matching the website's directions box), or
        None when routing is off. Failed or too-long trips are left out.
    """
    if service is None or not service.enabled:
        return None

    def route_walks(origins: dict, destination: dict) -> dict:
        end = Point(destination["latitude"], destination["longitude"])
        pool = ThreadPoolExecutor(max_workers=max(1, min(workers, len(origins) or 1)))
        futures = {
            pool.submit(service.route, "walking",
                        Point(start["latitude"], start["longitude"]), end): location_id
            for location_id, start in origins.items()
        }
        done, _ = wait(futures, timeout=budget_seconds)
        # Never block the request on stragglers; they finish (and are cached) later
        pool.shutdown(wait=False, cancel_futures=True)
        minutes = {}
        for future in done:
            try:
                route = future.result()
            except (ValueError, RuntimeError, NoRouteFound, RoutingError) as error:
                LOGGER.info("Walking route unavailable for %s: %s", futures[future], error)
                continue
            minutes[futures[future]] = math.ceil(route.duration_seconds / 60)
        return minutes

    return route_walks
