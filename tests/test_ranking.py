"""Tests for first-choice/backup ranking (Issue #20)."""

import re
from datetime import datetime
from pathlib import Path
from typing import get_args

import pandas as pd
import pytest

from src import ranking

from src.api.schemas import ParkingChoice, RecommendationResponse
from src.eligibility import UCSD_TIME_ZONE
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


def test_limited_estimates_are_named_in_explanation_and_limitations():
    candidates = _candidates([("near", "S", "", 0.6), ("mid", "S", "", 0.5)])
    candidates["estimate_basis"] = ["level_1", "level_3"]
    candidates["estimate_survey_time"] = "14:00"
    candidates["estimate_note"] = ["2:00 PM surveys; none cover 10:00 PM",
                                   "none cover 10:00 PM; all-day average for "
                                   "these stalls"]
    result = recommend(candidates, LOCATIONS, "S",
                       WEEKDAY_MORNING.replace(hour=22), DESTINATION)
    first, backup = result.first_choice, result.backup_choice
    assert "(2:00 PM surveys; none cover 10:00 PM)" in first.explanation
    assert first.estimate_survey_time == "14:00"
    assert first.estimate_basis == "level_1"
    assert len(backup.explanation) <= ranking.MAX_TEXT_LENGTH
    assert ("First choice estimate is limited: 2:00 PM surveys; none cover "
            "10:00 PM.") in result.limitations
    assert any(note.startswith("Backup estimate is limited: none cover")
               for note in result.limitations)


def test_full_match_estimates_add_no_note():
    candidates = _candidates([("near", "S", "", 0.6)])
    candidates["estimate_note"] = [None]
    result = recommend(candidates, LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION)
    assert "(" not in result.first_choice.explanation
    assert not any("estimate is limited" in n for n in result.limitations)


def test_long_estimate_note_falls_back_to_short_marker():
    first, backup = (recommend(_candidates([(loc, "Visitor", "2-Hour Limit",
                                             frac)]), LOCATIONS, "V",
                               WEEKDAY_MORNING, DESTINATION,
                               WEEKDAY_MORNING.replace(hour=11)).first_choice
                     for loc, frac in (("near", 0.9), ("gliderport", 0.05)))
    backup.allowed_until = datetime(2026, 10, 28, 7, 30)
    backup.estimated_walking_minutes = 19
    backup.estimate_note = ("2:00 PM surveys; none cover 10:00 PM; same time, "
                            "any weekday or quarter")
    text = ranking._explain(backup, "V", first)
    assert "(limited estimate)" in text
    assert len(text) <= ranking.MAX_TEXT_LENGTH, text


def test_dates_outside_verified_calendar_get_a_limitation():
    candidates = _candidates([("near", "S", "", 0.6)])
    inside = recommend(candidates, LOCATIONS, "S", WEEKDAY_MORNING)
    outside = recommend(candidates, LOCATIONS, "S", datetime(2027, 10, 5, 10))
    assert not any("verified only" in n for n in inside.limitations)
    assert any("verified only from Sep 21, 2026 to Sep 6, 2027" in n
               for n in outside.limitations)


def test_every_ranking_status_is_accepted_by_backend_and_website():
    statuses = {READY, NO_SUITABLE_LOCATION, PREDICTIONS_UNAVAILABLE}
    schema = RecommendationResponse.model_fields["status"].annotation
    assert statuses <= set(get_args(schema))
    client = Path("frontend/src/api/recommendations.ts").read_text()
    website = set(re.search(r"export type ApiStatus = ([^;]+);",
                            client).group(1).replace("'", "").split(" | "))
    assert statuses <= website


def test_predictions_unavailable_passes_response_schema():
    candidates = _candidates([("near", "S", "", None)])
    result = recommend(candidates, LOCATIONS, "S", WEEKDAY_MORNING)
    assert result.status == PREDICTIONS_UNAVAILABLE
    response = RecommendationResponse(**result.to_api(), is_example=False,
                                      arrival_time=datetime(
                                          2026, 10, 27, 10,
                                          tzinfo=UCSD_TIME_ZONE))
    assert response.status == PREDICTIONS_UNAVAILABLE
    for note in response.limitations:
        assert len(note) <= ranking.MAX_TEXT_LENGTH


# Routed walking (Issue #25) ------------------------------------------------

def _router(minutes, calls=None):
    """walk_router stand-in returning fixed routed minutes per location."""
    def route_walks(origins, destination):
        if calls is not None:
            calls.append(sorted(origins))
        return {loc: minutes[loc] for loc in origins if loc in minutes}
    return route_walks


def test_routed_walks_replace_straight_line_for_picks():
    calls = []
    result = recommend(_candidates([
        ("near", "S", "", 0.5), ("mid", "S", "", 0.5),
    ]), LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION,
        walk_router=_router({"near": 4, "mid": 9}, calls))
    first, backup = result.first_choice, result.backup_choice
    assert (first.estimated_walking_minutes, backup.estimated_walking_minutes) == (4, 9)
    assert first.walking_source == ranking.WALK_ROUTED
    assert "min walking route" in first.explanation
    assert ranking.ROUTED_NOTE in result.limitations
    assert ranking.STRAIGHT_LINE_NOTE not in result.limitations
    assert calls == [["mid", "near"]]


def test_routed_walk_over_limit_drops_location_and_promotes_next():
    result = recommend(_candidates([
        ("near", "S", "", 0.5), ("mid", "S", "", 0.5),
    ]), LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION,
        walk_router=_router({"near": ranking.MAX_WALK_MINUTES + 3, "mid": 9}))
    assert result.first_choice.location["location_id"] == "mid"
    assert result.backup_choice is None
    assert result.counts["too_far_routed"] == 1
    assert any("by mapped path" in note for note in result.limitations)


def test_longer_routed_walk_can_change_the_order():
    # Straight-line: near wins. Routed: near is a long detour, mid is direct.
    result = recommend(_candidates([
        ("near", "S", "", 0.5), ("mid", "S", "", 0.5),
    ]), LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION,
        walk_router=_router({"near": 18, "mid": 8}))
    assert result.first_choice.location["location_id"] == "mid"


def test_all_routed_walks_too_long_is_no_suitable_location():
    result = recommend(_candidates([("near", "S", "", 0.5)]), LOCATIONS, "S",
                       WEEKDAY_MORNING, DESTINATION,
                       walk_router=_router({"near": 25}))
    assert result.status == NO_SUITABLE_LOCATION


def test_routing_failure_keeps_straight_line_estimates():
    def broken(origins, destination):
        raise RuntimeError("provider down")
    plain = recommend(_candidates([("near", "S", "", 0.5)]), LOCATIONS, "S",
                      WEEKDAY_MORNING, DESTINATION)
    result = recommend(_candidates([("near", "S", "", 0.5)]), LOCATIONS, "S",
                       WEEKDAY_MORNING, DESTINATION, walk_router=broken)
    assert result.first_choice.estimated_walking_minutes == (
        plain.first_choice.estimated_walking_minutes)
    assert result.first_choice.walking_source == ranking.WALK_UNCHECKED
    assert ranking.STRAIGHT_LINE_NOTE in result.limitations
    assert "straight-line, unchecked" in result.first_choice.explanation
    assert any(note.startswith("First choice walking time is a straight-line")
               for note in result.limitations)
    assert result.counts["route_unavailable"] == 1


def test_partly_routed_picks_say_so():
    result = recommend(_candidates([
        ("near", "S", "", 0.5), ("mid", "S", "", 0.5),
    ]), LOCATIONS, "S", WEEKDAY_MORNING, DESTINATION,
        walk_router=_router({"near": 4}))
    assert result.backup_choice.walking_source == ranking.WALK_UNCHECKED
    assert ranking.MIXED_ROUTED_NOTE in result.limitations
    assert any(note.startswith("Backup walking time is a straight-line")
               for note in result.limitations)
    assert not any(note.startswith("First choice walking time")
                   for note in result.limitations)


def test_only_top_locations_are_routed():
    many = [_location(f"lot{i}", 32.8800 + i * 0.0002) for i in range(8)]
    calls = []
    recommend(_candidates([(f"lot{i}", "S", "", 0.5) for i in range(8)]), many,
              "S", WEEKDAY_MORNING, DESTINATION, walk_router=_router({}, calls))
    assert len(calls) == 1 and len(calls[0]) == ranking.ROUTED_WALK_CANDIDATES


def test_no_destination_means_no_routing():
    calls = []
    recommend(_candidates([("near", "S", "", 0.5)]), LOCATIONS, "S",
              WEEKDAY_MORNING, walk_router=_router({"near": 4}, calls))
    assert calls == []


def test_longest_routed_explanation_fits_api_limit():
    first, backup = (recommend(_candidates([(loc, "Visitor", "2-Hour Limit",
                                             frac)]), LOCATIONS, "V",
                               WEEKDAY_MORNING, DESTINATION,
                               WEEKDAY_MORNING.replace(hour=11)).first_choice
                     for loc, frac in (("near", 0.9), ("gliderport", 0.05)))
    backup.allowed_until = datetime(2026, 10, 28, 7, 30)
    backup.estimated_walking_minutes = 19
    backup.walking_source = ranking.WALK_ROUTED
    text = ranking._explain(backup, "V", first)
    assert "walking route" in text
    assert len(text) <= 200, text


def _row_of_lots(count):
    """``count`` S lots stepping north from DESTINATION, nearest first."""
    lots = [_location(f"lot{i}", 32.8802 + i * 0.0002) for i in range(count)]
    return lots, _candidates([(f"lot{i}", "S", "", 0.5) for i in range(count)])


def test_picks_outside_first_routed_group_are_checked_too():
    # Regression: the top 5 all route over the limit, so lot5 and lot6 (never
    # routed in the first round) become the picks; they must be routed too.
    lots, candidates = _row_of_lots(7)
    too_far = {f"lot{i}": ranking.MAX_WALK_MINUTES + 5 for i in range(5)}
    calls = []
    result = recommend(candidates, lots, "S", WEEKDAY_MORNING, DESTINATION,
                       walk_router=_router({**too_far, "lot5": 6, "lot6": 7},
                                           calls))
    assert calls == [[f"lot{i}" for i in range(5)], ["lot5", "lot6"]]
    assert result.first_choice.location["location_id"] == "lot5"
    assert result.first_choice.walking_source == ranking.WALK_ROUTED
    assert result.backup_choice.walking_source == ranking.WALK_ROUTED
    assert result.first_choice.estimated_walking_minutes == 6
    assert ranking.ROUTED_NOTE in result.limitations


def test_picks_not_reached_within_budget_are_labeled_unchecked():
    # The router answers the first round, then its budget is used up.
    lots, candidates = _row_of_lots(7)
    answers = [{f"lot{i}": ranking.MAX_WALK_MINUTES + 5 for i in range(5)}]

    def router(origins, destination):
        return answers.pop() if answers else {}

    result = recommend(candidates, lots, "S", WEEKDAY_MORNING, DESTINATION,
                       walk_router=router)
    for label, pick in (("First choice", result.first_choice),
                        ("Backup", result.backup_choice)):
        assert pick.walking_source == ranking.WALK_UNCHECKED
        assert "walking route" not in pick.explanation
        assert "straight-line, unchecked" in pick.explanation
        assert (f"{label} walking time is a straight-line estimate; its mapped "
                f"path was not checked against the {ranking.MAX_WALK_MINUTES}"
                "-minute limit.") in result.limitations
    assert ranking.ROUTED_NOTE not in result.limitations
    assert ranking.MIXED_ROUTED_NOTE not in result.limitations
    for note in result.limitations:
        assert len(note) <= ranking.MAX_TEXT_LENGTH


def test_routing_rounds_are_bounded():
    lots, candidates = _row_of_lots(15)
    calls = []
    result = recommend(candidates, lots, "S", WEEKDAY_MORNING, DESTINATION,
                       walk_router=_router({f"lot{i}": 30 for i in range(15)},
                                           calls))
    assert len(calls) == ranking.MAX_ROUTING_ROUNDS
    assert sum(len(batch) for batch in calls) == (
        ranking.ROUTED_WALK_CANDIDATES + 2 * (ranking.MAX_ROUTING_ROUNDS - 1))
    assert result.first_choice.walking_source == ranking.WALK_UNCHECKED


def test_without_routing_picks_keep_the_plain_straight_line_label():
    result = recommend(_candidates([("near", "S", "", 0.5)]), LOCATIONS, "S",
                       WEEKDAY_MORNING, DESTINATION)
    assert result.first_choice.walking_source == ranking.WALK_STRAIGHT_LINE
    assert "straight-line, unchecked" not in result.first_choice.explanation
    assert not any("was not checked against" in n for n in result.limitations)


def test_longest_unchecked_explanation_fits_api_limit():
    first, backup = (recommend(_candidates([(loc, "Visitor", "2-Hour Limit",
                                             frac)]), LOCATIONS, "V",
                               WEEKDAY_MORNING, DESTINATION,
                               WEEKDAY_MORNING.replace(hour=11)).first_choice
                     for loc, frac in (("near", 0.9), ("gliderport", 0.05)))
    backup.allowed_until = datetime(2026, 10, 28, 7, 30)
    backup.estimated_walking_minutes = 19
    backup.walking_source = ranking.WALK_UNCHECKED
    backup.estimate_note = "2:00 PM surveys; none cover 10:00 PM"
    text = ranking._explain(backup, "V", first)
    assert "straight-line, unchecked" in text
    assert len(text) <= ranking.MAX_TEXT_LENGTH, text
