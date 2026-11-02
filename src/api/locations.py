"""Build the public catalog from Dylan's validated shared registry."""

from src.location_registry import api_locations, load_registry

from .schemas import LocationsResponse


def get_locations(registry=None) -> LocationsResponse:
    """Return supported real locations with verified coordinates or JSON null.

    Args:
        registry: validated registry entries, or None to load the shared file.
    Returns:
        Supported IDs. Registry support is not proof of current use or eligibility.
    """
    registry = load_registry() if registry is None else registry
    supported = [entry for entry in registry
                 if entry["registry_status"] == "supported"]
    return LocationsResponse(
        data_status="verified",
        locations=api_locations(supported),
        limitations=[
            "Only supported registry locations are listed; restricted, unresolved "
            "and excluded entries are omitted.",
            "Only verified coordinates are returned; approximate or missing "
            "coordinates are null.",
            "Registry support does not verify current use, permit eligibility "
            "or availability. Recommendations evaluate eligible parking groups.",
        ],
    )
