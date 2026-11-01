"""Tests for the official 2026-27 UC San Diego calendar dates."""

from datetime import date

import pytest

from src.ucsd_calendar import (
    QUARTERS,
    UNIVERSITY_HOLIDAYS,
    VERIFIED_END,
    VERIFIED_START,
    is_verified,
    quarter_for,
)


def test_all_listed_holidays_are_present_and_verified():
    # 11 named holidays covering 14 days, Fall 2026 to Summer 2027.
    assert len(UNIVERSITY_HOLIDAYS) == 14
    assert {date(2027, 1, 18), date(2027, 2, 15), date(2027, 3, 26),
            date(2027, 5, 31), date(2027, 6, 18), date(2027, 7, 5),
            date(2027, 9, 6)} <= UNIVERSITY_HOLIDAYS
    assert all(is_verified(day) for day in UNIVERSITY_HOLIDAYS)


def test_verified_range_edges():
    assert is_verified(VERIFIED_START) and is_verified(VERIFIED_END)
    assert not is_verified(date(2026, 9, 20))
    assert not is_verified(date(2027, 9, 7))


@pytest.mark.parametrize("day, expected", [
    (date(2026, 9, 21), "Fall"),
    (date(2026, 12, 12), "Fall"),
    (date(2026, 12, 20), None),      # winter break
    (date(2027, 1, 4), "Winter"),
    (date(2027, 3, 22), None),       # spring break
    (date(2027, 4, 1), "Spring"),
    (date(2027, 7, 1), "Summer"),
    (date(2027, 10, 1), None),       # outside the verified year
])
def test_quarter_for(day, expected):
    assert quarter_for(day) == expected


def test_quarters_are_ordered_and_inside_the_verified_range():
    for index, (_, start, end) in enumerate(QUARTERS):
        assert start <= end
        if index + 1 < len(QUARTERS):
            assert end < QUARTERS[index + 1][1]
    assert all(is_verified(start) and is_verified(end)
               for _, start, end in QUARTERS)
