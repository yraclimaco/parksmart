"""Run locally with: python -m uvicorn src.api.main:app --reload."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .locations import get_locations
from .schemas import (
    HealthResponse,
    LocationsResponse,
)

app = FastAPI(
    title="ParkSmart Local API",
    version="0.1.0",
    description="Proposed interface contract. Locations are fictional samples; "
    "recommendations are not implemented. No live parking information is served.",
)

# Common local React development origins; no production access is configured.
LOCAL_FRONTEND_ORIGINS = [
    f"http://{host}:{port}"
    for host in ("localhost", "127.0.0.1")
    for port in (3000, 5173)
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=LOCAL_FRONTEND_ORIGINS,
    allow_methods=["GET"],
    allow_headers=["Content-Type"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
def health() -> HealthResponse:
    """Take no inputs and return process liveness, not prediction readiness."""
    return HealthResponse()


@app.get("/locations", response_model=LocationsResponse, tags=["Locations"])
def locations() -> LocationsResponse:
    """Take no inputs and return the explicitly labeled sample catalog."""
    return get_locations()
