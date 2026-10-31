"""Tests for first-choice/backup ranking (Issue #20)."""

from datetime import datetime

import pandas as pd
import pytest

from src import ranking

from src.api.schemas import ParkingChoice
from src.ranking import (
    AVAILABILITY_WEIGHT,
    NO_SUITABLE_LOCATION,
    PREDICTIONS_UNAVAILABLE,
    READY,
    WALKING_WEIGHT,
    recommend,
    score,
    walking_minutes,
)

WEEKDAY_MORNING = datetime(2026, 10, 27, 10)
DESTINATION = {"latitude": 32.8800, "longitude": -117.2400}


def _location(location_id, latitude, status="supported",
              coordinate_status="verified"):
    return {
        "location_id": location_id, "name": location_id.upper(), "kind": "lot",
        "dataset_facilities": [location_id.upper()],
        "coordinates": {"latitude": latitude, "longitude": -117.2400},
        "coordinate_status": coordinate_status, "coordinate_source": "test",
        "coordinate_verified_on": "2026-10-21", "registry_status": status,
        "access_note": None, "notes": None,
    }


# Latitude offsets of 0.001 deg are about 0.11 km apart.
LOCATIONS = [
    _location("near", 32.8805),
    _location("mid", 32.8850),
    _location("far", 32.8950),
    _location("restricted", 32.8801, status="restricted"),
    _location("gliderport", 32.8810, coordinate_status="approximate"),
]


def _candidates(rows):
    """Rows of (location_id, category, subtype, fraction)."""
    return pd.DataFrame([
        {"location_id": loc, "facility": loc.upper(), "category": cat,
         "subtype": sub, "level": "", "estimated_available_fraction": frac}
        for loc, cat, sub, frac in rows
    ])


def test_first_choice_and_distinct_backup():
    result = recommend(_candidates([
        ("near", "S", "", 0.5), ("mid", "S", "", 0.5), ("far", "S", "", 0.5),
    ]), LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION)
    assert result.status == READY
    assert result.first_choice.location["location_id"] == "near"
    assert result.backup_choice.location["location_id"] == "mid"
    assert "longer walk" in result.backup_choice.explanation


def test_best_group_represents_each_location_once():
    result = recommend(_candidates([
        ("near", "S", "", 0.2), ("near", "B", "", 0.9), ("near", "S", "", 0.8),
        ("mid", "S", "", 0.1),
    ]), LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION)
    # B is not allowed for S at 10 AM; the better S group wins.
    assert result.first_choice.estimated_available_fraction == 0.8
    assert result.backup_choice.location["location_id"] == "mid"
    assert "nearly full" in result.backup_choice.explanation


def test_single_option_has_no_backup():
    result = recommend(_candidates([("near", "S", "", 0.4)]), LOCATIONS, "S",
                       WEEKDAY_MORNING, DESTINATION)
    assert result.status == READY and result.backup_choice is None
    assert "No second suitable location" in result.explanation


def test_restricted_and_ineligible_options_are_not_recommended():
    result = recommend(_candidates([
        ("restricted", "S", "", 0.9), ("near", "A", "", 0.9),
        ("near", "Reserved", "", 0.9), ("mid", "D", "", 0.9),
    ]), LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION)
    assert result.status == NO_SUITABLE_LOCATION
    assert result.first_choice is None
    assert result.counts["not_supported"] == 1
    assert result.counts["not_allowed"] == 1
    assert result.counts["needs_verification"] == 2
    assert "does not mean parking is full" in result.explanation


def test_missing_predictions_are_reported_not_invented():
    result = recommend(_candidates([("near", "S", "", None)]), LOCATIONS, "S",
                       WEEKDAY_MORNING, DESTINATION)
    assert result.status == PREDICTIONS_UNAVAILABLE
    assert result.first_choice is None
    partial = recommend(_candidates([
        ("near", "S", "", float("nan")), ("mid", "S", "", 0.3),
    ]), LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION)
    assert partial.first_choice.location["location_id"] == "mid"
    assert any("no availability estimate" in note for note in partial.limitations)


def test_locations_beyond_walking_limit_are_skipped():
    result = recommend(_candidates([("far", "S", "", 0.9)]), LOCATIONS, "S",
                       WEEKDAY_MORNING, DESTINATION)
    assert result.status == NO_SUITABLE_LOCATION
    assert result.counts["too_far"] == 1


def test_without_destination_availability_decides():
    result = recommend(_candidates([
        ("near", "S", "", 0.3), ("far", "S", "", 0.6),
    ]), LOCATIONS, "S", WEEKDAY_MORNING)
    assert result.first_choice.location["location_id"] == "far"
    assert result.first_choice.estimated_walking_minutes is None
    assert any("walking time was not estimated" in note
               for note in result.limitations)


def test_ties_break_on_location_id():
    result = recommend(_candidates([
        ("mid", "S", "", 0.5), ("near", "S", "", 0.5),
    ]), LOCATIONS, "S", WEEKDAY_MORNING)
    assert result.first_choice.location["location_id"] == "mid"


def test_approximate_pins_are_labeled_and_not_exposed():
    result = recommend(_candidates([("gliderport", "S", "", 0.5)]), LOCATIONS,
                       "S", WEEKDAY_MORNING, DESTINATION)
    choice = result.first_choice
    assert choice.location["coordinates"] is None
    assert "(approximate pin)" in choice.explanation


def test_longest_explanation_fits_api_limit():
    # Longest eligible stall label, every optional sentence, both comparisons.
    first, backup = (recommend(_candidates([(loc, "Visitor", "2-Hour Limit",
                                             frac)]), LOCATIONS, "V",
                               WEEKDAY_MORNING, DESTINATION,
                               WEEKDAY_MORNING.replace(hour=11)).first_choice
                     for loc, frac in (("near", 0.9), ("gliderport", 0.05)))
    backup.allowed_until = datetime(2026, 10, 28, 7, 30)
    backup.estimated_walking_minutes = 19
    text = ranking._explain(backup, "V", first)
    assert "lower availability and a longer walk" in text
    assert len(text) <= 200, text


def test_scoring_formula():
    assert score(0.8, 0, True) == pytest.approx(
        AVAILABILITY_WEIGHT * 0.8 + WALKING_WEIGHT)
    assert score(0.8, 20, True) == pytest.approx(AVAILABILITY_WEIGHT * 0.8)
    assert score(0.8, None, True) == pytest.approx(AVAILABILITY_WEIGHT * 0.8)
    assert score(0.8, None, False) == pytest.approx(0.8)


def test_walking_estimate_matches_website_formula():
    assert walking_minutes(DESTINATION, DESTINATION) == 3
    one_km_north = {"latitude": 32.8800 + 1 / 111.195, "longitude": -117.2400}
    assert walking_minutes(DESTINATION, one_km_north) == 15
    assert walking_minutes(None, DESTINATION) is None


def test_invalid_candidates_raise():
    with pytest.raises(ValueError, match="Missing candidate columns"):
        recommend(pd.DataFrame({"location_id": ["near"]}), LOCATIONS, "S",
                  WEEKDAY_MORNING)
    with pytest.raises(ValueError, match="out of range"):
        recommend(_candidates([("near", "S", "", 1.5)]), LOCATIONS, "S",
                  WEEKDAY_MORNING)


def test_api_output_matches_backend_schema():
    result = recommend(_candidates([
        ("near", "S", "", 0.5), ("mid", "S", "", 0.4),
    ]), LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION)
    payload = result.to_api()
    assert payload["status"] == READY
    for key in ("first_choice", "backup_choice"):
        ParkingChoice(**payload[key])
    empty = recommend(_candidates([]).reindex(columns=[
        "location_id", "facility", "category", "subtype", "level",
        "estimated_available_fraction"]), LOCATIONS, "S", WEEKDAY_MORNING)
    assert empty.to_api()["first_choice"] is None
