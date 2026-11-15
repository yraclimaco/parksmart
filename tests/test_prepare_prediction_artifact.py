"""Check reproducible serving releases without changing the working artifact."""

import json
import shutil

import pandas as pd
import pytest
from fastapi.testclient import TestClient

from scripts.prepare_serving_bundle import main as prepare_bundle
from scripts.verify_prediction_release import verify_release
from src.api.bundle import file_sha256
from src.api.saved_model import create_configured_app
from src.api.settings import PROJECT_ROOT
from src.availability_prediction import load_prediction_service
from src.parking_benchmarks import HistoricalAverage, load_analysis_dataset
from src.prepare_prediction_artifact import main, prepare_artifact


@pytest.fixture
def release_sources(tmp_path):
    """Return a tiny survey and a real registry path without original data."""
    dataset = tmp_path / "survey.csv"
    pd.DataFrame([
        dict(record_id=f"{facility}-{day}", facility=facility, category="S",
             subtype="", level="", observation_date=day,
             observation_time="10:00", quarter="Fall",
             academic_year="2026-2027", fraction_available=value)
        for day in ("2026-10-06", "2026-10-13")
        for facility, value in (("Gilman", 0.6), ("Hopkins", 0.4))
    ]).to_csv(dataset, index=False)
    return dataset, PROJECT_ROOT / "config/locations.json", tmp_path / "release"


def test_release_binds_inputs_versions_and_loads_without_training(release_sources,
                                                                 monkeypatch):
    dataset, registry, output = release_sources
    sources_before = [file_sha256(path) for path in (dataset, registry)]
    metadata_path = prepare_artifact(dataset, registry, output)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    assert metadata["model_name"] == "historical_average"
    assert metadata["records"] == 4
    assert metadata["input_sha256"] == {
        "artifact": file_sha256(output / "selected.pkl"),
        "dataset": sources_before[0], "registry": sources_before[1],
    }
    assert all(metadata["source_sha256"].values())
    assert [file_sha256(path) for path in (dataset, registry)] == sources_before

    monkeypatch.setattr(HistoricalAverage, "fit",
                        lambda *args: pytest.fail("serving refitted the model"))
    service = load_prediction_service(output / "selected.pkl")
    assert service.dependency_versions == metadata["dependency_versions"]
    monkeypatch.delenv("PARKSMART_BUNDLE_MANIFEST", raising=False)
    monkeypatch.setenv("PARKSMART_MODEL_MODE", "saved")
    monkeypatch.setenv("PARKSMART_APPROVED_MODEL", "historical_average")
    monkeypatch.setenv("PARKSMART_ARTIFACT_PATH", str(output / "selected.pkl"))
    monkeypatch.setenv("PARKSMART_DATASET_PATH", str(dataset))
    monkeypatch.setenv("PARKSMART_REGISTRY_PATH", str(registry))
    with TestClient(create_configured_app()) as client:
        assert client.get("/readiness").status_code == 200
        body = client.post("/recommendations", json={
            "destination": {"name": "Fixture", "coordinates": None},
            "arrival_time": "2026-11-03T10:00:00", "permit_type": "S",
        }).json()
        assert body["status"] == "ready"
        assert body["first_choice"]["location"]["location_id"] != (
            body["backup_choice"]["location"]["location_id"])


def test_existing_or_invalid_inputs_never_replace_release(release_sources):
    dataset, registry, output = release_sources
    prepare_artifact(dataset, registry, output)
    before = {path.name: file_sha256(path) for path in output.iterdir()}
    with pytest.raises(FileExistsError):
        prepare_artifact(dataset, registry, output)
    assert {path.name: file_sha256(path) for path in output.iterdir()} == before
    with pytest.raises(FileNotFoundError):
        prepare_artifact(dataset.with_name("missing.csv"), registry,
                         output.with_name("invalid"))
    assert not output.with_name("invalid").exists()


def test_reproduction_with_reordered_rows(release_sources):
    dataset, registry, output = release_sources
    prepare_artifact(dataset, registry, output)
    first = load_prediction_service(output / "selected.pkl")
    features = load_analysis_dataset(dataset)
    pd.read_csv(dataset).iloc[::-1].to_csv(dataset, index=False)
    second_output = output.with_name("reordered-release")
    prepare_artifact(dataset, registry, second_output)
    second = load_prediction_service(second_output / "selected.pkl")
    pd.testing.assert_frame_equal(first.predict(features), second.predict(features))
    assert first.groups == second.groups
    assert first.training_start == second.training_start
    assert first.training_end == second.training_end


def test_metadata_prevents_pairing_an_artifact_with_changed_data(release_sources):
    dataset, registry, output = release_sources
    prepare_artifact(dataset, registry, output)
    rows = pd.read_csv(dataset)
    rows.loc[0, "fraction_available"] = 0.1
    rows.to_csv(dataset, index=False)
    bundle = output / "bundle"
    with pytest.raises(SystemExit):
        prepare_bundle([
            "--artifact", str(output / "selected.pkl"), "--dataset", str(dataset),
            "--registry", str(registry), "--metadata", str(output / "metadata.json"),
            "--s3-prefix", "releases/fixture", "--output-dir", str(bundle),
        ])
    assert not bundle.exists()


def test_bundle_preserves_serving_protocol_and_bound_metadata(release_sources):
    dataset, registry, output = release_sources
    metadata_path = prepare_artifact(dataset, registry, output)
    bundle = output / "bundle"
    manifest_path = prepare_bundle([
        "--artifact", str(output / "selected.pkl"), "--dataset", str(dataset),
        "--registry", str(registry), "--metadata", str(metadata_path),
        "--s3-prefix", "releases/fixture", "--output-dir", str(bundle),
    ])
    manifest = json.loads(manifest_path.read_text())
    assert set(manifest["files"]) == {"artifact", "dataset", "registry"}
    assert manifest["release_metadata"] == {
        "key": "releases/fixture/metadata.json", "sha256": file_sha256(metadata_path),
    }
    assert (bundle / "metadata.json").read_bytes() == metadata_path.read_bytes()
    summary = verify_release(bundle)
    assert summary["artifact_loads"] == 1
    assert summary["recommendation_requests"] == 2
    assert summary["training_allowed"] is False


def test_bundle_rejects_data_changed_during_copy(release_sources, monkeypatch):
    dataset, registry, output = release_sources
    metadata_path = prepare_artifact(dataset, registry, output)
    bundle = output / "bundle"
    original_copy = shutil.copyfile

    def changed_source(source, target):
        if source == dataset:
            rows = pd.read_csv(dataset)
            rows.loc[0, "fraction_available"] = 0.1
            rows.to_csv(dataset, index=False)
        return original_copy(source, target)

    monkeypatch.setattr(shutil, "copyfile", changed_source)
    with pytest.raises(ValueError, match="Copied dataset"):
        prepare_bundle([
            "--artifact", str(output / "selected.pkl"), "--dataset", str(dataset),
            "--registry", str(registry), "--metadata", str(metadata_path),
            "--s3-prefix", "releases/fixture", "--output-dir", str(bundle),
        ])
    assert not (bundle / "manifest.json").exists()


@pytest.mark.parametrize("release_id", ["../escape", ".", "..", "a/b", "a\\b"])
def test_release_id_stays_in_output_root(tmp_path, release_id):
    with pytest.raises(SystemExit):
        main(["--release-id", release_id, "--output-root", str(tmp_path)])
    assert list(tmp_path.iterdir()) == []
