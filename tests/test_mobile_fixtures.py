"""Check bundled iOS samples against the shared Python API contract."""

import json
from pathlib import Path

import pytest

from src.api.schemas import LocationsResponse, RecommendationResponse


ROOT = Path(__file__).resolve().parents[1]
RESOURCES = ROOT / "mobile/ios/ParkSmart/Resources"


@pytest.mark.parametrize("name", [
    "recommendation_example", "recommendation_no_suitable",
    "recommendation_not_implemented",
])
def test_mobile_recommendation_fixtures_match_shared_contract(name):
    """Bundled examples must match the API schema and remain illustrative."""
    copied = json.loads((RESOURCES / f"{name}.json").read_text())
    response = RecommendationResponse.model_validate(copied)
    assert response.is_example
    for choice in (response.first_choice, response.backup_choice):
        if choice:
            assert choice.location.coordinates is None
            assert choice.estimated_available_fraction is None
            assert choice.estimated_walking_minutes is None


def test_mobile_catalog_matches_shared_sample_ids():
    """The fictional catalog stays separate from the real backend registry."""
    value = json.loads((RESOURCES / "locations_sample.json").read_text())
    catalog = LocationsResponse.model_validate(value)
    ids = [location.location_id for location in catalog.locations]
    assert ids
    assert len(ids) == len(set(ids))
    assert all(location.name.strip() for location in catalog.locations)
    assert catalog.data_status == "sample"
    assert all(location.coordinates is None for location in catalog.locations)
