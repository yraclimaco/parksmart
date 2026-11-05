"""HTTP integration with the real baseline/ranker and synthetic survey fixtures.

Only generated temporary CSVs are read; no real pipeline dataset is needed.
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api import main
from src.api.main import create_app
from src.availability import AvailabilityEstimator
from src.location_registry import load_registry

REQUEST = {
    "destination": {"name": "Test destination", "coordinates": None},
    "arrival_time": "2026-11-03T10:00:00",
    "permit_type": "S",
}


def survey_records(facilities=("Gilman", "Hopkins"), category="S"):
    """Return synthetic survey readings, never evidence of real availability."""
    return pd.DataFrame([
        {"record_id": str(index), "facility": facility, "category": category,
         "subtype": "", "level": "", "observation_date": "2026-10-06",
         "academic_year": "2026-2027", "quarter": "Fall",
         "observation_time": "10:00", "fraction_available": fraction}
        for index, (facility, fraction) in enumerate(zip(facilities, (0.6, 0.4)))
    ])


@pytest.fixture
def app_factory(tmp_path):
    def build(records=None, estimator=None):
        dataset = tmp_path / "synthetic.csv"
        (survey_records() if records is None else records).to_csv(dataset, index=False)
        return create_app(dataset_path=dataset, estimator=estimator)
    return build


@pytest.fixture
def client(app_factory):
    with TestClient(app_factory()) as test_client:
        yield test_client


def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_real_registry_catalog(client):
    response = client.get("/locations")
    assert response.status_code == 200
    catalog = response.json()
    registry = load_registry()
    supported = {row["location_id"]: row for row in registry
                 if row["registry_status"] == "supported"}
    assert catalog["data_status"] == "verified"
    assert {row["location_id"] for row in catalog["locations"]} == set(supported)
    for row in catalog["locations"]:
        source = supported[row["location_id"]]
        assert row["name"] == source["name"]
        assert row["coordinates"] == (
            source["coordinates"] if source["coordinate_status"] == "verified"
            else None
        )
    assert catalog["limitations"]
    assert client.get("/locations").json() == catalog


def test_documentation_exposes_post_contract(client):
    assert client.get("/docs").status_code == 200
    schema = client.get("/openapi.json").json()
    assert set(schema["paths"]) == {"/health", "/locations", "/recommendations", "/routes"}
    assert "post" in schema["paths"]["/recommendations"]
    assert "post" in schema["paths"]["/routes"]
    assert "RecommendationRequest" in schema["components"]["schemas"]


def test_recommendation_runs_real_modules(client):
    response = client.post("/recommendations", json=REQUEST)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ready"
    assert body["is_example"] is False
    assert body["arrival_time"] == "2026-11-03T10:00:00-08:00"
    assert body["time_zone"] == "America/Los_Angeles"
    first, backup = body["first_choice"], body["backup_choice"]
    assert first["location"]["location_id"] == "gilman-ps"
    assert backup["location"]["location_id"] == "hopkins-ps"
    assert first["estimated_available_fraction"] == pytest.approx(0.6)
    assert backup["estimated_available_fraction"] == pytest.approx(0.4)
    assert first["estimated_walking_minutes"] is None
    assert any("historical" in note for note in body["limitations"])
    assert any("arrival only" in note for note in body["limitations"])
    catalog_ids = {row["location_id"]
                   for row in client.get("/locations").json()["locations"]}
    choice_ids = {choice["location"]["location_id"] for choice in (first, backup)}
    assert choice_ids <= catalog_ids


def test_walking_and_unused_starting_location_are_explicit(client):
    payload = {**REQUEST, "destination": {
        "name": "Test point", "coordinates": {"latitude": 32.88, "longitude": -117.24}},
        "starting_location": {"name": "User origin"}}
    result = client.post("/recommendations", json=payload).json()
    assert result["status"] == "ready"
    assert result["first_choice"]["estimated_walking_minutes"] is not None
    assert any("Starting location is not used for ranking" in note
               for note in result["limitations"])


def test_no_backup_is_valid(app_factory):
    with TestClient(app_factory(survey_records(("Gilman",)))) as client:
        body = client.post("/recommendations", json=REQUEST).json()
    assert body["status"] == "ready"
    assert body["first_choice"] is not None
    assert body["backup_choice"] is None


def test_no_eligible_options_is_not_missing_predictions(app_factory):
    with TestClient(app_factory(survey_records(category="Reserved"))) as client:
        body = client.post("/recommendations", json=REQUEST).json()
    assert body["status"] == "no_suitable_location"
    assert body["first_choice"] is body["backup_choice"] is None


class UnsupportedModel:
    """A ready model explicitly returning no estimate, with no fitting allowed."""

    def fit(self, records):
        raise AssertionError("A supplied model must not be retrained")

    def predict(self, features):
        return pd.DataFrame({"prediction": float("nan"), "baseline_group": "missing"},
                            index=features.index)


def test_no_prediction_is_not_no_eligible_parking(app_factory):
    estimator = AvailabilityEstimator(UnsupportedModel(), survey_times=["10:00"])
    with TestClient(app_factory(estimator=estimator)) as client:
        response = client.post("/recommendations", json=REQUEST)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "predictions_unavailable"
    assert body["first_choice"] is body["backup_choice"] is None


def test_resources_loaded_once_and_not_read_per_request(app_factory, monkeypatch):
    from src.api import main
    original = main.load_analysis_dataset
    calls = []

    def tracked_load(path):
        calls.append(path)
        return original(path)

    monkeypatch.setattr(main, "load_analysis_dataset", tracked_load)
    with TestClient(app_factory()) as client:
        assert len(calls) == 1
        calls[0].unlink()  # Temporary fixture only; cached requests still work.
        for _ in range(2):
            body = client.post("/recommendations", json=REQUEST).json()
            assert body["status"] == "ready"
        assert len(calls) == 1


@pytest.mark.parametrize("contents", [None, "invalid,csv\n1,2\n"])
def test_missing_or_invalid_dataset_keeps_catalog_and_health(tmp_path, contents):
    dataset = tmp_path / "missing.csv"
    if contents:
        dataset.write_text(contents)
    with TestClient(create_app(dataset_path=dataset)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/locations").status_code == 200
        response = client.post("/recommendations", json=REQUEST)
    assert response.status_code == 503
    assert "does not mean parking is full" in response.json()["detail"]


@pytest.mark.parametrize("contents", [None, '{"schema_version":"wrong"}'])
def test_missing_or_invalid_registry_is_explicit(tmp_path, contents):
    registry = tmp_path / "registry.json"
    if contents:
        registry.write_text(contents)
    with TestClient(create_app(registry_path=registry)) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/locations").status_code == 503
        assert client.post("/recommendations", json=REQUEST).status_code == 503


def test_unready_estimator_is_503(app_factory):
    with TestClient(app_factory(estimator=AvailabilityEstimator())) as client:
        assert client.post("/recommendations", json=REQUEST).status_code == 503


@pytest.mark.parametrize("changes", [
    {"permit_type": "unsupported"}, {"permit_type": ""},
    {"destination": None}, {"destination": {"name": ""}},
    {"arrival_time": "2026-11-03"}, {"arrival_time": "2026-11-01T01:30:00"},
    {"arrival_time": "2027-03-14T02:30:00"},
    {"destination": {"name": "Test", "coordinates": {"latitude": 91, "longitude": 0}}},
    {"permitType": "S"},
])
def test_invalid_inputs_are_422(client, changes):
    response = client.post("/recommendations", json={**REQUEST, **changes})
    assert response.status_code == 422
    assert response.json()["detail"]


def test_missing_body(client):
    assert client.post("/recommendations").status_code == 422


def test_post_preflight_and_error_response_allow_local_browser(client, tmp_path):
    response = client.options("/recommendations", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "content-type",
    })
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    response = client.get("/locations", headers={"Origin": "https://unlisted.test"})
    assert "access-control-allow-origin" not in response.headers
    with TestClient(create_app(dataset_path=tmp_path / "missing.csv")) as unavailable:
        response = unavailable.post("/recommendations", json=REQUEST,
                                    headers={"Origin": "http://localhost:3000"})
        assert response.status_code == 503
        assert response.headers["access-control-allow-origin"] == (
            "http://localhost:3000"
        )


def test_deployed_origins_come_from_environment(tmp_path, monkeypatch):
    monkeypatch.setenv(main.CORS_ORIGINS_ENV,
                       " https://main.d1abc.amplifyapp.com/ , https://parksmart.example ")
    assert main.allowed_origins()[-2:] == [
        "https://main.d1abc.amplifyapp.com", "https://parksmart.example"]
    with TestClient(create_app(dataset_path=tmp_path / "missing.csv")) as client:
        allowed = client.get("/health", headers={"Origin": "https://parksmart.example"})
        blocked = client.get("/health", headers={"Origin": "https://evil.example"})
    assert allowed.headers["access-control-allow-origin"] == "https://parksmart.example"
    assert "access-control-allow-origin" not in blocked.headers


@pytest.mark.parametrize("value", [
    "*", "https://*.amplifyapp.com", "parksmart.example",
    "https://main.d123.amplifyapp.com/app", "https://site.example?x=1",
    "https://site.example#top", "ftp://site.example", "https://",
    "https://user:pw@site.example",
])
def test_cors_origins_reject_wildcards_and_bare_hosts(value):
    with pytest.raises(ValueError, match="exact http"):
        main.allowed_origins({main.CORS_ORIGINS_ENV: value})


def test_local_origins_stay_allowed_without_configuration():
    assert main.allowed_origins({}) == main.LOCAL_FRONTEND_ORIGINS


def test_cors_origin_with_trailing_slash_or_port_is_accepted():
    origins = main.allowed_origins({main.CORS_ORIGINS_ENV:
                                    "https://main.d123.amplifyapp.com/, http://10.0.0.5:3000"})
    assert "https://main.d123.amplifyapp.com" in origins
    assert "http://10.0.0.5:3000" in origins



@pytest.mark.parametrize("value, expected", [
    ("https://Main.D123.amplifyapp.com", "https://main.d123.amplifyapp.com"),
    ("https://site.example:443", "https://site.example"),
    ("HTTP://site.example:80/", "http://site.example"),
    ("https://site.example:8443", "https://site.example:8443"),
    ("http://[::1]:3000", "http://[::1]:3000"),
    ("https://bücher.example", "https://xn--bcher-kva.example"),
])
def test_cors_origins_are_normalized_like_browser_origins(value, expected):
    assert expected in main.allowed_origins({main.CORS_ORIGINS_ENV: value})


@pytest.mark.parametrize("value", ["https://site.example:abc", "https://site.example:99999"])
def test_cors_origins_reject_bad_ports(value):
    with pytest.raises(ValueError, match="port"):
        main.allowed_origins({main.CORS_ORIGINS_ENV: value})


def test_cors_origins_reject_invalid_hosts():
    with pytest.raises(ValueError, match="host"):
        main.allowed_origins({main.CORS_ORIGINS_ENV: "https://a..b"})
