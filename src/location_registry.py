"""Shared location registry: stable location IDs mapped to dataset facilities.

The registry (config/locations.json) is the one place that says which parking
location a dataset facility belongs to. Predictions stay keyed by facility,
category, subtype and level; this module only attaches a location_id, so
restricted parking groups are never merged. Recent observations show that a
facility appeared in a survey, not that it is open or that its allocation is
unchanged; ``current_use_verified`` is therefore always False here.

Run ``python -m src.location_registry`` to check the registry against the
integrated dataset and print a coverage report.
"""

import argparse
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

DEFAULT_REGISTRY = Path("config/locations.json")
DEFAULT_DATASET = Path("data/processed/pipeline/analysis_dataset.csv")
SCHEMA_VERSION = "0.1"
LOCATION_ID_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
KINDS = {"structure", "lot", "unknown"}
# supported: may be recommended once eligibility rules allow it.
# restricted: needs a supplemental permit or authorization; never recommended.
# unresolved: name, location or scope not verified; never recommended.
# excluded: deliberately out of scope (e.g. resident-only housing).
REGISTRY_STATUSES = {"supported", "restricted", "unresolved", "excluded"}
COORDINATE_STATUSES = {"verified", "approximate", "missing"}
REQUIRED_FIELDS = (
    "location_id", "name", "kind", "dataset_facilities", "coordinates",
    "coordinate_status", "coordinate_source", "coordinate_verified_on",
    "registry_status", "access_note", "notes",
)
GROUP_COLUMNS = ["facility", "category", "subtype", "level"]


def load_registry(path=DEFAULT_REGISTRY):
    """Read and validate the location registry.

    Args:
        path: JSON registry file; defaults to config/locations.json.
    Returns:
        List of location dicts in file order.
    Raises:
        ValueError: if any entry breaks the rules in ``validate_registry``.
    """
    document = json.loads(Path(path).read_text())
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ValueError(f"Expected registry schema_version {SCHEMA_VERSION}")
    locations = document.get("locations")
    if not isinstance(locations, list):
        raise ValueError("Registry needs a 'locations' list")
    validate_registry(locations)
    return locations


def validate_registry(locations):
    """Check IDs, field values and facility mappings; raise on the first errors.

    Args:
        locations: list of location dicts.
    Returns:
        None. Raises ValueError listing every problem found.
    """
    problems = []
    seen_ids, seen_facilities = set(), {}
    for index, location in enumerate(locations):
        label = location.get("location_id", f"entry {index}")
        missing = [field for field in REQUIRED_FIELDS if field not in location]
        extra = sorted(set(location) - set(REQUIRED_FIELDS))
        if missing or extra:
            problems.append(f"{label}: missing {missing}, unexpected {extra}")
            continue
        location_id = location["location_id"]
        if not isinstance(location_id, str) or not LOCATION_ID_PATTERN.match(
                location_id):
            problems.append(f"{label}: location_id must be lowercase kebab-case")
        if location_id in seen_ids:
            problems.append(f"{label}: duplicate location_id")
        seen_ids.add(location_id)
        if not isinstance(location["name"], str) or not location["name"].strip():
            problems.append(f"{label}: name is required")
        if location["kind"] not in KINDS:
            problems.append(f"{label}: kind must be one of {sorted(KINDS)}")
        if location["registry_status"] not in REGISTRY_STATUSES:
            problems.append(
                f"{label}: registry_status must be one of "
                f"{sorted(REGISTRY_STATUSES)}"
            )
        problems.extend(_coordinate_problems(label, location))
        facilities = location["dataset_facilities"]
        if not isinstance(facilities, list):
            problems.append(f"{label}: dataset_facilities must be a list")
            continue
        for facility in facilities:
            if facility in seen_facilities:
                problems.append(
                    f"{label}: facility {facility!r} already mapped to "
                    f"{seen_facilities[facility]}"
                )
            seen_facilities[facility] = location_id
    if problems:
        raise ValueError("Invalid location registry:\n- " + "\n- ".join(problems))


def _coordinate_problems(label, location):
    """Return coordinate consistency problems for one location."""
    status = location["coordinate_status"]
    coordinates = location["coordinates"]
    if status not in COORDINATE_STATUSES:
        return [f"{label}: coordinate_status must be one of "
                f"{sorted(COORDINATE_STATUSES)}"]
    if status == "missing":
        if coordinates is not None or location["coordinate_source"] is not None:
            return [f"{label}: missing coordinates must have no value or source"]
        return []
    problems = []
    if not isinstance(coordinates, dict) or set(coordinates) != {
            "latitude", "longitude"}:
        return [f"{label}: coordinates need latitude and longitude"]
    latitude, longitude = coordinates["latitude"], coordinates["longitude"]
    if not (isinstance(latitude, (int, float)) and -90 <= latitude <= 90):
        problems.append(f"{label}: latitude out of range")
    if not (isinstance(longitude, (int, float)) and -180 <= longitude <= 180):
        problems.append(f"{label}: longitude out of range")
    if not location["coordinate_source"]:
        problems.append(f"{label}: coordinates need a coordinate_source")
    try:
        date.fromisoformat(location["coordinate_verified_on"])
    except (TypeError, ValueError):
        problems.append(f"{label}: coordinate_verified_on must be an ISO date")
    return problems


def facility_to_location(locations):
    """Map each standardized dataset facility to its location_id.

    Args:
        locations: validated registry list.
    Returns:
        Dict of facility -> location_id.
    """
    return {
        facility: location["location_id"]
        for location in locations
        for facility in location["dataset_facilities"]
    }


def location_groups(locations, records):
    """List each location's distinct parking groups observed in the dataset.

    Args:
        locations: validated registry list.
        records: analysis dataset with facility, category, subtype, level,
            observation_date, academic_year and quarter columns.
    Returns:
        DataFrame with location_id, the four group columns (blank subtype or
        level means unspecified), readings, first/last observation date, and
        whether the group appears in the latest surveyed quarter. Facilities
        missing from the registry get a null location_id instead of being
        dropped.
    """
    data = records.copy()
    for column in ("subtype", "level"):
        data[column] = data[column].fillna("").astype(str)
    data["observation_date"] = pd.to_datetime(data["observation_date"])
    latest = _latest_period(data)
    data["in_latest_quarter"] = (
        data["academic_year"].eq(latest[0]) & data["quarter"].eq(latest[1])
    )
    groups = (
        data.groupby(GROUP_COLUMNS, dropna=False)
        .agg(
            readings=("observation_date", "size"),
            first_observed=("observation_date", "min"),
            last_observed=("observation_date", "max"),
            in_latest_quarter=("in_latest_quarter", "any"),
        )
        .reset_index()
    )
    groups.insert(0, "location_id",
                  groups["facility"].map(facility_to_location(locations)))
    for column in ("first_observed", "last_observed"):
        groups[column] = groups[column].dt.date.astype(str)
    return groups


def location_summary(locations, records):
    """Summarize registry entries with dataset coverage and current-use evidence.

    Args:
        locations: validated registry list.
        records: analysis dataset (see ``location_groups``).
    Returns:
        DataFrame with one row per location: status fields, parking-group and
        reading counts, last observation, ``current_use_status``
        (observed_in_latest_quarter, not_in_latest_quarter or no_observations)
        and ``current_use_verified`` (always False; see module docstring).
    """
    groups = location_groups(locations, records)
    rows = []
    for location in locations:
        mine = groups[groups["location_id"] == location["location_id"]]
        if mine.empty:
            use, last, count, readings = "no_observations", None, 0, 0
        else:
            use = ("observed_in_latest_quarter" if mine["in_latest_quarter"].any()
                   else "not_in_latest_quarter")
            last, count, readings = (mine["last_observed"].max(), len(mine),
                                     int(mine["readings"].sum()))
        rows.append({
            "location_id": location["location_id"],
            "name": location["name"],
            "registry_status": location["registry_status"],
            "coordinate_status": location["coordinate_status"],
            "parking_groups": count,
            "readings": readings,
            "last_observed": last,
            "current_use_status": use,
            "current_use_verified": False,
        })
    return pd.DataFrame(rows)


def unmapped_facilities(locations, records):
    """Return sorted dataset facilities that no registry entry claims."""
    known = facility_to_location(locations)
    return sorted(set(records["facility"].dropna()) - set(known))


def api_locations(locations):
    """Convert registry entries to the API's ParkingLocation fields.

    Args:
        locations: validated registry list.
    Returns:
        List of dicts with location_id, name and coordinates. Only verified
        coordinates are passed on; approximate or missing ones become None,
        as the API contract requires.
    """
    return [
        {
            "location_id": location["location_id"],
            "name": location["name"],
            "coordinates": (location["coordinates"]
                            if location["coordinate_status"] == "verified"
                            else None),
        }
        for location in locations
    ]


def _latest_period(data):
    """Return (academic_year, quarter) of the latest observation date."""
    latest_row = data.loc[data["observation_date"].idxmax()]
    return latest_row["academic_year"], latest_row["quarter"]


def main(argv=None):
    """Validate the registry against the dataset and print a coverage report."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    args = parser.parse_args(argv)
    locations = load_registry(args.registry)
    records = pd.read_csv(args.dataset, low_memory=False)
    missing = unmapped_facilities(locations, records)
    summary = location_summary(locations, records)
    print(f"{len(locations)} locations; "
          f"{records['facility'].nunique()} dataset facilities.")
    print(summary.groupby(["registry_status", "coordinate_status",
                           "current_use_status"]).size().to_string())
    if missing:
        raise SystemExit(f"Facilities missing from the registry: {missing}")
    print("Every dataset facility is mapped to exactly one location.")


if __name__ == "__main__":
    main()
