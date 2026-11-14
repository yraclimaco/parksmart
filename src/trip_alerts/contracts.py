"""Provider-neutral trip alert objects shared by the HTTP and client interfaces."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass(frozen=True)
class AlertTarget:
    """A verified/requested trip point, without geocoding a free-text name.

    Args:
        role: parking or destination.
        name: Display label only; never used for fuzzy location matching.
        latitude: WGS84 northing in degrees.
        longitude: WGS84 easting in degrees.
        location_id: Stable registry ID for parking, otherwise None.
    """

    role: str
    name: str
    latitude: float
    longitude: float
    location_id: Optional[str] = None


@dataclass
class ProviderResult:
    """Source outcome with success/attempt timestamps and explicitly typed data.

    Args:
        status: available, no_relevant, partial, out_of_range, missing_location,
            unavailable or stale. Stale never means fresh no-relevant notices.
        source_name: Human-readable provider attribution.
        source_url: Public information/API link, never a credential-bearing URL.
        last_checked_at: Successful retrieval time of the actual data, UTC.
        last_attempt_at: Last refresh attempt, including a failed attempt, UTC.
        alerts: Normalized alert dictionaries using the shared HTTP schema.
        forecast: Optional normalized hourly forecast dictionary, weather only.
        limitations: Concise coverage, matching and freshness qualifications.
    """

    status: str
    source_name: str
    source_url: str
    last_checked_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    alerts: list = field(default_factory=list)
    forecast: Optional[dict] = None
    limitations: list = field(default_factory=list)
