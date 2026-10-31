"""Rank eligible parking and pick a first choice and a distinct backup.

Callers (the FastAPI endpoint) supply one row per current parking group with
its predicted availability. This module filters by registry status and permit
eligibility, estimates walking time, scores each eligible group, keeps the
best group per location, and returns the top two locations with explanations.
Scoring weights, walking assumptions and tie-breaking are documented in
docs/recommendations.md.
"""

import math
from dataclasses import dataclass, field
from typing import List, Optional

import pandas as pd

from .eligibility import ALLOWED, NEEDS_VERIFICATION, check_eligibility

# Same weights as the website prototype (frontend/src/constants.ts).
AVAILABILITY_WEIGHT = 0.65
WALKING_WEIGHT = 0.35
# Walking score falls linearly from 1 at 0 min to 0 at this many minutes;
# locations farther than this are not recommended.
MAX_WALK_MINUTES = 20
# Straight-line walking estimate, matching the website: about 13 min per km
# plus a 2-minute buffer, never below 3 minutes. Not a routed path.
WALK_MINUTES_PER_KM = 13
WALK_BUFFER_MINUTES = 2
MIN_WALK_MINUTES = 3
EARTH_RADIUS_KM = 6371.0
# Matches the near-full threshold in src/parking_benchmarks.py (10% open).
NEAR_FULL_FRACTION = 0.10

READY = "ready"
NO_SUITABLE_LOCATION = "no_suitable_location"
PREDICTIONS_UNAVAILABLE = "predictions_unavailable"

REQUIRED_COLUMNS = ["location_id", "facility", "category", "subtype", "level",
                    "estimated_available_fraction"]
BASE_LIMITATIONS = [
    "Availability is an estimate from historical surveys, not live occupancy "
    "or a guaranteed space.",
    "Walking times are straight-line estimates, not routed walking paths.",
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

    def to_api(self):
        """Return fields matching src.api.schemas.ParkingChoice."""
        return {
            "location": self.location,
            "estimated_available_fraction": self.estimated_available_fraction,
            "estimated_walking_minutes": self.estimated_walking_minutes,
            "explanation": self.explanation,
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

    def to_api(self):
        """Return status, choices, explanation and limitations for the API."""
        return {
            "status": self.status,
            "first_choice": self.first_choice and self.first_choice.to_api(),
            "backup_choice": self.backup_choice and self.backup_choice.to_api(),
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


def score(fraction, walk_minutes, walking_known):
    """Score one option from 0 to 1.

    Args:
        fraction: estimated available fraction, 0-1.
        walk_minutes: estimated minutes, or None.
        walking_known: whether any candidate has a walking estimate. If none
            do, availability alone decides; if some do, unknown walks score 0.
    Returns:
        Weighted score.
    """
    if not walking_known:
        return fraction
    walk_score = 0.0 if walk_minutes is None else max(
        0.0, min(1.0, (MAX_WALK_MINUTES - walk_minutes) / MAX_WALK_MINUTES))
    return AVAILABILITY_WEIGHT * fraction + WALKING_WEIGHT * walk_score


def recommend(candidates, locations, permit, arrival, destination=None,
              departure=None):
    """Pick a first choice and a distinct backup for one request.

    Args:
        candidates: DataFrame, one row per current parking group, with
            REQUIRED_COLUMNS (fraction NaN/None when no estimate) and an
            optional ``estimate_basis`` column (e.g. "historical_average").
        locations: validated registry list (src.location_registry).
        permit: permit code (see src.eligibility.PERMIT_TYPES).
        arrival: datetime; naive values are UCSD local time.
        destination: optional coordinate dict for walking estimates.
        departure: optional datetime to check the whole stay.
    Returns:
        RecommendationResult.
    Raises:
        ValueError: missing columns, unknown permit, or invalid times.
    """
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
              "missing_estimate": 0, "scored": 0}
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
        if walk is not None and walk > MAX_WALK_MINUTES:
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
            score=score(fraction, walk, walking_known),
            eligibility_reason=result.reason,
            allowed_until=result.allowed_until,
        ))

    best = {}
    for choice in sorted(scored, key=_sort_key):
        best.setdefault(choice.location["location_id"], choice)
    ranked = sorted(best.values(), key=_sort_key)
    limitations = _limitations(counts, walking_known, departure)

    if not ranked:
        if counts["missing_estimate"]:
            return RecommendationResult(
                PREDICTIONS_UNAVAILABLE, None, None,
                "Your permit can use some nearby parking, but no availability "
                "estimate exists for it at this time.", limitations, counts)
        return RecommendationResult(
            NO_SUITABLE_LOCATION, None, None,
            "No supported parking matched your permit, arrival time and "
            "walking limit. This does not mean parking is full.",
            limitations, counts)

    first = ranked[0]
    backup = ranked[1] if len(ranked) > 1 else None
    first.explanation = _explain(first, permit, None)
    if backup:
        backup.explanation = _explain(backup, permit, first)
    summary = (f"{first.location['name']} scored highest on expected "
               "availability and walking distance.")
    if backup is None:
        summary += " No second suitable location was found."
    return RecommendationResult(READY, first, backup, summary, limitations,
                                counts)


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


def _explain(choice, permit, first):
    """Build a short explanation (the API allows 200 characters).

    The estimate basis is kept on the Choice, not repeated here.
    """
    parts = [f"{permit} permit valid in {_stall_text(choice.parking_group)}"]
    if choice.allowed_until is not None:
        parts[0] += f" until {_clock(choice.allowed_until)}"
    parts[0] += "."
    percent = round(choice.estimated_available_fraction * 100)
    parts.append(f"Past surveys: about {percent}% open.")
    if choice.estimated_available_fraction <= NEAR_FULL_FRACTION:
        parts.append("Often nearly full.")
    if choice.estimated_walking_minutes is not None:
        approx = " (approximate pin)" if choice.walking_is_approximate else ""
        parts.append(f"About {choice.estimated_walking_minutes} min walk{approx}.")
    if first is not None:
        parts.append(_compare(choice, first))
    return " ".join(parts)


def _clock(moment):
    """Format a time like "8:00 AM" (portable; no platform strftime flags)."""
    hour = moment.hour % 12 or 12
    suffix = "AM" if moment.hour < 12 else "PM"
    return f"{moment.strftime('%a')} {hour}:{moment.minute:02d} {suffix}"


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


def _limitations(counts, walking_known, departure):
    notes = list(BASE_LIMITATIONS)
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
