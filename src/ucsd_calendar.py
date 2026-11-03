"""Official UC San Diego 2026-27 calendar dates used by eligibility and estimates.

Source: UC San Diego Academic and Administrative Calendar 2026-2027,
https://blink.ucsd.edu/instructors/resources/academic/calendars/2026.html
(page last updated 2026-10-07; checked 2026-10-31). Only this academic year is
verified. Dates outside VERIFIED_START..VERIFIED_END are not checked for
holidays or quarters, and callers must say so.
"""

from datetime import date

# Fall quarter begins through the last holiday the calendar lists (Labor Day).
VERIFIED_START = date(2026, 9, 21)
VERIFIED_END = date(2027, 9, 6)

UNIVERSITY_HOLIDAYS = {
    date(2026, 11, 11),                       # Veterans Day
    date(2026, 11, 26), date(2026, 11, 27),   # Thanksgiving
    date(2026, 12, 24), date(2026, 12, 25),   # Winter Break
    date(2026, 12, 31), date(2027, 1, 1),     # New Year Holiday
    date(2027, 1, 18),                        # Martin Luther King, Jr.
    date(2027, 2, 15),                        # Presidents' Day
    date(2027, 3, 26),                        # Farmworkers Day
    date(2027, 5, 31),                        # Memorial Day
    date(2027, 6, 18),                        # Juneteenth
    date(2027, 7, 5),                         # Independence Day
    date(2027, 9, 6),                         # Labor Day
}

# Quarter begins/ends from the calendar, inclusive. Summer uses Session I
# instruction start through Session II finals. Breaks belong to no quarter.
QUARTERS = [
    ("Fall", date(2026, 9, 21), date(2026, 12, 12)),
    ("Winter", date(2027, 1, 4), date(2027, 3, 20)),
    ("Spring", date(2027, 3, 24), date(2027, 6, 11)),
    ("Summer", date(2027, 6, 28), date(2027, 9, 4)),
]


def is_verified(day):
    """Return whether ``day`` (a date) is inside the verified calendar range."""
    return VERIFIED_START <= day <= VERIFIED_END


def quarter_for(day):
    """Return the quarter name ("Fall", ...) containing ``day``, or None.

    None means a break between quarters or a date outside the verified range.
    """
    for name, start, end in QUARTERS:
        if start <= day <= end:
            return name
    return None
