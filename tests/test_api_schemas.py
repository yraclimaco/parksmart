"""Input, time-zone, response consistency, and shared-example validation."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.api.locations import get_locations
from src.api.schemas import (
    Coordinates,
    LocationsResponse,
    ParkingChoice,
    RecommendationRequest,
    RecommendationResponse,
)

EXAMPLES = Path(__file__).resolve().parents[1] / "docs/examples/backend"


def make_request(**changes):
    payload = {
        "destination": {"name": "User-selected destination"},
        "arrival_time": "2026-10-27T09:00:00",
        "permit_type": "S",
    }
    payload.update(changes)
    return RecommendationRequest.model_validate(payload)


@pytest.mark.parametrize("arrival, expected", [
    ("2026-10-27T09:00:00", "2026-10-27T09:00:00-07:00"),
    ("2026-12-01T09:00:00", "2026-12-01T09:00:00-08:00"),
    ("2026-10-27T16:00:00Z", "2026-10-27T09:00:00-07:00"),
    ("2026-11-01T01:30:00-07:00", "2026-11-01T01:30:00-07:00"),
    ("2026-11-01T01:30:00-08:00", "2026-11-01T01:30:00-08:00"),
])
def test_ucsd_time_conversion(arrival, expected):
    assert make_request(arrival_time=arrival).arrival_time.isoformat() == expected


@pytest.mark.parametrize("arrival", [
    "2026-03-08T02:30:00",  # Missing spring hour.
    "2026-11-01T01:30:00",  # Repeated autumn hour needs an offset.
    "2026-10-27", 1793120400, None, "invalid",
])
def test_invalid_or_ambiguous_arrivals(arrival):
    with pytest.raises(ValidationError):
        make_request(arrival_time=arrival)


def test_optional_origin_and_unverified_permit_input():
    request = make_request(permit_type=" proposed-code ")
    assert request.starting_location is None
    assert request.destination.coordinates is None
    assert request.permit_type == "proposed-code"
    request = make_request(starting_location={"name": "User-selected origin"})
    assert request.starting_location.name == "User-selected origin"


@pytest.mark.parametrize("coordinates", [
    {"latitude": 91, "longitude": 0},
    {"latitude": 0, "longitude": -181},
    {"latitude": 0},
    {"latitude": float("nan"), "longitude": 0},
])
def test_invalid_coordinate_pairs(coordinates):
    with pytest.raises(ValidationError):
        Coordinates.model_validate(coordinates)


def test_coordinate_boundaries():
    assert Coordinates(latitude=90, longitude=-180).latitude == 90


@pytest.mark.parametrize("field,value", [
    ("estimated_available_fraction", -0.1),
    ("estimated_available_fraction", 1.1),
    ("estimated_available_fraction", float("inf")),
    ("estimated_walking_minutes", -1),
])
def test_bad_estimates(field, value):
    with pytest.raises(ValidationError):
        ParkingChoice.model_validate({
            "location": {"location_id": "sample-a", "name": "Sample A"},
            "explanation": "Validation fixture only",
            field: value,
        })


def test_zero_and_unknown_are_distinct():
    choice = ParkingChoice(
        location={"location_id": "sample-a", "name": "Sample A"},
        explanation="Boundary test, not a prediction",
    )
    assert choice.estimated_available_fraction is None
    zero = ParkingChoice.model_validate({
        **choice.model_dump(), "estimated_available_fraction": 0,
    })
    assert zero.estimated_available_fraction == 0
    assert ParkingChoice.model_validate({
        **choice.model_dump(), "estimated_available_fraction": 1,
        "estimated_walking_minutes": 0,
    }).estimated_available_fraction == 1


def test_duplicate_catalog_ids_rejected():
    location = {"location_id": "sample-a", "name": "Sample A"}
    with pytest.raises(ValidationError):
        LocationsResponse(data_status="sample", locations=[location, location],
                          limitations=["Sample"])


@pytest.mark.parametrize("filename", [
    "recommendation_not_implemented.json",
    "recommendation_example.json",
    "recommendation_no_suitable.json",
])
def test_response_examples(filename):
    response = RecommendationResponse.model_validate_json(
        (EXAMPLES / filename).read_text()
    )
    assert response.is_example is True


def test_request_example():
    RecommendationRequest.model_validate_json(
        (EXAMPLES / "recommendation_request.json").read_text()
    )


@pytest.mark.parametrize("changes", [
    {"status": "ready", "first_choice": None},
    {"status": "not_implemented"},
    {"status": "no_suitable_location"},
    {"arrival_time": "2026-10-27T09:00:00"},
])
def test_inconsistent_response(changes):
    payload = json.loads((EXAMPLES / "recommendation_example.json").read_text())
    payload.update(changes)
    with pytest.raises(ValidationError):
        RecommendationResponse.model_validate(payload)


def test_duplicate_backup_rejected():
    payload = json.loads((EXAMPLES / "recommendation_example.json").read_text())
    payload["backup_choice"] = payload["first_choice"]
    with pytest.raises(ValidationError):
        RecommendationResponse.model_validate(payload)


def test_sample_catalog_objects_are_independent():
    first = get_locations()
    first.locations.clear()
    second = get_locations()
    assert second.data_status == "sample"
    assert len(second.locations) == 2
    assert all(location.coordinates is None for location in second.locations)


@pytest.mark.parametrize("changes", [
    {"permit_type": "  "},
    {"permit_type": "S" * 201},
    {"destination": {"name": ""}},
    {"destination": {"name": "Library", "coordinates": {"latitude": 91}}},
    {"permitType": "S"},
    {"destination": None},
])
def test_invalid_request_fields(changes):
    with pytest.raises(ValidationError):
        make_request(**changes)


def test_missing_required_request_fields():
    with pytest.raises(ValidationError):
        RecommendationRequest.model_validate({})
