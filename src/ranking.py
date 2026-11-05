"""Rank eligible parking and pick a first choice and a distinct backup.

Callers (the FastAPI endpoint) supply one row per current parking group with
its predicted availability. This module filters by registry status and permit
eligibility, estimates walking time, scores each eligible group, keeps the
best group per location, and returns the top two locations with explanations.
Scoring weights, walking assumptions and tie-breaking are documented in
docs/recommendations.md.
"""

import logging
import math
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from .eligibility import (ALLOWED, NEEDS_VERIFICATION, check_eligibility,
                          clock, to_ucsd_time)
from .ucsd_calendar import VERIFIED_END, VERIFIED_START, is_verified

LOGGER = logging.getLogger(__name__)

# Same weights as the website prototype (frontend/src/constants.ts). These are
# the "balanced" preference and the default.
AVAILABILITY_WEIGHT = 0.65
WALKING_WEIGHT = 0.35
# Walking score falls linearly from 1 at 0 min to 0 at this many minutes;
# locations farther than this are not recommended.
MAX_WALK_MINUTES = 20
# What the user cares about most (Yra's review of the website, 2026-11-05).
# Each maps to (availability weight, walking weight). "balanced" keeps the
# original prototype weights; the other two are starting points to revisit
# with the experts, not tuned values.
SHORTER_WALK = "shorter_walk"
BALANCED = "balanced"
MORE_AVAILABILITY = "more_availability"
PREFERENCE_WEIGHTS = {
    SHORTER_WALK: (0.20, 0.80),
    BALANCED: (AVAILABILITY_WEIGHT, WALKING_WEIGHT),
    MORE_AVAILABILITY: (0.85, 0.15),
}
PREFERENCES = tuple(PREFERENCE_WEIGHTS)
PREFERENCE_LABELS = {SHORTER_WALK: "shorter walk first", BALANCED: "balanced",
                     MORE_AVAILABILITY: "more space first"}
# A user's own walking limit may be shorter than MAX_WALK_MINUTES, never
# longer, and not below the shortest straight-line estimate.
MIN_WALK_LIMIT_MINUTES = 3
# Ranked locations returned for map markers and detail cards, best first.
MAX_RANKED_OPTIONS = 12
# Straight-line walking estimate, matching the website: about 13 min per km
# plus a 2-minute buffer, never below 3 minutes. Not a routed path.
WALK_MINUTES_PER_KM = 13
WALK_BUFFER_MINUTES = 2
MIN_WALK_MINUTES = 3
EARTH_RADIUS_KM = 6371.0
# Matches the near-full threshold in src/parking_benchmarks.py (10% open).
NEAR_FULL_FRACTION = 0.10
# Routed walking (Issue #25): the best few locations by straight-line score
# are routed first. Straight-line estimates are usually, but not always,
# shorter than mapped paths (the pilot in docs/routing.md found paths 1.2-1.4x
# the straight line), so a location outside this group can still end up as a
# pick; the picks are then routed too, a few at a time, until both are checked
# or the request's routing budget runs out.
ROUTED_WALK_CANDIDATES = 5
# Routing rounds per request: the first routes ROUTED_WALK_CANDIDATES
# locations, each later one only the current first choice and backup that are
# not yet checked (at most 2), so one request makes at most 5 + 2 * 3 = 11
# provider calls (fewer once routes are cached).
MAX_ROUTING_ROUNDS = 4
WALK_STRAIGHT_LINE = "straight_line"
WALK_ROUTED = "routed"
# Routing was on but this location's path was not checked (not reached within
# the request's budget, or the route failed): the straight-line time stands
# and the 20-minute limit was only checked in a straight line.
WALK_UNCHECKED = "straight_line_unchecked"
STRAIGHT_LINE_NOTE = ("Walking times are straight-line estimates, not routed "
                      "walking paths.")
ROUTED_NOTE = ("Walking times follow mapped walking paths from each parking "
               "location's map point; check signs for closures.")
MIXED_ROUTED_NOTE = ("Walking times follow mapped walking paths where available; "
                     "others are straight-line estimates.")
# How explanations name each walking-time source.
WALK_KINDS = {WALK_ROUTED: "walking route",
              WALK_UNCHECKED: "walk (straight-line, unchecked)"}
# Compact wording used only when the full explanation would be too long.
WALK_KINDS_SHORT = {WALK_ROUTED: "walking route",
                    WALK_UNCHECKED: "walk (unchecked)"}
# API Text fields (explanations, limitations) allow at most 200 characters.
MAX_TEXT_LENGTH = 200

READY = "ready"
NO_SUITABLE_LOCATION = "no_suitable_location"
PREDICTIONS_UNAVAILABLE = "predictions_unavailable"

REQUIRED_COLUMNS = ["location_id", "facility", "category", "subtype", "level",
                    "estimated_available_fraction"]
BASE_LIMITATIONS = [
    "Availability is an estimate from historical surveys, not live occupancy "
    "or a guaranteed space.",
    STRAIGHT_LINE_NOTE,
    "Check posted signs: closures, events and reserved areas can override "
    "permit rules.",
]


@dataclass
class Choice:
    """One recommended location and the parking group that earned it."""

    location: dict
    parking_group: dict
    estimated_available_fraction: float
    estimate_basis: Optional[str]
    estimated_walking_minutes: Optional[float]
    walking_is_approximate: bool
    score: float
    eligibility_reason: str
    allowed_until: Optional[object]
    explanation: str = ""
    estimate_survey_time: Optional[str] = None
    estimate_note: Optional[str] = None
    walking_source: str = WALK_STRAIGHT_LINE
    fit_reason: Optional[str] = None
    rank: Optional[int] = None

    def to_api(self):
        """Return fields matching src.api.schemas.ParkingChoice."""
        walking_known = self.estimated_walking_minutes is not None
        return {
            "location": self.location,
            "estimated_available_fraction": self.estimated_available_fraction,
            "estimated_walking_minutes": self.estimated_walking_minutes,
            "walking_time_source": self.walking_source if walking_known else None,
            "explanation": self.explanation,
            "fit_reason": self.fit_reason,
            "rank": self.rank,
        }


@dataclass
class RecommendationResult:
    """Ranking outcome; ``status`` says whether choices exist.

    ready: first_choice is set (backup may be None).
    no_suitable_location: evaluation found no eligible, scorable option.
    predictions_unavailable: eligible options exist but none has an estimate.
    Neither unavailable status means parking is full.
    """

    status: str
    first_choice: Optional[Choice]
    backup_choice: Optional[Choice]
    explanation: str
    limitations: List[str]
    counts: dict = field(default_factory=dict)
    options: List[Choice] = field(default_factory=list)
    preference: str = BALANCED
    max_walk_minutes: int = MAX_WALK_MINUTES

    def to_api(self):
        """Return status, choices, ranked options, settings and notes for the API."""
        return {
            "status": self.status,
            "preference": self.preference,
            "max_walk_minutes": self.max_walk_minutes,
            "first_choice": self.first_choice and self.first_choice.to_api(),
            "backup_choice": self.backup_choice and self.backup_choice.to_api(),
            "options": [choice.to_api() for choice in self.options],
            "explanation": self.explanation,
            "limitations": self.limitations,
        }


def walking_minutes(origin, destination):
    """Estimate walking minutes between two coordinate dicts.

    Args:
        origin, destination: {"latitude": ..., "longitude": ...} or None.
    Returns:
        Whole minutes (straight-line estimate), or None if either is missing.
    """
    if not origin or not destination:
        return None
    lat1, lon1 = map(math.radians, (origin["latitude"], origin["longitude"]))
    lat2, lon2 = map(math.radians,
                     (destination["latitude"], destination["longitude"]))
    a = (math.sin((lat2 - lat1) / 2) ** 2
         + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2)
    km = 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))
    return max(MIN_WALK_MINUTES, round(km * WALK_MINUTES_PER_KM)
               + WALK_BUFFER_MINUTES)


def score(fraction, walk_minutes, walking_known, preference=BALANCED):
    """Score one option from 0 to 1.

    Args:
        fraction: estimated available fraction, 0-1.
        walk_minutes: estimated minutes, or None.
        walking_known: whether any candidate has a walking estimate. If none
            do, availability alone decides; if some do, unknown walks score 0.
        preference: key of PREFERENCE_WEIGHTS.
    Returns:
        Weighted score. The walking part always scales against
        MAX_WALK_MINUTES, so scores stay comparable across walking limits.
    """
    if not walking_known:
        return fraction
    availability_weight, walking_weight = PREFERENCE_WEIGHTS[preference]
    walk_score = 0.0 if walk_minutes is None else max(
        0.0, min(1.0, (MAX_WALK_MINUTES - walk_minutes) / MAX_WALK_MINUTES))
    return availability_weight * fraction + walking_weight * walk_score


def check_settings(preference, max_walk_minutes):
    """Validate a preference and walking limit.

    Args:
        preference: one of PREFERENCES.
        max_walk_minutes: None for MAX_WALK_MINUTES, or whole minutes from
            MIN_WALK_LIMIT_MINUTES to MAX_WALK_MINUTES.
    Returns:
        The walking limit to apply, in minutes.
    Raises:
        ValueError: unknown preference or a limit out of range.
    """
    if preference not in PREFERENCE_WEIGHTS:
        raise ValueError(f"Unknown preference {preference!r}; use "
                         f"{', '.join(PREFERENCES)}.")
    if max_walk_minutes is None:
        return MAX_WALK_MINUTES
    whole = (isinstance(max_walk_minutes, int)
             and not isinstance(max_walk_minutes, bool))
    if not whole or not MIN_WALK_LIMIT_MINUTES <= max_walk_minutes <= MAX_WALK_MINUTES:
        raise ValueError(f"max_walk_minutes must be a whole number from "
                         f"{MIN_WALK_LIMIT_MINUTES} to {MAX_WALK_MINUTES}.")
    return max_walk_minutes


def recommend(candidates, locations, permit, arrival, destination=None,
              departure=None, walk_router=None, preference=BALANCED,
              max_walk_minutes=None):
    """Pick a first choice and a distinct backup for one request.

    Args:
        candidates: DataFrame, one row per current parking group, with
            REQUIRED_COLUMNS (fraction NaN/None when no estimate) and the
            optional ``estimate_basis``, ``estimate_survey_time`` and
            ``estimate_note`` columns from
            ``src.availability.AvailabilityEstimator.attach``. A note marks a
            limited estimate and is shown in the explanation and limitations.
        locations: validated registry list (src.location_registry).
        permit: permit code (see src.eligibility.PERMIT_TYPES).
        arrival: datetime; naive values are UCSD local time.
        destination: optional coordinate dict for walking estimates.
        departure: optional datetime to check the whole stay.
        walk_router: optional callable ``(origins, destination) -> minutes``
            where ``origins`` maps location IDs to coordinate dicts and the
            result maps location IDs to routed walking minutes (missing or
            None when a route is unavailable). The best ROUTED_WALK_CANDIDATES
            locations are routed, then any unchecked first choice or backup
            (up to MAX_ROUTING_ROUNDS calls in all); routes over
            MAX_WALK_MINUTES are dropped and the rest are rescored. A pick
            whose route failed or was not reached keeps its straight-line
            estimate and is labeled unchecked. See src.routing.walk_router.
        preference: PREFERENCES key setting the walking/availability weights.
        max_walk_minutes: optional personal walking limit (see
            check_settings); locations over it are not recommended.
    Returns:
        RecommendationResult; ``options`` lists up to MAX_RANKED_OPTIONS
        ranked locations, each with a ``fit_reason``.
    Raises:
        ValueError: missing columns, unknown permit or preference, invalid
            walking limit, or invalid times.
    """
    walk_limit = check_settings(preference, max_walk_minutes)
    missing = set(REQUIRED_COLUMNS) - set(candidates.columns)
    if missing:
        raise ValueError(f"Missing candidate columns: {sorted(missing)}")
    registry = {location["location_id"]: location for location in locations}
    walks = {
        location_id: walking_minutes(location["coordinates"], destination)
        for location_id, location in registry.items()
    }
    walking_known = destination is not None

    counts = {"candidate_groups": len(candidates), "not_supported": 0,
              "not_allowed": 0, "needs_verification": 0, "too_far": 0,
              "missing_estimate": 0, "scored": 0, "too_far_routed": 0,
              "route_unavailable": 0}
    scored = []
    for row in candidates.itertuples(index=False):
        location = registry.get(row.location_id)
        if location is None or location["registry_status"] != "supported":
            counts["not_supported"] += 1
            continue
        subtype = "" if pd.isna(row.subtype) else str(row.subtype)
        result = check_eligibility(permit, row.category, subtype, arrival,
                                   departure, location_id=row.location_id)
        if result.status != ALLOWED:
            key = ("needs_verification" if result.status == NEEDS_VERIFICATION
                   else "not_allowed")
            counts[key] += 1
            continue
        walk = walks[row.location_id]
        if walk is not None and walk > walk_limit:
            counts["too_far"] += 1
            continue
        fraction = row.estimated_available_fraction
        if fraction is None or pd.isna(fraction):
            counts["missing_estimate"] += 1
            continue
        fraction = float(fraction)
        if not 0 <= fraction <= 1:
            raise ValueError(f"Estimate out of range for {row.location_id}")
        counts["scored"] += 1
        scored.append(Choice(
            location=_api_location(location),
            parking_group={"facility": row.facility, "category": row.category,
                           "subtype": subtype,
                           "level": "" if pd.isna(row.level) else str(row.level)},
            estimated_available_fraction=fraction,
            estimate_basis=getattr(row, "estimate_basis", None),
            estimated_walking_minutes=walk,
            walking_is_approximate=location["coordinate_status"] != "verified",
            score=score(fraction, walk, walking_known, preference),
            eligibility_reason=result.reason,
            allowed_until=result.allowed_until,
            estimate_survey_time=_optional(row, "estimate_survey_time"),
            estimate_note=_optional(row, "estimate_note"),
        ))

    best = {}
    for choice in sorted(scored, key=_sort_key):
        best.setdefault(choice.location["location_id"], choice)
    ranked = sorted(best.values(), key=_sort_key)
    if walk_router is not None and walking_known and ranked:
        ranked = _apply_routed_walks(ranked, registry, destination, walk_router,
                                     counts, walk_limit, preference)
    limitations = _limitations(counts, walking_known, arrival, departure)
    if walk_limit != MAX_WALK_MINUTES:
        limitations.append(f"Only parking within your {walk_limit}-minute "
                           "walking limit was considered.")
    settings = {"preference": preference, "max_walk_minutes": walk_limit}

    if not ranked:
        # Describe walking sources and locations dropped by routed walk (no
        # picks); only blame missing estimates when nothing was even scored
        _note_walking_sources(limitations, [], counts, walk_limit)
        if counts["missing_estimate"] and not counts["scored"]:
            return RecommendationResult(
                PREDICTIONS_UNAVAILABLE, None, None,
                "Your permit can use some nearby parking, but no availability "
                "estimate exists for it at this time.", limitations, counts,
                **settings)
        return RecommendationResult(
            NO_SUITABLE_LOCATION, None, None,
            "No supported parking matched your permit, arrival time and "
            "walking limit. This does not mean parking is full.",
            limitations, counts, **settings)

    options = ranked[:MAX_RANKED_OPTIONS]
    first = options[0]
    backup = options[1] if len(options) > 1 else None
    for position, choice in enumerate(options, start=1):
        choice.rank = position
        choice.explanation = _explain(choice, permit,
                                      first if position == 2 else None)
    for choice, reason in zip(options, _fit_reasons(options, preference,
                                                    walking_known)):
        choice.fit_reason = reason
    _note_walking_sources(limitations, [("First choice", first),
                                        ("Backup", backup)], counts,
                          walk_limit)
    for label, choice in (("First choice", first), ("Backup", backup)):
        if choice is not None and choice.estimate_note:
            limitations.append(f"{label} estimate is limited: "
                               f"{choice.estimate_note}.")
    summary = (f"{first.location['name']} scored highest on expected "
               "availability and walking distance "
               f"({PREFERENCE_LABELS[preference]}).")
    if backup is None:
        summary += " No second suitable location was found."
    return RecommendationResult(READY, first, backup, summary, limitations,
                                counts, options, **settings)


def _apply_routed_walks(ranked, registry, destination, walk_router, counts,
                        walk_limit=MAX_WALK_MINUTES, preference=BALANCED):
    """Replace straight-line walks with routed ones until both picks are checked.

    The first round routes the top ROUTED_WALK_CANDIDATES locations; each later
    round routes whichever of the current first choice and backup are not yet
    checked, until both are checked, MAX_ROUTING_ROUNDS is reached or the router
    (which owns the request's time budget) returns nothing more. Locations whose
    route is over ``walk_limit`` are removed and routed ones are rescored with
    the ``preference`` weights.
    Every other location keeps its straight-line estimate, labeled
    WALK_UNCHECKED.
    """
    for choice in ranked:
        if choice.estimated_walking_minutes is not None:
            choice.walking_source = WALK_UNCHECKED
    attempted = set()
    batch = ranked[:ROUTED_WALK_CANDIDATES]
    for _ in range(MAX_ROUTING_ROUNDS):
        batch = [choice for choice in batch
                 if choice.location["location_id"] not in attempted]
        if not batch:
            break
        attempted.update(choice.location["location_id"] for choice in batch)
        minutes = _route_walks(batch, registry, destination, walk_router)
        dropped = set()
        for choice in batch:
            location_id = choice.location["location_id"]
            routed = minutes.get(location_id)
            if routed is None:
                # Counts only locations actually sent to the router
                if registry[location_id]["coordinates"]:
                    counts["route_unavailable"] += 1
            elif routed > walk_limit:
                counts["too_far_routed"] += 1
                dropped.add(location_id)
            else:
                choice.estimated_walking_minutes = routed
                choice.walking_source = WALK_ROUTED
                choice.score = score(choice.estimated_available_fraction, routed,
                                     True, preference)
        ranked = sorted((choice for choice in ranked
                         if choice.location["location_id"] not in dropped),
                        key=_sort_key)
        batch = ranked[:2]
    return ranked


def _route_walks(batch, registry, destination, walk_router):
    """Call the router for one batch; an outage returns no routes."""
    origins = {}
    for choice in batch:
        location_id = choice.location["location_id"]
        coordinates = registry[location_id]["coordinates"]
        if coordinates:
            origins[location_id] = coordinates
    if not origins:
        return {}
    try:
        return walk_router(origins, destination) or {}
    except Exception as error:  # a routing outage must not break recommendations
        LOGGER.warning("Routed walking times unavailable: %s", error)
        return {}


def _note_walking_sources(limitations, picks, counts,
                          walk_limit=MAX_WALK_MINUTES):
    """Describe where the picks' walking times came from.

    Args:
        limitations: list to update in place.
        picks: (label, Choice or None) pairs for the first choice and backup.
        counts: ranking counts (``too_far_routed``).
        walk_limit: walking limit applied to this request, in minutes.
    """
    sources = {choice.walking_source for _, choice in picks if choice is not None
               and choice.estimated_walking_minutes is not None}
    # Mapped paths were used if a pick was routed or a location was dropped by
    # its routed walk; straight-line estimates were used if a pick has one or a
    # location was filtered by its straight-line time (same rule with or
    # without picks).
    routed_any = WALK_ROUTED in sources or counts["too_far_routed"] > 0
    straight_any = bool(sources - {WALK_ROUTED}) or counts["too_far"] > 0
    if routed_any and STRAIGHT_LINE_NOTE in limitations:
        index = limitations.index(STRAIGHT_LINE_NOTE)
        limitations[index] = MIXED_ROUTED_NOTE if straight_any else ROUTED_NOTE
    for label, choice in picks:
        if choice is not None and choice.walking_source == WALK_UNCHECKED:
            limitations.append(
                f"{label} walking time is a straight-line estimate; its mapped "
                f"path was not checked against the {walk_limit}-minute "
                "limit.")
    if counts["too_far_routed"]:
        count = counts["too_far_routed"]
        subject = ("1 parking location was" if count == 1
                   else f"{count} parking locations were")
        limitations.append(f"{subject} over a {walk_limit}-minute walk by "
                           "mapped path and not recommended.")


def _fit_reasons(options, preference, walking_known):
    """One short sentence per ranked option saying why it ranks where it does.

    Each option is compared, on the factor the user prioritized, with the
    closest and the most open of the ranked ``options``. Walking times are only
    compared within the same kind (mapped path vs straight-line estimate), so a
    routed walk is never called longer than an unchecked straight-line guess.
    Best and tied-best use exact values, not rounded percents. Percentages are
    shares of spaces open in past surveys, never a chance of finding a space.

    Returns:
        List of strings (at most MAX_TEXT_LENGTH characters), in option order.
    """
    most_open = max(o.estimated_available_fraction for o in options)
    open_ties = sum(o.estimated_available_fraction == most_open for o in options)
    best_open = max(options, key=lambda o: (o.estimated_available_fraction,
                                            o.location["location_id"]))
    pools = {}
    for option in options:
        if option.estimated_walking_minutes is not None:
            pools.setdefault(option.walking_source == WALK_ROUTED, []).append(option)
    reasons = []
    for choice in options:
        text = _fit_reason(choice, pools, best_open, most_open, open_ties,
                           len(options), preference, walking_known)
        reasons.append(text if len(text) <= MAX_TEXT_LENGTH
                       else text[:MAX_TEXT_LENGTH - 1] + "\u2026")
    return reasons


def _fit_reason(choice, pools, best_open, most_open, open_ties, count,
                preference, walking_known):
    """Fit sentence for one option; see _fit_reasons for the rules."""
    percent = _percent(choice)
    walk = choice.estimated_walking_minutes
    if not walking_known:
        return (f"Ranked on past availability only (about {percent}% of spaces "
                "open); no destination was given.")
    if walk is None:
        return (f"No walking time for this location, so its walk scored 0; "
                f"about {percent}% open in past surveys.")
    pool = pools[choice.walking_source == WALK_ROUTED]
    shortest = min(o.estimated_walking_minutes for o in pool)
    closest = min(pool, key=lambda o: (o.estimated_walking_minutes,
                                       o.location["location_id"]))
    kind = "" if choice.walking_source == WALK_ROUTED else " (straight-line)"
    is_most_open = choice.estimated_available_fraction == most_open
    if preference == SHORTER_WALK:
        extra = walk - shortest
        if extra <= 0:
            ties = sum(o.estimated_walking_minutes == shortest for o in pool)
            lead = "Tied for the shortest walk" if ties > 1 else "Shortest walk"
            return f"{lead} of your {count} options ({walk:g} min{kind})."
        if choice.estimated_available_fraction > closest.estimated_available_fraction:
            return (f"{extra:g} min longer walk{kind} than {_name(closest)}, but "
                    f"more space in past surveys ({percent}% vs "
                    f"{_percent(closest)}% open).")
        return (f"{extra:g} min longer walk{kind} than {_name(closest)}; ranked "
                "lower for a shorter walk.")
    if preference == MORE_AVAILABILITY:
        if is_most_open:
            lead = "Tied for the most space" if open_ties > 1 else "Most space"
            return (f"{lead} in past surveys of your {count} options "
                    f"(about {percent}% open).")
        compared = f"Less space than {_name(best_open)} ({percent}% vs " \
                   f"{_percent(best_open)}% open)"
        other_walk = best_open.estimated_walking_minutes
        same_kind = (best_open.walking_source == WALK_ROUTED) == (
            choice.walking_source == WALK_ROUTED)
        if other_walk is not None and same_kind and walk < other_walk:
            return f"{compared}, but a shorter walk ({walk:g} min{kind})."
        return f"{compared}; ranked lower for more space."
    return (f"Balances a {walk:g}-min walk{kind} (shortest {shortest:g}) with "
            f"about {percent}% open in past surveys (most "
            f"{round(most_open * 100)}%).")


def _percent(choice):
    """Whole-number percent of spaces open in past surveys."""
    return round(choice.estimated_available_fraction * 100)


def _name(choice):
    """Location display name for fit reasons."""
    return choice.location["name"]


def _sort_key(choice):
    """Higher score, then availability, then shorter walk, then location ID."""
    walk = choice.estimated_walking_minutes
    return (-choice.score, -choice.estimated_available_fraction,
            math.inf if walk is None else walk, choice.location["location_id"])


def _api_location(location):
    coordinates = (location["coordinates"]
                   if location["coordinate_status"] == "verified" else None)
    return {"location_id": location["location_id"], "name": location["name"],
            "coordinates": coordinates}


def _stall_text(group):
    """Name the stall type; the level stays in ``parking_group`` for display."""
    subtype = f" {group['subtype']}" if group["subtype"] else ""
    return f"{group['category']}{subtype} stalls"


def _optional(row, column):
    """Return a candidate's optional text column, or None when absent/blank."""
    value = getattr(row, column, None)
    return None if value is None or pd.isna(value) else str(value)


def _explain(choice, permit, first):
    """Build a short explanation of at most MAX_TEXT_LENGTH characters.

    A limited estimate is named in parentheses. If that does not fit, a
    shorter marker is used, then the backup comparison is dropped, then the
    walking wording is shortened; the full notes always stay in the
    limitations. As a last resort the text is cut, so the API's length limit
    can never fail a response.
    """
    notes = ([(f" ({choice.estimate_note})", True),
              (" (limited estimate)", True), (" (limited estimate)", False)]
             if choice.estimate_note else [("", True), ("", False)])
    for short_walk in (False, True):
        for note, compare in notes:
            text = _explanation_text(choice, permit,
                                     first if compare else None, note,
                                     short_walk)
            if len(text) <= MAX_TEXT_LENGTH:
                return text
    return text[:MAX_TEXT_LENGTH - 1] + "\u2026"


def _explanation_text(choice, permit, first, note, short_walk=False):
    """Join the explanation parts.

    ``first`` adds the backup comparison; ``short_walk`` uses the compact
    walking wording (WALK_KINDS_SHORT, "approx. pin").
    """
    parts = [f"{permit} permit valid in {_stall_text(choice.parking_group)}"]
    if choice.allowed_until is not None:
        parts[0] += f" until {_clock(choice.allowed_until)}"
    parts[0] += "."
    percent = round(choice.estimated_available_fraction * 100)
    basis = ("Model estimate based on historical surveys"
             if choice.estimate_basis == "model" else "Past surveys")
    parts.append(f"{basis}: about {percent}% open{note}.")
    if choice.estimated_available_fraction <= NEAR_FULL_FRACTION:
        parts.append("Often nearly full.")
    if choice.estimated_walking_minutes is not None:
        kinds = WALK_KINDS_SHORT if short_walk else WALK_KINDS
        approx = ((" (approx. pin)" if short_walk else " (approximate pin)")
                  if choice.walking_is_approximate else "")
        kind = kinds.get(choice.walking_source, "walk")
        parts.append(
            f"About {choice.estimated_walking_minutes} min {kind}{approx}.")
    if first is not None:
        parts.append(_compare(choice, first))
    return " ".join(parts)


def _day(day):
    """Format a date like "Sep 21, 2026" (portable; no platform strftime flags)."""
    return f"{day:%b} {day.day}, {day.year}"


def _clock(moment):
    """Format a time like "Wed 8:00 AM"."""
    return f"{moment:%a} {clock(moment)}"


def _compare(backup, first):
    """Say why the backup ranks below the first choice."""
    reasons = []
    if backup.estimated_available_fraction < first.estimated_available_fraction:
        reasons.append("lower availability")
    if (backup.estimated_walking_minutes is not None
            and first.estimated_walking_minutes is not None
            and backup.estimated_walking_minutes > first.estimated_walking_minutes):
        reasons.append("a longer walk")
    if not reasons:
        return "Backup: next-best combined score."
    return f"Backup: {' and '.join(reasons)}."


def _limitations(counts, walking_known, arrival, departure):
    notes = list(BASE_LIMITATIONS)
    days = [to_ucsd_time(arrival).date()]
    if departure is not None:
        days.append(to_ucsd_time(departure).date())
    if not all(is_verified(day) for day in days):
        notes.append(f"Holiday and quarter dates are verified only from "
                     f"{_day(VERIFIED_START)} to {_day(VERIFIED_END)}; "
                     "this date was not checked.")
    if not walking_known:
        notes.append("No destination coordinates, so walking time was not "
                     "estimated and only availability was compared.")
    if departure is None:
        notes.append("Permit rules were checked at arrival only; they can "
                     "change during your stay.")
    if counts["needs_verification"]:
        notes.append(f"{counts['needs_verification']} parking groups with "
                     "unclear or specialized rules were not recommended.")
    if counts["missing_estimate"]:
        notes.append(f"{counts['missing_estimate']} eligible parking groups had "
                     "no availability estimate and were not ranked.")
    return notes
