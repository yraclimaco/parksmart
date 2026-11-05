"""One object that loads everything a recommendation needs, once.

The API endpoint, the mobile app's backend calls, notebooks and the CLI below
all use ``Recommender`` instead of repeating the setup: load the analysis
dataset and location registry, fit (or accept) an availability estimator, and
keep the current parking groups. Each request then only attaches estimates
and ranks.

Try it without the API (after ``python -m src.build_dataset``):

    python -m src.recommender --permit S --arrival 2026-11-03T09:00 \\
        --lat 32.8811 --lon -117.2376
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from .availability import AvailabilityEstimator
from .location_registry import (DEFAULT_DATASET, DEFAULT_REGISTRY,
                                current_groups, load_registry)
from .parking_benchmarks import load_analysis_dataset
from .ranking import BALANCED, recommend


class Recommender:
    """Loaded data plus estimator; ``recommend()`` answers one request.

    Args:
        records: prepared analysis records (``load_analysis_dataset``).
        locations: validated registry list (``load_registry``).
        estimator: optional ready AvailabilityEstimator (for example one
            wrapping a saved Issue #18 model). Defaults to the historical
            average fitted on ``records``.
    """

    def __init__(self, records, locations, estimator=None):
        self.locations = locations
        self.estimator = (estimator if estimator is not None
                          else AvailabilityEstimator().fit(records))
        self.candidates = current_groups(locations, records)

    @classmethod
    def from_files(cls, dataset=DEFAULT_DATASET, registry=DEFAULT_REGISTRY,
                   estimator=None):
        """Build from the pipeline CSV and registry JSON.

        Args:
            dataset: analysis dataset path (default: pipeline output).
            registry: location registry path (default: config/locations.json).
            estimator: optional ready AvailabilityEstimator.
        Returns:
            Recommender.
        Raises:
            FileNotFoundError: the dataset or registry is missing, with the
                command that creates it.
        """
        dataset, registry = Path(dataset), Path(registry)
        if not dataset.exists():
            raise FileNotFoundError(
                f"Analysis dataset not found at {dataset}. Build it with "
                "`python -m src.download_qpass`, `python -m "
                "src.download_inventory`, then `python -m src.build_dataset`.")
        if not registry.exists():
            raise FileNotFoundError(f"Location registry not found at {registry}.")
        return cls(load_analysis_dataset(dataset), load_registry(registry),
                   estimator)

    def recommend(self, permit, arrival, destination=None, departure=None,
                  walk_router=None, preference=BALANCED, max_walk_minutes=None):
        """Rank parking for one request.

        Args:
            permit: permit code (see ``src.eligibility.PERMIT_TYPES``).
            arrival: datetime; naive values are UCSD local time.
            destination: optional {"latitude", "longitude"} dict.
            departure: optional datetime; checks the whole stay.
            walk_router: optional routed-walking callable for the top
                choices (``src.routing.walk_router``); None keeps
                straight-line walking estimates.
            preference: ``shorter_walk``, ``balanced`` or
                ``more_availability`` (``src.ranking.PREFERENCES``).
            max_walk_minutes: optional personal walking limit.
        Returns:
            ``src.ranking.RecommendationResult``; ``to_api()`` gives the
            response fields.
        Raises:
            ValueError: unknown permit or preference, an invalid walking
                limit, or invalid times.
        """
        groups = self.estimator.attach(self.candidates, arrival)
        return recommend(groups, self.locations, permit, arrival,
                         destination=destination, departure=departure,
                         walk_router=walk_router, preference=preference,
                         max_walk_minutes=max_walk_minutes)


def main(argv=None):
    """Print one recommendation as JSON, for trying the pipeline from a shell."""
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--permit", required=True)
    parser.add_argument("--arrival", required=True,
                        help="ISO datetime, UCSD local time if no offset")
    parser.add_argument("--departure", help="optional ISO datetime")
    parser.add_argument("--lat", type=float, help="destination latitude")
    parser.add_argument("--lon", type=float, help="destination longitude")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--registry", default=DEFAULT_REGISTRY)
    args = parser.parse_args(argv)
    if (args.lat is None) != (args.lon is None):
        parser.error("give both --lat and --lon, or neither")

    destination = (None if args.lat is None
                   else {"latitude": args.lat, "longitude": args.lon})
    departure = (datetime.fromisoformat(args.departure) if args.departure
                 else None)
    result = Recommender.from_files(args.dataset, args.registry).recommend(
        args.permit, datetime.fromisoformat(args.arrival), destination,
        departure)
    print(json.dumps(result.to_api(), indent=2))


if __name__ == "__main__":
    main()
