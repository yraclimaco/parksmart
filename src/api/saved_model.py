"""Serve a trusted saved Issue #18 estimator through the existing API."""

from src.availability import AvailabilityEstimator
from src.availability_prediction import (
    BASIS_DESCRIPTIONS, DEFAULT_ARTIFACT, load_prediction_service,
)
from src.location_registry import DEFAULT_DATASET, DEFAULT_REGISTRY

from .main import create_app


def create_saved_app(artifact_path=DEFAULT_ARTIFACT, dataset_path=DEFAULT_DATASET,
                     registry_path=DEFAULT_REGISTRY):
    """Return FastAPI configured with a compatible, already fitted estimator.

    Args:
        artifact_path: Trusted local saved service; checked before API startup.
        dataset_path: Existing integrated CSV used for current parking groups.
        registry_path: Shared real-location registry.
    Returns:
        FastAPI app using create_app(estimator=...). No model is fitted here.
        Missing or incompatible artifacts stop startup with a clear error;
        there is no silent switch to a different prediction model.
    """
    model = load_prediction_service(artifact_path)
    estimator = AvailabilityEstimator(
        model, survey_times=model.survey_times,
        basis_descriptions=BASIS_DESCRIPTIONS,
    )
    return create_app(dataset_path=dataset_path, registry_path=registry_path,
                      estimator=estimator)
