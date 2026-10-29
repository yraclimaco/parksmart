"""Tests for permit eligibility rules (Issue #20).

T1-T8 follow section 8 of the team's UCSD Parking Domain Research v1.2.
"""

from datetime import datetime, timedelta, timezone

import pytest

from src.eligibility import (
    ALLOWED,
    NEEDS_VERIFICATION,
    NOT_ALLOWED,
    UCSD_TIME_ZONE,
    check_eligibility,
    stall_category,
    time_limit_minutes,
)

TUESDAY = datetime(2026, 10, 27)  # Ordinary weekday, not a holiday.
SATURDAY = datetime(2026, 10, 31)
SUNDAY = datetime(2026, 11, 1)


def at(day, hour, minute=0):
    return day.replace(hour=hour, minute=minute)


@pytest.mark.parametrize("permit, category, arrival, departure, expected", [
    ("S", "B", at(TUESDAY, 17), at(TUESDAY, 19), ALLOWED),          # T1
    ("S", "B", at(TUESDAY, 10), at(TUESDAY, 12), NOT_ALLOWED),      # T2
    ("B", "A", at(SATURDAY, 12), at(SATURDAY, 14), ALLOWED),        # T3
    ("D", "S", at(TUESDAY, 15), at(TUESDAY, 17), NOT_ALLOWED),      # T4
])
def test_research_session_cases(permit, category, arrival, departure, expected):
    assert check_eligibility(permit, category, "", arrival,
                             departure).status == expected


def test_a_24_7_stalls_need_an_a_permit():  # T8
    assert check_eligibility("S", "A", "24/7 Enforced",
                             at(SUNDAY, 20)).status == NOT_ALLOWED
    assert check_eligibility("A", "A", "24/7 Enforced",
                             at(SUNDAY, 20)).status == ALLOWED


@pytest.mark.parametrize("permit, category, hour, expected", [
    ("A", "S", 10, ALLOWED),
    ("A", "SR", 10, NOT_ALLOWED),
    ("B", "A", 10, NOT_ALLOWED),
    ("B", "A", 16, ALLOWED),
    ("SR", "SR", 10, ALLOWED),
    ("S", "SR", 10, NOT_ALLOWED),
    ("V", "Visitor", 10, ALLOWED),
    ("V", "B", 16, ALLOWED),
    ("V", "A", 16, NOT_ALLOWED),
    ("V", "A", 17, ALLOWED),
    ("A", "Visitor", 10, NOT_ALLOWED),
])
def test_weekday_permit_matrix(permit, category, hour, expected):
    assert check_eligibility(permit, category, "",
                             at(TUESDAY, hour)).status == expected


def test_morning_cutovers_are_permit_specific():
    # B/S/SR/D upgrades end at 8 AM; pay-station V ends at 7:30 AM.
    assert check_eligibility("S", "B", "", at(TUESDAY, 7, 45)).status == ALLOWED
    assert check_eligibility("V", "B", "", at(TUESDAY, 7, 45)).status == (
        NOT_ALLOWED)


def test_visitor_a_window_does_not_extend_to_weekends():
    assert check_eligibility("V", "A", "", at(SATURDAY, 12)).status == NOT_ALLOWED
    assert check_eligibility("V", "B", "", at(SATURDAY, 12)).status == ALLOWED


def test_d_stalls_need_verification_except_for_d_permits():
    assert check_eligibility("D", "D", "", at(TUESDAY, 10)).status == ALLOWED
    for permit in ("A", "B", "S", "SR", "V"):
        result = check_eligibility(permit, "D", "", at(TUESDAY, 10))
        assert result.status == NEEDS_VERIFICATION
        assert "Sept 18, 2026" in result.reason


@pytest.mark.parametrize("category, subtype", [
    ("Reserved", "Blue Pool"), ("Accessible", ""), ("Carpool", "B"),
    ("Electric Vehicle", "EV4"), ("SS", ""), ("B", "Oversized"),
    ("Visitor", "Patient/Visitor Reserved"), ("B", "Preuss"),
    ("Motorcycle Section", ""),
])
def test_specialized_stalls_are_never_allowed(category, subtype):
    for permit in ("A", "B", "S", "SR", "D", "V"):
        assert check_eligibility(permit, category, subtype,
                                 at(TUESDAY, 10)).status == NEEDS_VERIFICATION


def test_time_limited_stalls_need_a_stay_length():
    arrival = at(TUESDAY, 10)
    assert check_eligibility("V", "Visitor", "2 Hours",
                             arrival).status == NEEDS_VERIFICATION
    short = check_eligibility("V", "Visitor", "2 Hours", arrival,
                              arrival + timedelta(hours=1))
    assert short.status == ALLOWED and "120 minutes" in short.reason
    assert check_eligibility("V", "Visitor", "2-Hour Limit", arrival,
                             arrival + timedelta(hours=3)).status == NOT_ALLOWED


def test_whole_stay_fails_when_access_ends_midway():
    # S in B is allowed from 4 PM to 8 AM; a 7-9 AM stay crosses the cutover.
    assert check_eligibility("S", "B", "", at(TUESDAY, 7),
                             at(TUESDAY, 9)).status == NOT_ALLOWED


def test_allowed_until_reports_the_next_cutover():
    result = check_eligibility("S", "B", "", at(TUESDAY, 17))
    assert result.status == ALLOWED
    assert result.allowed_until == datetime(2026, 10, 28, 8,
                                            tzinfo=UCSD_TIME_ZONE)
    assert check_eligibility("S", "S", "", at(TUESDAY, 10)).allowed_until is None


def test_holidays_do_not_borrow_weekend_rules():
    veterans_day = datetime(2026, 11, 11, 10)
    assert check_eligibility("S", "B", "",
                             veterans_day).status == NEEDS_VERIFICATION
    assert check_eligibility("S", "S", "", veterans_day).status == ALLOWED
    assert check_eligibility("S", "B", "",
                             veterans_day.replace(hour=17)).status == ALLOWED


def test_gliderport_overnight_needs_verification():
    assert check_eligibility("S", "S", "", at(TUESDAY, 19),
                             location_id="p386").status == ALLOWED
    assert check_eligibility("S", "S", "", at(TUESDAY, 21),
                             location_id="p386").status == NEEDS_VERIFICATION
    december_evening = datetime(2026, 12, 8, 19)
    assert check_eligibility("S", "S", "", december_evening,
                             location_id="p386").status == NEEDS_VERIFICATION


def test_explicit_offsets_are_converted_to_ucsd_time():
    # 01:00 UTC Wednesday is 6 PM Tuesday in San Diego (PDT).
    arrival = datetime(2026, 10, 28, 1, tzinfo=timezone.utc)
    assert check_eligibility("S", "B", "", arrival).status == ALLOWED


def test_session_steps_across_daylight_saving_change():
    # Clocks fall back on Nov 1, 2026; the stay is checked in elapsed time.
    arrival = datetime(2026, 11, 1, 0, 30, tzinfo=UCSD_TIME_ZONE)
    result = check_eligibility("S", "B", "", arrival, arrival + timedelta(hours=3))
    assert result.status == ALLOWED


def test_invalid_inputs_raise():
    with pytest.raises(ValueError, match="Unknown permit"):
        check_eligibility("X", "A", "", at(TUESDAY, 10))
    with pytest.raises(ValueError, match="after arrival"):
        check_eligibility("S", "S", "", at(TUESDAY, 10), at(TUESDAY, 9))


def test_stall_classification_helpers():
    assert stall_category("B", "") == ("B", "none")
    assert stall_category("A", "24/7 Enforced") == ("A", "a_24_7")
    assert stall_category("Visitor", "5 Min") == ("Visitor", "time_limited")
    assert stall_category("Reserved", "") == (None, "specialized")
    assert time_limit_minutes("2-Hour Limit") == 120
    assert time_limit_minutes("5 Min") == 5
    assert time_limit_minutes("Blue Pool") is None
