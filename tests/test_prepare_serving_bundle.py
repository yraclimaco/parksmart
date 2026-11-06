"""Offline release preparation checks using generated records and artifacts."""

import json
import shutil

import pandas as pd
import pytest

from scripts.prepare_serving_bundle import main
from src.api.bundle import file_sha256, validate_manifest
from src.api.settings import PROJECT_ROOT
from src.availability_prediction import PredictionService, load_prediction_service
from src.parking_benchmarks import prepare_records


@pytest.fixture
def release_inputs(tmp_path):
    """Create a trusted fixture artifact, tiny survey and public registry copy."""
    records = prepare_records(pd.DataFrame([{
        "record_id": "fixture-gilman", "facility": "Gilman", "category": "S",
        "subtype": "", "level": "", "observation_date": "2026-10-06",
        "observation_time": "10:00", "academic_year": "2026-2027",
        "quarter": "Fall", "fraction_available": 0.5,
    }]))
    artifact = PredictionService(records).save(tmp_path / "fixture.pkl")
    dataset = tmp_path / "fixture.csv"
    records.to_csv(dataset, index=False)
    registry = tmp_path / "registry.json"
    shutil.copyfile(PROJECT_ROOT / "config/locations.json", registry)
    output = tmp_path / "release"
    args = ["--artifact", str(artifact), "--dataset", str(dataset),
            "--registry", str(registry), "--output-dir", str(output),
            "--s3-prefix", "releases/fixture"]
    return args, artifact, dataset, registry, output


def test_prepared_manifest_hashes_pins_and_sources(release_inputs):
    args, artifact, dataset, registry, output = release_inputs
    sources = {"artifact": artifact, "dataset": dataset, "registry": registry}
    before = {role: file_sha256(path) for role, path in sources.items()}
    manifest_path = main(args)
    document = json.loads(manifest_path.read_text())
    files = validate_manifest(document, "releases/fixture/")
    for role, item in files.items():
        destination = output / item["key"].rsplit("/", 1)[1]
        assert file_sha256(destination) == item["sha256"] == before[role]
        assert file_sha256(sources[role]) == before[role]
    model = load_prediction_service(artifact)
    assert document["model_name"] == model.name == "historical_average"
    assert document["dependency_versions"] == model.dependency_versions
    expected_pins = {f"{name}=={value}" for name, value in
                     model.dependency_versions.items() if name != "python"}
    assert set((output / "requirements-model.txt").read_text().splitlines()) == (
        expected_pins)


def test_unapproved_model_does_not_create_release(release_inputs, capsys):
    args, _, _, _, output = release_inputs
    with pytest.raises(SystemExit) as error:
        main([*args, "--approved-model", "unapproved-fixture-model"])
    assert error.value.code == 2
    assert "approved model" in capsys.readouterr().err
    assert not output.exists()


def test_unmapped_facility_does_not_create_release(release_inputs, capsys):
    args, _, dataset, _, output = release_inputs
    records = pd.read_csv(dataset)
    records["facility"] = "Unmapped fictional fixture"
    records.to_csv(dataset, index=False)
    with pytest.raises(SystemExit) as error:
        main(args)
    assert error.value.code == 2
    assert "not mapped" in capsys.readouterr().err
    assert not output.exists()


def test_existing_release_is_never_overwritten(release_inputs):
    args, _, _, _, output = release_inputs
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("existing release")
    with pytest.raises(FileExistsError):
        main(args)
    assert sentinel.read_text() == "existing release"
    assert list(output.iterdir()) == [sentinel]
