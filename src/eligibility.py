"""Permit eligibility for one parking group at a given time.

Rules come from the team's "UCSD Parking Domain Research v1.2" (Oct 11, 2026),
sections 1-5, which cite https://transportation.ucsd.edu/commute/permits/index.html
(S1), https://transportation.ucsd.edu/contact/news.html (S2),
https://transportation.ucsd.edu/visit/parking.html (S4) and
https://transportation.ucsd.edu/contact/citations/avoiding.html (S5).
Rules last checked against that document on 2026-10-28.

Every check returns ALLOWED, NOT_ALLOWED or NEEDS_VERIFICATION. Unknown or
conflicting permissions are NEEDS_VERIFICATION, never ALLOWED. Only ordinary
A/B/S/SR/D/Visitor stalls and posted A 24/7 stalls have modeled rules; reserved,
accessible, carpool, EV, special-access and other specialized stalls always
need verification. Lot-level supplemental permits are handled by the location
registry's ``registry_status``, not here.
"""

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional
from zoneinfo import ZoneInfo

from .ucsd_calendar import UNIVERSITY_HOLIDAYS

UCSD_TIME_ZONE = ZoneInfo("America/Los_Angeles")
ALLOWED = "allowed"
NOT_ALLOWED = "not_allowed"
NEEDS_VERIFICATION = "needs_verification"

PERMIT_TYPES = ("A", "B", "S", "SR", "D", "V")
ORDINARY_CATEGORIES = {"A", "B", "S", "SR", "D", "Visitor"}
A_24_7_SUBTYPE = "24/7 Enforced"
# Every published rule boundary (8:00, 7:30, 4 PM, midnight...) is a multiple
# of BOUNDARY_GRID_MINUTES past midnight, so access cannot change between grid
# marks. Stays are checked at arrival and at every mark before departure.
BOUNDARY_GRID_MINUTES = 30
STEP_MINUTES = 15  # divides the grid, so every boundary is a checked mark
STEP = timedelta(minutes=STEP_MINUTES)
# How far ahead to look for the end of a valid window ("valid until 8:00 AM").
ACCESS_HORIZON = timedelta(hours=24)

# University holidays come from src.ucsd_calendar (official 2026-27 calendar).
# Fees are waived, but whether weekday category limits still apply is
# unresolved (research section 3, S10), so holidays need verification.


def _minutes(hour, minute=0):
    return hour * 60 + minute


@dataclass(frozen=True)
class Window:
    """Overnight window from ``start`` to ``end`` (minutes after midnight).

    ``weekends`` True also allows all of Saturday and Sunday.
    """

    start: int
    end: int
    weekends: bool


ALWAYS = "always"
# 4 PM-8 AM weekdays, all day weekends: the B/S/SR/D upgrade window (S1).
STANDARD_UPGRADE = Window(_minutes(16), _minutes(8), weekends=True)
# Pay-station V: S/B 4 PM-7:30 AM weekdays and weekends; A 5 PM-7:30 AM daily (S4).
VISITOR_UPGRADE = Window(_minutes(16), _minutes(7, 30), weekends=True)
VISITOR_A = Window(_minutes(17), _minutes(7, 30), weekends=False)

# Stall category -> rule, per permit. Missing pairs are NOT_ALLOWED.
PERMIT_RULES = {
    "A": {"A": ALWAYS, "B": ALWAYS, "S": ALWAYS, "D": ALWAYS},
    "B": {"B": ALWAYS, "S": ALWAYS, "D": ALWAYS, "A": STANDARD_UPGRADE},
    "S": {"S": ALWAYS, "D": ALWAYS, "A": STANDARD_UPGRADE,
          "B": STANDARD_UPGRADE},
    "SR": {"SR": ALWAYS, "S": ALWAYS, "D": ALWAYS, "A": STANDARD_UPGRADE,
           "B": STANDARD_UPGRADE},
    "D": {"D": ALWAYS, "A": STANDARD_UPGRADE, "B": STANDARD_UPGRADE,
          "S": STANDARD_UPGRADE},
    "V": {"Visitor": ALWAYS, "D": ALWAYS, "S": VISITOR_UPGRADE,
          "B": VISITOR_UPGRADE, "A": VISITOR_A},
}

# Gliderport P386: D/V overnight parking is prohibited but the boundary is not
# published (research section 4); the SuperSaver daylight window is used to
# flag, never to allow. Months are inclusive.
GLIDERPORT_ID = "p386"
GLIDERPORT_WINTER = (_minutes(6), _minutes(18))   # Nov-Mar
GLIDERPORT_SUMMER = (_minutes(6), _minutes(20))   # Apr-Oct
GLIDERPORT_SUMMER_MONTHS = range(4, 11)            # April through October
SATURDAY = 5  # datetime.weekday(): Monday is 0, so 5 and 6 are the weekend

TIME_LIMIT_PATTERN = re.compile(
    r"^(\d+)[ -]?(min|minute|minutes|hour|hours)(?: limit)?$", re.IGNORECASE
)


@dataclass(frozen=True)
class Eligibility:
    """Result of one permit/stall check.

    status: ALLOWED, NOT_ALLOWED or NEEDS_VERIFICATION.
    reason: short plain-language explanation.
    allowed_until: for an ALLOWED arrival-only check, when access next ends
        within ACCESS_HORIZON; None if it does not end in that time.
    """

    status: str
    reason: str
    allowed_until: Optional[datetime] = None


def to_ucsd_time(moment):
    """Return ``moment`` in UCSD time; naive datetimes are taken as UCSD local."""
    if moment.tzinfo is None:
        return moment.replace(tzinfo=UCSD_TIME_ZONE)
    return moment.astimezone(UCSD_TIME_ZONE)


def clock(value):
    """Format "HH:MM" text or a datetime as "8:00 AM" (no platform strftime flags)."""
    if isinstance(value, str):
        value = datetime.strptime(value, "%H:%M")
    hour = value.hour % 12 or 12
    return f"{hour}:{value.minute:02d} {'AM' if value.hour < 12 else 'PM'}"


def time_limit_minutes(subtype):
    """Return the posted time limit in minutes for subtypes like "2 Hours"."""
    match = TIME_LIMIT_PATTERN.match((subtype or "").strip())
    if not match:
        return None
    amount, unit = int(match.group(1)), match.group(2).lower()
    return amount * 60 if unit.startswith("hour") else amount


def stall_category(category, subtype=""):
    """Classify a dataset parking group for eligibility.

    Args:
        category: standardized category (e.g. "B", "Visitor", "Reserved").
        subtype: standardized subtype; blank means unspecified.
    Returns:
        (base, restriction): base is an ordinary category or None; restriction
        is "none", "a_24_7", "time_limited" or "specialized".
    """
    category = (category or "").strip()
    subtype = (subtype or "").strip()
    if category not in ORDINARY_CATEGORIES:
        return None, "specialized"
    if not subtype:
        return category, "none"
    if category == "A" and subtype == A_24_7_SUBTYPE:
        return "A", "a_24_7"
    if time_limit_minutes(subtype) is not None:
        return category, "time_limited"
    return None, "specialized"


def check_eligibility(permit, category, subtype, arrival, departure=None,
                      location_id=None):
    """Check whether ``permit`` may park in one parking group.

    Args:
        permit: one of PERMIT_TYPES ("V" means a pay-station visitor permit).
        category, subtype: standardized dataset labels for the group.
        arrival: datetime; naive values are UCSD local time.
        departure: optional datetime. With it, the whole stay is checked;
            without it, only the arrival moment.
        location_id: registry ID, for lot-specific rules (Gliderport).
    Returns:
        Eligibility.
    Raises:
        ValueError: unknown permit, or departure not after arrival.
    """
    if permit not in PERMIT_TYPES:
        raise ValueError(f"Unknown permit type {permit!r}; use {PERMIT_TYPES}")
    arrival = to_ucsd_time(arrival)
    if departure is not None:
        departure = to_ucsd_time(departure)
        if departure <= arrival:
            raise ValueError("departure must be after arrival")

    base, restriction = stall_category(category, subtype)
    label = _stall_label(category, subtype)
    if restriction == "specialized":
        return Eligibility(NEEDS_VERIFICATION,
                           f"{label} stalls have restrictions ParkSmart does "
                           "not model; check posted signs.")
    if restriction == "a_24_7":
        if permit == "A":
            return Eligibility(ALLOWED, "A permits may use posted A 24/7 stalls.")
        return Eligibility(NOT_ALLOWED,
                           "Posted A 24/7 stalls need an A permit at all times.")
    if restriction == "time_limited":
        limit = time_limit_minutes(subtype)
        if departure is None:
            return Eligibility(NEEDS_VERIFICATION,
                               f"{label} stalls have a {limit}-minute limit; "
                               "stay length is unknown.")
        if departure - arrival > timedelta(minutes=limit):
            return Eligibility(NOT_ALLOWED,
                               f"Stay is longer than the {limit}-minute limit.")

    moments = _session_moments(arrival, departure)
    results = [_check_moment(permit, base, moment, location_id)
               for moment in moments]
    statuses = {result.status for result in results}
    if NOT_ALLOWED in statuses:
        return next(r for r in results if r.status == NOT_ALLOWED)
    if NEEDS_VERIFICATION in statuses:
        return next(r for r in results if r.status == NEEDS_VERIFICATION)
    until = None if departure else _allowed_until(permit, base, arrival,
                                                  location_id)
    reason = results[0].reason
    if restriction == "time_limited":
        reason = f"{reason[:-1]}, for up to {time_limit_minutes(subtype)} minutes."
    return Eligibility(ALLOWED, reason, until)


def _check_moment(permit, base, moment, location_id):
    """Check one ordinary stall category at one instant."""
    rule = PERMIT_RULES[permit].get(base)
    stall = "Visitor" if base == "Visitor" else base
    if rule is None:
        return Eligibility(NOT_ALLOWED,
                           f"{permit} permits cannot use {stall} stalls.")
    if location_id == GLIDERPORT_ID and not _gliderport_daylight(moment):
        return Eligibility(NEEDS_VERIFICATION,
                           "Gliderport (P386) bans overnight parking; the exact "
                           "hours are not published.")
    if base == "D" and permit != "D":
        # Sept 18, 2026 notice limits D parking; effect on other permits is
        # unresolved (research C1).
        return Eligibility(NEEDS_VERIFICATION,
                           f"{permit} access to D stalls is unclear since the "
                           "Sept 18, 2026 D restriction.")
    if rule == ALWAYS:
        return Eligibility(ALLOWED, f"{permit} permits may use {stall} stalls "
                                    "at any time.")
    if _in_window(rule, moment):
        if moment.date() in UNIVERSITY_HOLIDAYS and not _in_window(
                rule, moment, treat_as_weekday=True):
            return Eligibility(NEEDS_VERIFICATION,
                               "University holiday: unclear whether weekday "
                               "stall limits apply.")
        return Eligibility(ALLOWED, f"{permit} permits may use {stall} stalls "
                                    "at this time.")
    if moment.date() in UNIVERSITY_HOLIDAYS and rule.weekends:
        return Eligibility(NEEDS_VERIFICATION,
                           "University holiday: unclear whether weekend stall "
                           "rules apply.")
    return Eligibility(NOT_ALLOWED,
                       f"{permit} permits cannot use {stall} stalls at this time.")


def _in_window(rule, moment, treat_as_weekday=False):
    """Return whether ``moment`` falls inside an overnight Window."""
    weekend = moment.weekday() >= SATURDAY and not treat_as_weekday
    if rule.weekends and weekend:
        return True
    minute = moment.hour * 60 + moment.minute
    return minute >= rule.start or minute < rule.end


def _gliderport_daylight(moment):
    start, end = (GLIDERPORT_SUMMER if moment.month in GLIDERPORT_SUMMER_MONTHS
                  else GLIDERPORT_WINTER)
    minute = moment.hour * 60 + moment.minute
    return start <= minute < end


def _session_moments(arrival, departure):
    """Return the instants to check: arrival, then every grid mark before departure.

    Marks are aligned to the wall clock (:00, :15, :30, :45), not to arrival,
    so a boundary inside the final partial interval is still checked.
    """
    if departure is None:
        return [arrival]
    moments, moment = [arrival], _next_mark(arrival)
    while moment < departure:
        moments.append(moment)
        moment = _later(moment, STEP)
    return moments


def _next_mark(moment):
    """Return the first wall-clock STEP mark strictly after ``moment``."""
    start = moment.replace(second=0, microsecond=0)
    return _later(start, timedelta(minutes=STEP_MINUTES
                                   - start.minute % STEP_MINUTES))


def _allowed_until(permit, base, arrival, location_id):
    """Return the first STEP mark within ACCESS_HORIZON that is not ALLOWED."""
    moment = _next_mark(arrival)
    while moment - arrival <= ACCESS_HORIZON:
        if _check_moment(permit, base, moment, location_id).status != ALLOWED:
            return moment
        moment = _later(moment, STEP)
    return None


def _later(moment, delta):
    """Add elapsed time (not wall-clock time) so DST changes stay correct."""
    return (moment.astimezone(timezone.utc) + delta).astimezone(UCSD_TIME_ZONE)


def _stall_label(category, subtype):
    return f"{category} {subtype}".strip() if subtype else category
