"""Versioned trip-alert JSON contract shared by website and iOS clients."""

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import Field, field_validator, model_validator

from .schemas import (
    APIModel, LOCAL_ZONE, PlaceInput, RecommendationRequest, Text, UCSD_TIME_ZONE,
)

class TripAlertsRequest(APIModel):
    """Trip arrival and selected parking ID and/or geocoded destination."""

    arrival_time: datetime
    parking_location_id: Optional[Text] = None
    destination: Optional[PlaceInput] = None

    @field_validator("arrival_time", mode="before")
    @classmethod
    def require_datetime(cls, value):
        """Apply the existing recommendation ISO-datetime input contract."""
        return RecommendationRequest.require_iso_datetime(value)

    @field_validator("arrival_time")
    @classmethod
    def normalize_arrival(cls, value):
        """Use existing UCSD timezone and DST validation without permit inputs."""
        return RecommendationRequest.interpret_ucsd_time(value)

    @model_validator(mode="after")
    def require_location(self):
        """Reject requests with neither a parking ID nor destination coordinates."""
        if self.parking_location_id is None and (
                self.destination is None or self.destination.coordinates is None):
            raise ValueError("Provide parking_location_id or destination coordinates")
        return self


class AlertLocation(APIModel):
    """A requested destination or registry parking point used for matching."""

    role: Literal["parking", "destination"]
    name: Text
    latitude: float = Field(ge=-90, le=90, allow_inf_nan=False)
    longitude: float = Field(ge=-180, le=180, allow_inf_nan=False)
    location_id: Optional[Text] = None


class TripAlert(APIModel):
    """A plain-text informational notice with source, matching and freshness."""

    alert_id: str = Field(min_length=1, max_length=300)
    alert_type: Literal["weather", "construction"]
    message: str = Field(min_length=1, max_length=600)
    locations: List[AlertLocation] = Field(min_length=1, max_length=2)
    relevant_from: Optional[datetime] = None
    relevant_until: Optional[datetime] = None
    source_name: str
    source_url: str
    last_checked_at: datetime
    match_basis: str
    limitations: List[str]


class ForecastWeather(APIModel):
    """Hourly forecast values, not observed weather or official hazard warnings."""

    location: AlertLocation
    forecast_time: datetime
    period_start: datetime
    period_end: datetime
    temperature_c: Optional[float] = Field(default=None, allow_inf_nan=False)
    apparent_temperature_c: Optional[float] = Field(default=None, allow_inf_nan=False)
    precipitation_probability_percent: Optional[float] = Field(
        default=None, ge=0, le=100, allow_inf_nan=False)
    precipitation_mm: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    wind_speed_kmh: Optional[float] = Field(default=None, ge=0, allow_inf_nan=False)
    weather_code: Optional[int] = Field(default=None, ge=0, le=99)


class AlertSourceResult(APIModel):
    """Independent source state; fresh-empty never substitutes for failure/stale."""

    status: Literal["available", "no_relevant", "partial", "stale", "unavailable",
                    "out_of_range", "missing_location"]
    source_name: str
    source_url: str
    last_checked_at: Optional[datetime] = None
    last_attempt_at: Optional[datetime] = None
    alerts: List[TripAlert] = Field(default_factory=list)
    forecast: Optional[ForecastWeather] = None
    limitations: List[str] = Field(default_factory=list)


class TripAlertsResponse(APIModel):
    """Independent source results; receiving alerts never changes recommendations."""

    schema_version: Literal["0.1"] = "0.1"
    is_example: bool = False
    arrival_time: datetime
    time_zone: Literal["America/Los_Angeles"] = UCSD_TIME_ZONE
    weather: AlertSourceResult
    construction: AlertSourceResult
    limitations: List[str]

    @field_validator("arrival_time")
    @classmethod
    def require_aware_arrival(cls, value):
        """Return an aware UCSD arrival; reject ambiguous response timestamps."""
        if value.tzinfo is None:
            raise ValueError("Response arrival_time must include an offset")
        return value.astimezone(LOCAL_ZONE)
