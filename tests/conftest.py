"""Shared pytest setup."""

import pytest


@pytest.fixture(autouse=True)
def no_real_routing(monkeypatch):
    """Keep every test offline even if a routing key is exported locally.

    create_app() reads routing settings from the environment; tests that need
    routes pass a RouteService (or set the variables) explicitly.
    """
    for name in ("ORS_API_KEY", "PARKSMART_ROUTING_PROVIDER",
                 "OSRM_DRIVING_URL", "OSRM_WALKING_URL"):
        monkeypatch.delenv(name, raising=False)
