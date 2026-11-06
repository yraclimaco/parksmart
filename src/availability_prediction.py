"""Saved prediction service implementing Issue #20's DataFrame contract."""

import json
import pickle
import platform
from importlib.metadata import version
from pathlib import Path

import numpy as np
import pandas as pd

from .parking_benchmarks import FEATURES, GROUP_COLUMNS, HistoricalAverage

ARTIFACT_VERSION = 2
DEFAULT_ARTIFACT = Path("models/issue18/selected.pkl")
BASIS_DESCRIPTIONS = {
    "level_1": None,
    "level_2": "same time, any weekday or quarter",
    "level_3": "all-day average for these stalls",
    "model": None,  # Estimate kind is descriptive, not itself a limitation.
    "unsupported_group": "no history for these exact stalls",
    "unsupported_time": "survey time outside training coverage",
    "unsupported_calendar": "weekday or quarter outside training coverage",
}
CANDIDATE_FEATURE_MODES = {
    "historical_average": "original",
    "linear_original": "original",
    "ridge_original": "original",
    "ridge_engineered": "engineered",
    "forest_engineered": "engineered",
    "boost_engineered": "engineered",
}


def dependency_versions():
    """Return runtime Python and model/data dependency versions for artifacts."""
    return {"python": platform.python_version(), **{
        package: version(package) for package in (
            "numpy", "pandas", "scikit-learn", "scipy", "joblib")
    }}


def normalize_features(records):
    """Return FEATURES from records with nulls normalized to blank strings.

    Raises ValueError for missing columns. No trimming or alias inference occurs.
    """
    missing = set(FEATURES) - set(records)
    if missing:
        raise ValueError(f"Missing prediction fields: {sorted(missing)}")
    return records[FEATURES].fillna("").astype(str)


def engineer_features(records):
    """Return prediction-time categorical features from a DataFrame.

    Adds joint group identity and weekday/time effects without target statistics.
    JSON encoding preserves distinctions even when labels contain separators.
    """
    result = normalize_features(records)
    result["parking_group"] = [json.dumps(list(row)) for row in
                               result[GROUP_COLUMNS].itertuples(index=False,
                                                               name=None)]
    result["weekday_time"] = result.weekday + "@" + result.observation_time
    return result


def select_features(records, mode):
    """Return normalized original or engineered features for explicit mode.

    Used by both training and saved-model inference; unknown modes raise ValueError.
    """
    if mode == "original":
        return normalize_features(records)
    if mode == "engineered":
        return engineer_features(records)
    raise ValueError(f"Unknown prediction feature mode: {mode}")


class PredictionService:
    """Ready estimator wrapping fitted baseline and optional regression pipeline.

    Args:
        records: Prepared training records used for coverage and baseline fitting.
        model: Optional fitted sklearn pipeline accepting engineered features.
        name: Model name recorded for consumers. No training occurs in predict.
        feature_mode: Explicit original/engineered mode; defaults to the shared
            candidate mapping. Stored in the artifact, independent of name later.
    """

    def __init__(self, records, model=None, name="historical_average",
                 feature_mode=None):
        self.baseline = HistoricalAverage().fit(records)
        self.model = model
        self.name = name
        self.feature_mode = (feature_mode if feature_mode is not None
                             else CANDIDATE_FEATURE_MODES[name])
        select_features(records.iloc[:0], self.feature_mode)
        self.groups = set(records[GROUP_COLUMNS].itertuples(index=False, name=None))
        self.survey_times = sorted(records.observation_time.unique())
        self.weekdays = set(records.weekday)
        self.quarters = set(records.quarter)
        self.training_start = str(records.observation_date.min().date())
        self.training_end = str(records.observation_date.max().date())
        self.artifact_version = ARTIFACT_VERSION
        self.dependency_versions = dependency_versions()

    def support_labels(self, features):
        """Return per-row support reasons using training coverage only.

        features must contain FEATURES. Exact group, survey time, weekday and
        quarter must occur in training; blank quarter is allowed for fallback.
        The same function defines selection rows and request-time abstention.
        """
        frame = normalize_features(features)
        labels = np.full(len(frame), "supported", dtype=object)
        calendar_ok = (frame.weekday.isin(self.weekdays)
                       & frame.quarter.isin(self.quarters | {""})).to_numpy()
        labels[~calendar_ok] = "unsupported_calendar"
        labels[~frame.observation_time.isin(self.survey_times).to_numpy()] = (
            "unsupported_time")
        known = np.array([key in self.groups for key in
                          frame[GROUP_COLUMNS].itertuples(index=False, name=None)],
                         dtype=bool)
        labels[~known] = "unsupported_group"
        return pd.Series(labels, index=features.index, name="support_reason")

    def predict(self, features):
        """Return aligned prediction/baseline_group columns for feature rows.

        Requires FEATURES; blank subtype/level is allowed. Unknown exact groups,
        survey times and weekdays produce NaN with explicit reason labels.
        A blank quarter (outside a verified quarter) uses the historical fallback.
        No location ID, eligibility, date-to-quarter or nearest-time inference is
        performed here; those belong to the registry and arrival adapter.
        """
        frame = normalize_features(features)
        if features.empty:
            return pd.DataFrame({"prediction": pd.Series(dtype=float),
                                 "baseline_group": pd.Series(dtype=str)},
                                index=features.index)
        result = self.baseline.predict(frame)
        labels = self.support_labels(frame).to_numpy()
        supported = labels == "supported"
        if self.model is not None and supported.any():
            # Outside verified quarters, retain an explicitly labeled baseline.
            use_model = supported & frame.quarter.ne("").to_numpy()
            if use_model.any():
                result.loc[use_model, "prediction"] = np.clip(
                    self.model.predict(select_features(
                        frame.loc[use_model], self.feature_mode)), 0, 1)
                result.loc[use_model, "baseline_group"] = "model"
        result.loc[~supported, "prediction"] = np.nan
        result.loc[~supported, "baseline_group"] = labels[~supported]
        return result

    def save(self, path=DEFAULT_ARTIFACT):
        """Serialize this fitted service to path; return the artifact Path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as stream:
            pickle.dump({"artifact_version": ARTIFACT_VERSION,
                         "dependency_versions": self.dependency_versions,
                         "payload": pickle.dumps(self)}, stream)
        return path


def load_prediction_service(path=DEFAULT_ARTIFACT):
    """Load a trusted locally generated artifact, without dataset access or fitting.

    Args:
        path: Pickle from PredictionService.save; never load untrusted pickles.
    Returns:
        Fitted PredictionService. Missing files raise FileNotFoundError.
    """
    with Path(path).open("rb") as stream:
        envelope = pickle.load(stream)
    if not isinstance(envelope, dict) or (
        envelope.get("artifact_version") != ARTIFACT_VERSION
    ):
        raise ValueError("Unsupported prediction artifact; "
                         "rerun src.train_availability")
    trained = envelope.get("dependency_versions")
    current = dependency_versions()
    if trained != current:
        raise ValueError(f"Incompatible prediction dependencies: trained={trained}, "
                         f"runtime={current}. Use the training environment or "
                         "regenerate artifacts with src.train_availability.")
    service = pickle.loads(envelope["payload"])
    if not isinstance(service, PredictionService) or (
        service.artifact_version != ARTIFACT_VERSION
        or service.dependency_versions != trained
    ):
        raise ValueError("Invalid prediction artifact payload; regenerate artifacts")
    return service
