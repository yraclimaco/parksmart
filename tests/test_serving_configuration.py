"""Saved-artifact serving checks using synthetic model/data fixtures.

No real network service, production artifact or private dataset is used.
"""

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from src.api.saved_model import create_configured_app
from src.api.settings import PROJECT_ROOT, ServingSettings
from src.availability_prediction import PredictionService
from src.parking_benchmarks import HistoricalAverage, prepare_records

REQUEST = {"destination": {"name": "Fixture", "coordinates": None},
           "arrival_time": "2026-11-03T10:00:00", "permit_type": "S"}


def records(facilities=("Gilman", "Hopkins")):
    return prepare_records(pd.DataFrame([
        dict(record_id=facility, facility=facility, category="S", subtype="",
             level="", observation_date="2026-10-06", observation_time="10:00",
             academic_year="2026-2027", quarter="Fall", fraction_available=value)
        for facility, value in zip(facilities, (0.6, 0.4))
    ]))


@pytest.fixture
def serving_files(tmp_path, monkeypatch):
    monkeypatch.delenv("PARKSMART_BUNDLE_MANIFEST", raising=False)
    monkeypatch.setenv("PARKSMART_MODEL_MODE", "saved")
    monkeypatch.setenv("PARKSMART_APPROVED_MODEL", "historical_average")
    data = records()
    artifact = PredictionService(data).save(tmp_path / "approved.pkl")
    dataset = tmp_path / "survey.csv"
    data.to_csv(dataset, index=False)
    monkeypatch.setenv("PARKSMART_ARTIFACT_PATH", str(artifact))
    monkeypatch.setenv("PARKSMART_DATASET_PATH", str(dataset))
    monkeypatch.setenv("PARKSMART_REGISTRY_PATH", str(PROJECT_ROOT / "config/locations.json"))
    return artifact, dataset


def test_settings_resolve_paths_and_explicit_mode():
    settings = ServingSettings.from_env({})
    assert settings.model_mode == "saved"
    assert settings.artifact_path == PROJECT_ROOT / "models/issue18/selected.pkl"
    assert ServingSettings.from_env({"PARKSMART_MODEL_MODE": "baseline"}).model_mode == "baseline"
    with pytest.raises(ValueError):
        ServingSettings.from_env({"PARKSMART_MODEL_MODE": "automatic"})


def test_saved_resources_load_once_and_never_fit(serving_files, monkeypatch):
    from src.api import saved_model
    original = saved_model.load_prediction_service
    loads = []

    def load(path):
        loads.append(path)
        return original(path)

    def forbidden(*args, **kwargs):
        raise AssertionError("Saved serving must never fit or train")

    monkeypatch.setattr(saved_model, "load_prediction_service", load)
    monkeypatch.setattr(HistoricalAverage, "fit", forbidden)
    app = create_configured_app()
    assert loads == []  # Loading occurs at startup, not import/factory creation.
    with TestClient(app) as client:
        assert client.get("/readiness").json() == {
            "status": "ready", "catalog_ready": True,
            "predictions_ready": True, "prediction_mode": "saved"}
        serving_files[0].unlink()  # Temporary fixture only; future requests use memory.
        for _ in range(2):
            response = client.post("/recommendations", json=REQUEST)
            assert response.status_code == 200
            body = response.json()
            assert body["is_example"] is False
            assert body["status"] == "ready"
            assert body["first_choice"]["location"]["location_id"] != (
                body["backup_choice"]["location"]["location_id"])
        assert len(loads) == 1


@pytest.mark.parametrize("problem", ["missing", "corrupt", "dependencies", "wrong_model"])
def test_artifact_failure_never_fits_fallback(serving_files, monkeypatch, problem):
    import pickle
    artifact, _ = serving_files
    if problem == "missing":
        artifact.unlink()
    elif problem == "corrupt":
        artifact.write_bytes(b"invalid pickle")
    elif problem == "dependencies":
        with artifact.open("rb") as stream:
            envelope = pickle.load(stream)
        envelope["dependency_versions"]["python"] = "incompatible"
        with artifact.open("wb") as stream:
            pickle.dump(envelope, stream)
    else:
        monkeypatch.setenv("PARKSMART_APPROVED_MODEL", "another_model")
    monkeypatch.setattr(HistoricalAverage, "fit", lambda *args: pytest.fail("fallback fit"))
    with TestClient(create_configured_app()) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/locations").status_code == 200
        assert client.get("/readiness").status_code == 503
        assert client.post("/recommendations", json=REQUEST).status_code == 503


def test_unsupported_saved_request_does_not_invent_prediction(serving_files):
    with TestClient(create_configured_app()) as client:
        # Only Tuesday is present in the generated training fixture.
        request = {**REQUEST, "arrival_time": "2026-11-04T10:00:00"}
        response = client.post("/recommendations", json=request)
        assert response.status_code == 200
        assert response.json()["status"] == "predictions_unavailable"
        assert response.json()["first_choice"] is None


def test_saved_model_can_return_only_one_choice(serving_files):
    artifact, dataset = serving_files
    data = records(("Gilman",))
    PredictionService(data).save(artifact)
    data.to_csv(dataset, index=False)
    with TestClient(create_configured_app()) as client:
        body = client.post("/recommendations", json=REQUEST).json()
        assert body["status"] == "ready"
        assert body["backup_choice"] is None


def test_baseline_demo_mode_is_explicit(serving_files, monkeypatch):
    serving_files[0].unlink()
    monkeypatch.setenv("PARKSMART_MODEL_MODE", "baseline")
    with TestClient(create_configured_app()) as client:
        assert client.get("/readiness").json()["prediction_mode"] == "baseline"
        assert client.post("/recommendations", json=REQUEST).json()["status"] == "ready"


def test_explicit_baseline_ignores_saved_settings(serving_files, monkeypatch):
    from src.api.main import create_app

    monkeypatch.setenv("PARKSMART_MODEL_MODE", "invalid-saved-mode")
    monkeypatch.setenv("PARKSMART_APPROVED_MODEL", "")
    monkeypatch.setenv("PARKSMART_BUNDLE_MANIFEST", "s3://unused/missing/manifest.json")
    monkeypatch.setenv("PARKSMART_ARTIFACT_PATH", "/missing/unused.pkl")
    _, dataset = serving_files
    with TestClient(create_app(dataset_path=dataset)) as client:
        assert client.get("/readiness").json()["prediction_mode"] == "baseline"
        assert client.post("/recommendations", json=REQUEST).json()["status"] == "ready"


@pytest.fixture
def configured_s3_bundle(serving_files, tmp_path, monkeypatch):
    """Provide the actual configured factory an offline S3 byte-stream client."""
    import hashlib
    import io
    import json
    import boto3

    artifact, dataset = serving_files
    objects = {}
    files = {}
    for role, path in {"artifact": artifact, "dataset": dataset,
                       "registry": PROJECT_ROOT / "config/locations.json"}.items():
        key = f"release/{role}"
        content = path.read_bytes()
        objects[key] = content
        files[role] = {"key": key, "sha256": hashlib.sha256(content).hexdigest()}
    objects["release/manifest.json"] = json.dumps(
        {"schema_version": 1, "files": files}).encode()
    calls = []

    class StubS3:
        def get_object(self, Bucket, Key):
            assert Bucket == "fixture-bucket"
            calls.append(Key)
            if Key not in objects:
                raise OSError("Fixture object unavailable")
            return {"Body": io.BytesIO(objects[Key])}

    def client(service):
        assert service == "s3"
        return StubS3()

    monkeypatch.setattr(boto3, "client", client)
    monkeypatch.setenv("PARKSMART_BUNDLE_MANIFEST",
                       "s3://fixture-bucket/release/manifest.json")
    monkeypatch.setenv("PARKSMART_CACHE_DIR", str(tmp_path / "cache"))
    # Only the materialized bundle paths can succeed.
    for variable in ("ARTIFACT", "DATASET", "REGISTRY"):
        monkeypatch.setenv(f"PARKSMART_{variable}_PATH", str(tmp_path / "absent"))
    return objects, calls


def test_configured_bundle_uses_materialized_paths(configured_s3_bundle):
    _, calls = configured_s3_bundle
    with TestClient(create_configured_app()) as client:
        assert client.get("/readiness").json() == {
            "status": "ready", "catalog_ready": True,
            "predictions_ready": True, "prediction_mode": "saved"}
        for _ in range(2):
            response = client.post("/recommendations", json=REQUEST)
            assert response.status_code == 200
            assert response.json()["first_choice"] is not None
        assert len(calls) == 4  # One manifest and three files, never per request.


@pytest.mark.parametrize("failure", ["missing", "checksum"])
def test_configured_bundle_failure_returns_lambda_503(
        configured_s3_bundle, monkeypatch, failure):
    from types import SimpleNamespace
    from src.api import lambda_handler

    objects, _ = configured_s3_bundle
    if failure == "missing":
        del objects["release/artifact"]
    else:
        objects["release/artifact"] = b"checksum-invalid fixture"
    monkeypatch.setattr(lambda_handler, "_runtime", None)
    # Exercise the real configured factory and real Lambda initialization.
    response = lambda_handler.handler({}, SimpleNamespace())
    assert response["statusCode"] == 503
    assert "fixture-bucket" not in response["body"]
    assert lambda_handler._runtime is None
