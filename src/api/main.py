"""Local HTTP orchestration; predictions and ranking stay in reusable modules."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from src.location_registry import DEFAULT_DATASET, DEFAULT_REGISTRY, load_registry
from src.parking_benchmarks import load_analysis_dataset
from src.recommender import Recommender

from .locations import get_locations
from .schemas import (
    HealthResponse, LocationsResponse, RecommendationRequest, RecommendationResponse,
)

LOGGER = logging.getLogger(__name__)
LOCAL_FRONTEND_ORIGINS = [
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1")
    for port in (3000, 5173)
]
DATA_UNAVAILABLE = (
    "Historical estimates are unavailable. Check the server startup logs and "
    "the processed dataset or estimator, then restart the backend. "
    "This does not mean parking is full."
)


def create_app(dataset_path=DEFAULT_DATASET, registry_path=DEFAULT_REGISTRY,
               estimator=None) -> FastAPI:
    """Create an API loading its catalog and prediction resources at startup.

    Args:
        dataset_path: existing integrated CSV; never built by the API.
        registry_path: validated shared registry JSON.
        estimator: optional ready AvailabilityEstimator wrapping a loaded model.
            None uses the historical-average baseline, fitted once at startup.
    Returns:
        FastAPI app. Missing/invalid resources produce HTTP 503 while health
        remains available. Each process loads once; restart to reload resources.
    """
    @asynccontextmanager
    async def lifespan(application):
        """Load shared resources for this app, then release them on shutdown."""
        application.state.catalog = None
        application.state.recommender = None
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

    application = FastAPI(
        title="ParkSmart Local API", version="0.2.0", lifespan=lifespan,
        description="Shared real locations and historical parking recommendations. "
        "Estimates are not live availability or a guaranteed space.",
    )
    application.add_middleware(
        CORSMiddleware, allow_origins=LOCAL_FRONTEND_ORIGINS,
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
                "Starting location is not used yet; no driving route is calculated.",
            ]
        return RecommendationResponse(
            **payload, is_example=False, arrival_time=request.arrival_time,
        )

    return application


app = create_app()
