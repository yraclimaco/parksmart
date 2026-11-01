"""Tests for the one-object recommendation entry point and its CLI."""

import json
from datetime import datetime

import pandas as pd
import pytest

from src.recommender import Recommender, main
from src.ranking import READY

TUESDAY_10AM = datetime(2026, 10, 27, 10)


def _location(location_id, facility, latitude):
    return {"location_id": location_id, "name": location_id.title(),
            "kind": "lot", "dataset_facilities": [facility],
            "coordinates": {"latitude": latitude, "longitude": -117.24},
            "coordinate_status": "verified", "coordinate_source": "test",
            "coordinate_verified_on": "2026-10-21",
            "registry_status": "supported", "access_note": None, "notes": None}


LOCATIONS = [_location("near", "NEAR", 32.8805), _location("mid", "MID", 32.8850)]


def _records():
    """Prepared-style readings for two S lots, both in Fall 2026-2027."""
    rows = []
    for facility, fraction in (("NEAR", 0.6), ("MID", 0.4)):
        for record_id, time in enumerate(("08:00", "10:00")):
            rows.append({
                "record_id": f"{facility}-{record_id}", "facility": facility,
                "category": "S", "subtype": "", "level": "",
                "observation_date": pd.Timestamp("2026-10-06"),
                "academic_year": "2026-2027", "quarter": "Fall",
                "weekday": "Tuesday", "observation_time": time,
                "fraction_available": fraction})
    return pd.DataFrame(rows)


def test_recommend_runs_the_whole_pipeline():
    recommender = Recommender(_records(), LOCATIONS)
    result = recommender.recommend("S", TUESDAY_10AM,
                                   {"latitude": 32.88, "longitude": -117.24})
    assert result.status == READY
    assert result.first_choice.location["location_id"] == "near"
    assert result.backup_choice.location["location_id"] == "mid"
    assert result.first_choice.estimate_note is None   # full match at 10:00


def test_custom_estimator_is_used():
    class Fixed:
        def attach(self, groups, arrival):
            return groups.assign(estimated_available_fraction=0.5,
                                 estimate_note="test model")

    result = Recommender(_records(), LOCATIONS, Fixed()).recommend(
        "S", TUESDAY_10AM)
    assert result.first_choice.estimated_available_fraction == 0.5
    assert result.first_choice.estimate_note == "test model"


def test_missing_dataset_names_the_build_command(tmp_path):
    with pytest.raises(FileNotFoundError, match="src.build_dataset"):
        Recommender.from_files(dataset=tmp_path / "missing.csv")


def test_cli_prints_api_json(capsys, monkeypatch):
    monkeypatch.setattr("src.recommender.Recommender.from_files",
                        classmethod(lambda cls, *args: cls(_records(),
                                                           LOCATIONS)))
    main(["--permit", "S", "--arrival", "2026-10-27T10:00",
          "--lat", "32.88", "--lon", "-117.24"])
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == READY
    assert payload["first_choice"]["location"]["location_id"] == "near"


def test_cli_requires_both_coordinates():
    with pytest.raises(SystemExit):
        main(["--permit", "S", "--arrival", "2026-10-27T10:00", "--lat", "32.88"])


def test_from_files_loads_dataset_and_registry(tmp_path):
    dataset = tmp_path / "analysis_dataset.csv"
    _records().drop(columns="weekday").to_csv(dataset, index=False)
    registry = tmp_path / "locations.json"
    registry.write_text(json.dumps({"schema_version": "0.1",
                                    "locations": LOCATIONS}))
    recommender = Recommender.from_files(dataset, registry)
    assert len(recommender.candidates) == 2
    assert recommender.recommend("S", TUESDAY_10AM).status == READY


def test_missing_registry_is_reported(tmp_path):
    dataset = tmp_path / "analysis_dataset.csv"
    dataset.write_text("")
    with pytest.raises(FileNotFoundError, match="registry"):
        Recommender.from_files(dataset, tmp_path / "missing.json")
