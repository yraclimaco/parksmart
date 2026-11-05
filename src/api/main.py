"""Local HTTP orchestration; predictions and ranking stay in reusable modules."""

import logging
import os
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.location_registry import DEFAULT_DATASET, DEFAULT_REGISTRY, load_registry
from src.parking_benchmarks import load_analysis_dataset
from src.recommender import Recommender
from src.routing import (
    PROVIDER_LABELS, METERS_PER_MILE, ROUTE_REQUEST_BUDGET_SECONDS, NoRouteFound, Point,
    RouteService, RoutingError, provider_from_env, walk_router,
)

from .locations import get_locations
from .schemas import (
    HealthResponse, LocationsResponse, RecommendationRequest, RecommendationResponse,
    RouteRequest, RouteResponse,
)

LOGGER = logging.getLogger(__name__)
LOCAL_FRONTEND_ORIGINS = [
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1")
    for port in (3000, 5173)
]
#: Extra browser origins (comma-separated, exact scheme://host[:port]) allowed to call
#: the API, e.g. the deployed Amplify site. Wildcards are not accepted.
CORS_ORIGINS_ENV = "PARKSMART_CORS_ORIGINS"
DATA_UNAVAILABLE = (
    "Historical estimates are unavailable. Check the server startup logs and "
    "the processed dataset or estimator, then restart the backend. "
    "This does not mean parking is full."
)
ROUTING_OFF = ("Routes are not available on this server. Recommendations still "
               "work; see the server log and docs/routing.md to enable them.")
ROUTE_FAILED = ("The routing service could not provide this route right now. "
                "Try again shortly.")
ROUTE_ATTRIBUTION = "Route data \u00a9 OpenStreetMap contributors"
ROUTE_LIMITATIONS = {
    "driving": [
        "Typical driving time without live traffic.",
        "Ends at the parking location's map point, which may not be its "
        "vehicle entrance.",
    ],
    "walking": [
        "Walking path from map data; check signs for closures and construction.",
        "Starts at the parking location's map point, which may not be its "
        "pedestrian exit.",
    ],
}


def allowed_origins(environ=None) -> list:
    """Return local development origins plus any from PARKSMART_CORS_ORIGINS.

    Args:
        environ: mapping to read (defaults to os.environ).
    Returns:
        Origins without trailing slashes, local ones first, no duplicates.
    Raises:
        ValueError: an entry is a wildcard or lacks an http(s) scheme.
    """
    env = os.environ if environ is None else environ
    extra = []
    for raw in env.get(CORS_ORIGINS_ENV, "").split(","):
        origin = raw.strip().rstrip("/")
        if not origin:
            continue
        if "*" in origin or not origin.startswith(("https://", "http://")):
            raise ValueError(
                f"{CORS_ORIGINS_ENV} entries must be exact http(s) origins: {raw!r}")
        extra.append(origin)
    return list(dict.fromkeys([*LOCAL_FRONTEND_ORIGINS, *extra]))


def create_app(dataset_path=DEFAULT_DATASET, registry_path=DEFAULT_REGISTRY,
               estimator=None, route_service=None) -> FastAPI:
    """Create an API loading its catalog and prediction resources at startup.

    Args:
        dataset_path: existing integrated CSV; never built by the API.
        registry_path: validated shared registry JSON.
        estimator: optional ready AvailabilityEstimator wrapping a loaded model.
            None uses the historical-average baseline, fitted once at startup.
        route_service: optional RouteService. None builds one from environment
            variables (src.routing.provider_from_env) at startup.
    Returns:
        FastAPI app. Missing/invalid resources produce HTTP 503 while health
        remains available. Each process loads once; restart to reload resources.
    """
    @asynccontextmanager
    async def lifespan(application):
        """Load shared resources for this app, then release them on shutdown."""
        application.state.catalog = None
        application.state.recommender = None
        if route_service is not None:
            application.state.routes = route_service
        else:
            try:
                application.state.routes = RouteService(provider_from_env())
            except ValueError as error:
                LOGGER.warning("Routing disabled: %s", error)
                application.state.routes = RouteService(None)
        try:
            registry = load_registry(registry_path)
            application.state.catalog = get_locations(registry)
        except (OSError, ValueError) as error:
            LOGGER.warning("Location registry unavailable: %s", error)
        else:
            try:
                records = load_analysis_dataset(dataset_path)
                application.state.recommender = Recommender(
                    records, registry, estimator=estimator,
                )
            except (OSError, ValueError, KeyError) as error:
                LOGGER.warning("Historical recommendation resources unavailable: %s",
                               error)
        try:
            yield
        finally:
            application.state.recommender = None
            application.state.catalog = None
            application.state.routes = None

    application = FastAPI(
        title="ParkSmart Local API", version="0.2.0", lifespan=lifespan,
        description="Shared real locations and historical parking recommendations. "
        "Estimates are not live availability or a guaranteed space.",
    )
    application.add_middleware(
        CORSMiddleware, allow_origins=allowed_origins(),
        allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
    )

    @application.get("/health", response_model=HealthResponse, tags=["Health"])
    def health() -> HealthResponse:
        """Return process liveness, independently of prediction readiness."""
        return HealthResponse()

    @application.get("/locations", response_model=LocationsResponse,
                     tags=["Locations"])
    def locations() -> LocationsResponse:
        """Return the cached supported registry catalog, or 503 if unavailable."""
        catalog = application.state.catalog
        if catalog is None:
            raise HTTPException(503, "Location registry unavailable; check startup "
                                "logs and restart after fixing the registry.")
        return catalog

    @application.post("/recommendations", response_model=RecommendationResponse,
                      tags=["Recommendations"])
    def recommendations(request: RecommendationRequest) -> RecommendationResponse:
        """Pass validated trip inputs to the cached recommender and serialize it."""
        recommender = application.state.recommender
        if recommender is None:
            raise HTTPException(503, DATA_UNAVAILABLE)
        coordinates = request.destination.coordinates
        try:
            result = recommender.recommend(
                request.permit_type, request.arrival_time,
                destination=coordinates.model_dump() if coordinates else None,
                walk_router=walk_router(application.state.routes),
            )
        except ValueError as error:
            # Request syntax, permit and time errors are validated by Pydantic.
            # An unready estimator here is a service problem, not bad user input.
            LOGGER.warning("Prediction request unavailable: %s", error)
            raise HTTPException(503, DATA_UNAVAILABLE) from error
        payload = result.to_api()
        if request.starting_location is not None:
            payload["limitations"] = [
                *payload["limitations"],
                "Starting location is not used for ranking yet; driving routes "
                "come from POST /routes.",
            ]
        return RecommendationResponse(
            **payload, is_example=False, arrival_time=request.arrival_time,
        )

    @application.post("/routes", response_model=RouteResponse, tags=["Routes"])
    def routes(request: RouteRequest) -> RouteResponse:
        """Return one driving or walking route, or explain why there is none.

        400: trip too long for the mode. 404: provider found no route, or a
        point is too far from any mapped road or path. 502: provider failed.
        503: routing is not configured, or was turned off (for example a
        Python without TLS 1.3; see the server log).
        """
        service = application.state.routes
        if service is None or not service.enabled:
            raise HTTPException(503, ROUTING_OFF)
        origin = Point(request.origin.latitude, request.origin.longitude)
        destination = Point(request.destination.latitude, request.destination.longitude)
        try:
            # Throttle wait plus provider call stay inside the website's route timeout
            deadline = time.monotonic() + ROUTE_REQUEST_BUDGET_SECONDS
            route = service.route(request.mode, origin, destination,
                                  deadline=deadline)
        except RuntimeError as error:
            # Routing was turned off after a confirmed unsupported-TLS failure
            raise HTTPException(503, ROUTING_OFF) from error
        except ValueError as error:
            raise HTTPException(400, str(error)) from error
        except NoRouteFound as error:
            raise HTTPException(404, str(error)) from error
        except RoutingError as error:
            LOGGER.warning("Route provider failed: %s", error)
            raise HTTPException(502, ROUTE_FAILED) from error
        return RouteResponse(
            mode=route.mode,
            distance_meters=round(route.distance_meters, 1),
            distance_miles=round(route.distance_meters / METERS_PER_MILE, 2),
            duration_minutes=round(route.duration_seconds / 60, 1),
            geometry=route.geometry,
            provider=PROVIDER_LABELS.get(route.provider, route.provider),
            attribution=ROUTE_ATTRIBUTION,
            limitations=ROUTE_LIMITATIONS[route.mode],
        )

    return application


app = create_app()
