"""HTTP contract checks using an in-process client; no datasets required."""

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def client():
    with TestClient(app) as test_client:
        yield test_client


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_sample_catalog_is_stable_and_explicit(client):
    response = client.get("/locations")
    assert response.status_code == 200
    catalog = response.json()
    assert catalog["data_status"] == "sample"
    assert catalog["limitations"]
    assert [row["location_id"] for row in catalog["locations"]] == [
        "sample-parking-a", "sample-parking-b"
    ]
    assert all(row["coordinates"] is None for row in catalog["locations"])
    assert client.get("/locations").json() == catalog


def test_documentation_exposes_contract(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/health", "/locations"}


def test_recommendation_endpoint_is_not_implemented(client):
    assert client.post("/recommendations", json={}).status_code == 404


def test_local_browser_cors(client):
    response = client.options("/locations", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    response = client.get("/locations", headers={"Origin": "https://unlisted.test"})
    assert "access-control-allow-origin" not in response.headers
