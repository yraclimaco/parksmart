"""Serve a trusted saved Issue #18 estimator through the existing API."""

from src.availability import AvailabilityEstimator
from src.availability_prediction import (
    BASIS_DESCRIPTIONS, DEFAULT_ARTIFACT, load_prediction_service,
)
from src.location_registry import DEFAULT_DATASET, DEFAULT_REGISTRY

from .main import create_app
from .settings import ServingSettings


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
                      estimator=estimator, prediction_mode="saved")


def load_approved_estimator(path, approved_model):
    """Load Vivaan's trusted v2 artifact and enforce the configured model choice.

    Args:
        path: trusted local artifact, never a user-uploaded pickle.
        approved_model: reviewed model name; default configuration is historical_average.
    Returns:
        Ready AvailabilityEstimator; no fit/train calls or fallback substitution.
    """
    import pickle

    try:
        model = load_prediction_service(path)
    except (pickle.UnpicklingError, EOFError, TypeError, KeyError,
            AttributeError, ImportError) as error:
        raise ValueError("Invalid saved prediction artifact; use the trusted "
                         "compatible artifact and its training environment") from error
    if model.name != approved_model:
        raise ValueError(f"Artifact estimator {model.name!r} does not match the "
                         f"configured approved model {approved_model!r}")
    return AvailabilityEstimator(
        model, survey_times=model.survey_times,
        basis_descriptions=BASIS_DESCRIPTIONS,
    )


def create_configured_app():
    """Build the local/Lambda serving app from nonsecret environment settings.

    Saved mode is the default. The approved artifact is loaded once during
    lifespan startup; invalid/missing artifacts leave health/catalog available
    and readiness/recommendations return 503. Baseline mode is explicit only.
    An optional private S3 bundle is materialized before startup, never per HTTP
    request. Bundle failures stop this factory rather than mixing resources.
    """
    settings = ServingSettings.from_env()
    paths = {"artifact": settings.artifact_path, "dataset": settings.dataset_path,
             "registry": settings.registry_path}
    if settings.bundle_manifest:
        from .bundle import materialize_bundle
        paths = materialize_bundle(settings.bundle_manifest, settings.cache_dir)
    loader = None
    if settings.model_mode == "saved":
        def loader():
            """Load only the explicitly approved estimator for this process."""
            return load_approved_estimator(paths["artifact"], settings.approved_model)
    return create_app(
        dataset_path=paths["dataset"], registry_path=paths["registry"],
        estimator_loader=loader, prediction_mode=settings.model_mode,
    )
