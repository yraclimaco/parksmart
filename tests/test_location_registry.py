"""Tests for the shared location registry (Issue #20)."""

import copy
import json
import re

import pandas as pd
import pytest

from src.location_registry import (
    DEFAULT_DATASET,
    DEFAULT_REGISTRY,
    api_locations,
    main,
    facility_to_location,
    load_registry,
    location_groups,
    location_summary,
    unmapped_facilities,
    validate_registry,
)


def _location(location_id, facilities, **overrides):
    """Return a valid registry entry with verified coordinates."""
    entry = {
        "location_id": location_id,
        "name": location_id.title(),
        "kind": "lot",
        "dataset_facilities": facilities,
        "coordinates": {"latitude": 32.88, "longitude": -117.24},
        "coordinate_status": "verified",
        "coordinate_source": "test GIS",
        "coordinate_verified_on": "2026-10-21",
        "registry_status": "supported",
        "access_note": None,
        "notes": None,
    }
    entry.update(overrides)
    return entry


LOCATIONS = [
    _location("gilman-ps", ["Gilman"], kind="structure"),
    _location("p406", ["P406"]),
    _location("tdlln", ["TDLLN"], kind="unknown", coordinates=None,
              coordinate_status="missing", coordinate_source=None,
              coordinate_verified_on=None, registry_status="unresolved"),
    _location("p386", ["P386"], coordinate_status="approximate"),
]


def _records():
    """Return a tiny analysis dataset spanning two quarters."""
    rows = [
        ("Gilman", "A", None, None, "2026-10-01", "2026-2027", "Fall"),
        ("Gilman", "A", None, "Level 2", "2018-06-18", "2017-2018", "Summer"),
        ("Gilman", "Visitor", "2 Hours", None, "2026-10-02", "2026-2027", "Fall"),
        ("P406", "S", None, None, "2025-01-10", "2024-2025", "Winter"),
        ("Unlisted", "B", None, None, "2026-10-01", "2026-2027", "Fall"),
    ]
    return pd.DataFrame(rows, columns=[
        "facility", "category", "subtype", "level", "observation_date",
        "academic_year", "quarter",
    ])


def test_valid_registry_passes():
    validate_registry(LOCATIONS)


@pytest.mark.parametrize("change, message", [
    (lambda ls: ls[1].update(location_id="gilman-ps"), "duplicate location_id"),
    (lambda ls: ls[0].update(location_id="Gilman PS"), "kebab-case"),
    (lambda ls: ls[1].update(dataset_facilities=["Gilman"]), "already mapped"),
    (lambda ls: ls[0].update(registry_status="maybe"), "registry_status"),
    (lambda ls: ls[0].update(coordinates=None), "latitude and longitude"),
    (lambda ls: ls[0]["coordinates"].update(latitude=95), "latitude out of range"),
    (lambda ls: ls[0].update(coordinate_verified_on="soon"), "ISO date"),
    (lambda ls: ls[2].update(coordinate_source="guess"), "no value or source"),
    (lambda ls: ls[0].pop("notes"), "missing ['notes']"),
    (lambda ls: ls[0].update(capacity=10), "unexpected ['capacity']"),
])
def test_invalid_registry_is_rejected(change, message):
    locations = copy.deepcopy(LOCATIONS)
    change(locations)
    with pytest.raises(ValueError, match=re.escape(message)):
        validate_registry(locations)


def test_load_registry_checks_schema_version(tmp_path):
    path = tmp_path / "locations.json"
    path.write_text(json.dumps({"schema_version": "9", "locations": LOCATIONS}))
    with pytest.raises(ValueError, match="schema_version"):
        load_registry(path)


def test_groups_keep_category_subtype_and_level_separate():
    groups = location_groups(LOCATIONS, _records())
    gilman = groups[groups.location_id == "gilman-ps"]
    assert len(gilman) == 3
    assert set(zip(gilman.category, gilman.subtype, gilman.level)) == {
        ("A", "", ""), ("A", "", "Level 2"), ("Visitor", "2 Hours", ""),
    }


def test_unmapped_facilities_are_kept_and_reported():
    groups = location_groups(LOCATIONS, _records())
    unlisted = groups[groups.facility == "Unlisted"]
    assert len(unlisted) == 1 and unlisted.location_id.isna().all()
    assert unmapped_facilities(LOCATIONS, _records()) == ["Unlisted"]


def test_current_use_reflects_latest_quarter_but_is_never_verified():
    summary = location_summary(LOCATIONS, _records()).set_index("location_id")
    assert summary.loc["gilman-ps", "current_use_status"] == (
        "observed_in_latest_quarter")
    assert summary.loc["p406", "current_use_status"] == "not_in_latest_quarter"
    assert summary.loc["p386", "current_use_status"] == "no_observations"
    assert summary.loc["p386", "readings"] == 0
    assert not summary.current_use_verified.any()


def test_api_locations_pass_only_verified_coordinates():
    by_id = {item["location_id"]: item for item in api_locations(LOCATIONS)}
    assert by_id["gilman-ps"]["coordinates"] == {
        "latitude": 32.88, "longitude": -117.24}
    assert by_id["p386"]["coordinates"] is None
    assert by_id["tdlln"]["coordinates"] is None
    assert set(by_id["p406"]) == {"location_id", "name", "coordinates"}


def test_api_locations_match_backend_schema():
    from src.api.schemas import ParkingLocation

    for item in api_locations(load_registry()):
        ParkingLocation(**item)


def test_committed_registry_is_valid():
    locations = load_registry(DEFAULT_REGISTRY)
    assert len(facility_to_location(locations)) >= 1
    for location in locations:
        if location["registry_status"] == "supported":
            assert location["coordinate_status"] != "missing"


@pytest.mark.skipif(not DEFAULT_DATASET.exists(),
                    reason="Integrated dataset not built locally")
def test_real_dataset_facilities_are_all_mapped():
    records = pd.read_csv(DEFAULT_DATASET, usecols=["facility"])
    assert unmapped_facilities(load_registry(), records) == []


FRONTEND_DATA = DEFAULT_REGISTRY.parent.parent / "frontend" / "src" / "data"


@pytest.mark.skipif(not FRONTEND_DATA.exists(), reason="frontend/ not present")
def test_website_location_ids_exist_in_registry():
    """The website pins and the registry must use the same location IDs."""
    ids = set()
    for name in ("parkingLots.ts", "surfaceLots.ts"):
        text = (FRONTEND_DATA / name).read_text()
        ids.update(re.findall(r"locationId:\s*['\"]([^'\"]+)['\"]", text))
    assert ids, "no locationId values found in the website data"
    registry_ids = {location["location_id"] for location in load_registry()}
    assert ids - registry_ids == set()


def test_cli_reports_unmapped_facilities(tmp_path, capsys):
    registry = tmp_path / "locations.json"
    registry.write_text(json.dumps({"schema_version": "0.1",
                                    "locations": LOCATIONS}))
    dataset = tmp_path / "analysis.csv"
    _records().to_csv(dataset, index=False)
    with pytest.raises(SystemExit, match="Unlisted"):
        main(["--registry", str(registry), "--dataset", str(dataset)])
    mapped = _records()[lambda d: d.facility != "Unlisted"]
    mapped.to_csv(dataset, index=False)
    main(["--registry", str(registry), "--dataset", str(dataset)])
    assert "mapped to exactly one location" in capsys.readouterr().out
