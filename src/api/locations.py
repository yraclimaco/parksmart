"""Explicitly fictional UI fixtures; no processed dataset is read at startup."""

from .schemas import LocationsResponse, ParkingLocation


def get_locations() -> LocationsResponse:
    """Return a fresh sample catalog with stable fixture IDs and no coordinates.

    Takes no parameters. These IDs are for interface development only and must
    be replaced with a team-reviewed, persisted catalog before real use.
    The proposed fields and fixture IDs give Hanrong a starting point for his app.
    """
    return LocationsResponse(
        data_status="sample",
        locations=[
            ParkingLocation(location_id="sample-parking-a", name="Sample Parking A"),
            ParkingLocation(location_id="sample-parking-b", name="Sample Parking B"),
        ],
        limitations=[
            "Fictional sample locations for interface development only.",
            "Proposed location IDs and fields support Hanrong's app development.",
            "Coordinates and permit eligibility have not been verified.",
            "Catalog is not connected to the processed pipeline dataset.",
        ],
    )
