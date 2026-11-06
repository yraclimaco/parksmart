"""Shared pytest setup."""

import pytest


@pytest.fixture(autouse=True)
def no_real_routing(monkeypatch):
    """Keep every test offline even if a routing key is exported locally.

    create_app() reads routing settings from the environment; tests that need
    routes pass a RouteService (or set the variables) explicitly.
    """
    for name in ("ORS_API_KEY", "OSRM_DRIVING_URL", "OSRM_WALKING_URL"):
        monkeypatch.delenv(name, raising=False)
    # Unset would mean the public OSRM servers; tests must stay offline
    monkeypatch.setenv("PARKSMART_ROUTING_PROVIDER", "none")


@pytest.fixture(autouse=True)
def fast_routes_endpoint(monkeypatch):
    """Tests call POST /routes back to back; the production gate spaces
    provider calls ROUTES_ENDPOINT_MIN_INTERVAL_SECONDS apart. Tests of the gate
    itself set it back explicitly."""
    monkeypatch.setattr("src.api.main.ROUTES_ENDPOINT_MIN_INTERVAL_SECONDS", 0.0)
