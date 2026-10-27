"""Pydantic v2 models shared by HTTP endpoints and future services.

All models reject unknown fields so interface spelling mistakes fail visibly.
Unknown measurements are represented by None (JSON null), never zero.
"""

from datetime import datetime, timezone
from typing import Annotated, List, Literal, Optional
from zoneinfo import ZoneInfo

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

UCSD_TIME_ZONE = "America/Los_Angeles"
LOCAL_ZONE = ZoneInfo(UCSD_TIME_ZONE)
Text = Annotated[str, Field(min_length=1, max_length=200)]


class APIModel(BaseModel):
    """Base JSON object; keyword fields are validated and serialized by Pydantic."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Coordinates(APIModel):
    """A complete WGS84 latitude/longitude pair supplied as keyword fields."""

    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)


class PlaceInput(APIModel):
    """User-supplied destination or origin, without inferred geocoding results."""

    name: Text
    coordinates: Optional[Coordinates] = None


class ParkingLocation(APIModel):
    """Catalog ID and display name; coordinates are populated only when verified."""

    location_id: Text
    name: Text
    coordinates: Optional[Coordinates] = None


class HealthResponse(APIModel):
    """Process liveness response, independent of data and model readiness."""

    status: Literal["ok"] = "ok"


class LocationsResponse(APIModel):
    """Location catalog envelope with explicit source status and limitations."""

    schema_version: Literal["0.1"] = "0.1"
    data_status: Literal["sample", "verified"]
    locations: List[ParkingLocation]
    limitations: List[Text]

    @model_validator(mode="after")
    def unique_ids(self):
        """Check this catalog's IDs and return the validated catalog."""
        ids = [location.location_id for location in self.locations]
        if len(ids) != len(set(ids)):
            raise ValueError("location_id must be unique within the catalog")
        return self


class RecommendationRequest(APIModel):
    """Proposed user inputs; permit_type records input, not verified eligibility."""

    destination: PlaceInput
    arrival_time: datetime = Field(
        description="ISO 8601 datetime. Without an offset, interpreted in "
        "America/Los_Angeles. Explicit offsets identify an instant and are "
        "converted to UCSD local time. DST-ambiguous local times need an offset."
    )
    permit_type: Text = Field(
        description="Team-proposed permit code; no eligibility rules applied yet."
    )
    starting_location: Optional[PlaceInput] = None

    @field_validator("arrival_time", mode="before")
    @classmethod
    def require_iso_datetime(cls, value):
        """Reject timestamps/date-only input; return an ISO string or datetime."""
        if isinstance(value, datetime):
            return value
        if not isinstance(value, str) or "T" not in value:
            raise ValueError("Use an ISO 8601 datetime containing T")
        return value

    @field_validator("arrival_time")
    @classmethod
    def interpret_ucsd_time(cls, value: datetime) -> datetime:
        """Normalize an arrival datetime to UCSD time, rejecting invalid DST input."""
        if value.tzinfo is not None:
            return value.astimezone(LOCAL_ZONE)
        # Round trips detect the missing spring hour; two valid offsets detect
        # the repeated autumn hour. An explicit offset resolves that ambiguity.
        candidates = []
        for fold in (0, 1):
            candidate = value.replace(tzinfo=LOCAL_ZONE, fold=fold)
            restored = candidate.astimezone(timezone.utc).astimezone(LOCAL_ZONE)
            if restored.replace(tzinfo=None) == value:
                candidates.append(candidate)
        if not candidates:
            raise ValueError("Arrival time does not exist in UCSD local time")
        if len({candidate.utcoffset() for candidate in candidates}) > 1:
            raise ValueError("Ambiguous UCSD local time; include an explicit offset")
        return candidates[0]


class ParkingChoice(APIModel):
    """One future recommendation, with optional estimates and an explanation."""

    location: ParkingLocation
    estimated_available_fraction: Optional[float] = Field(
        default=None, ge=0, le=1, allow_inf_nan=False,
        description="Fraction from 0 to 1, not a percentage or guarantee."
    )
    estimated_walking_minutes: Optional[float] = Field(
        default=None, ge=0, allow_inf_nan=False
    )
    explanation: Text


class RecommendationResponse(APIModel):
    """Future result envelope; status controls whether parking choices exist."""

    schema_version: Literal["0.1"] = "0.1"
    status: Literal["ready", "no_suitable_location", "not_implemented"]
    is_example: bool
    arrival_time: datetime
    time_zone: Literal["America/Los_Angeles"] = UCSD_TIME_ZONE
    first_choice: Optional[ParkingChoice] = None
    backup_choice: Optional[ParkingChoice] = None
    explanation: Text
    limitations: List[Text]

    @model_validator(mode="after")
    def check_choices(self):
        """Validate status/choice consistency and return this response object."""
        if self.arrival_time.tzinfo is None:
            raise ValueError("Response arrival_time must include a UTC offset")
        self.arrival_time = self.arrival_time.astimezone(LOCAL_ZONE)
        if self.status == "ready" and self.first_choice is None:
            raise ValueError("ready requires first_choice")
        if self.status != "ready" and (
            self.first_choice is not None or self.backup_choice is not None
        ):
            raise ValueError("Unavailable results cannot contain parking choices")
        if self.backup_choice and (
            self.backup_choice.location.location_id
            == self.first_choice.location.location_id
        ):
            raise ValueError("Backup must differ from first choice")
        return self
