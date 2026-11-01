"""Saved prediction service implementing Issue #20's DataFrame contract."""

import pickle
from pathlib import Path

import numpy as np
import pandas as pd

from .parking_benchmarks import FEATURES, GROUP_COLUMNS, HistoricalAverage

ARTIFACT_VERSION = 1
DEFAULT_ARTIFACT = Path("models/issue18/selected.pkl")
BASIS_DESCRIPTIONS = {
    "level_1": None,
    "level_2": "same time, any weekday or quarter",
    "level_3": "all-day average for these stalls",
    "model": "model estimate for historically observed stalls",
    "unsupported_group": "no history for these exact stalls",
    "unsupported_time": "survey time outside training coverage",
    "unsupported_calendar": "weekday or quarter outside training coverage",
}


def engineer_features(records):
    """Return prediction-time categorical features from a DataFrame.

    Adds joint group identity and weekday/time effects without target statistics.
    JSON encoding preserves distinctions even when labels contain separators.
    """
    import json

    result = records[FEATURES].copy()
    result["parking_group"] = [json.dumps(list(row)) for row in
                               result[GROUP_COLUMNS].itertuples(index=False,
                                                               name=None)]
    result["weekday_time"] = result.weekday + "@" + result.observation_time
    return result


class PredictionService:
    """Ready estimator wrapping fitted baseline and optional regression pipeline.

    Args:
        records: Prepared training records used for coverage and baseline fitting.
        model: Optional fitted sklearn pipeline accepting engineered features.
        name: Model name recorded for consumers. No training occurs in predict.
    """

    def __init__(self, records, model=None, name="historical_average"):
        self.baseline = HistoricalAverage().fit(records)
        self.model = model
        self.name = name
        self.groups = set(records[GROUP_COLUMNS].itertuples(index=False, name=None))
        self.survey_times = sorted(records.observation_time.unique())
        self.weekdays = set(records.weekday)
        self.quarters = set(records.quarter)
        self.training_start = str(records.observation_date.min().date())
        self.training_end = str(records.observation_date.max().date())
        self.artifact_version = ARTIFACT_VERSION

    def predict(self, features):
        """Return aligned prediction/baseline_group columns for feature rows.

        Requires FEATURES; blank subtype/level is allowed. Unknown exact groups,
        survey times and weekdays produce NaN with explicit reason labels.
        A blank quarter (outside a verified quarter) uses the historical fallback.
        No location ID, eligibility, date-to-quarter or nearest-time inference is
        performed here; those belong to the registry and arrival adapter.
        """
        missing = set(FEATURES) - set(features)
        if missing:
            raise ValueError(f"Missing prediction fields: {sorted(missing)}")
        if features.empty:
            return pd.DataFrame({"prediction": pd.Series(dtype=float),
                                 "baseline_group": pd.Series(dtype=str)},
                                index=features.index)
        frame = features[FEATURES].copy()
        for column in FEATURES:
            frame[column] = frame[column].fillna("").astype(str)
        result = self.baseline.predict(frame)
        known = np.array([key in self.groups for key in
                          frame[GROUP_COLUMNS].itertuples(index=False, name=None)],
                         dtype=bool)
        time_ok = frame.observation_time.isin(self.survey_times).to_numpy()
        calendar_ok = (frame.weekday.isin(self.weekdays)
                       & frame.quarter.isin(self.quarters | {""})).to_numpy()
        supported = known & time_ok & calendar_ok
        if self.model is not None and supported.any():
            # Outside verified quarters, retain an explicitly labeled baseline.
            use_model = supported & frame.quarter.ne("").to_numpy()
            if use_model.any():
                result.loc[use_model, "prediction"] = np.clip(
                    self.model.predict(
                        frame.loc[use_model, FEATURES]
                        if self.name.endswith("original")
                        else engineer_features(frame.loc[use_model])), 0, 1)
                result.loc[use_model, "baseline_group"] = "model"
        result.loc[~supported, "prediction"] = np.nan
        result.loc[~calendar_ok, "baseline_group"] = "unsupported_calendar"
        result.loc[~time_ok, "baseline_group"] = "unsupported_time"
        result.loc[~known, "baseline_group"] = "unsupported_group"
        return result

    def save(self, path=DEFAULT_ARTIFACT):
        """Serialize this fitted service to path; return the artifact Path."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("wb") as stream:
            pickle.dump(self, stream)
        return path


def load_prediction_service(path=DEFAULT_ARTIFACT):
    """Load a trusted locally generated artifact, without dataset access or fitting.

    Args:
        path: Pickle from PredictionService.save; never load untrusted pickles.
    Returns:
        Fitted PredictionService. Missing files raise FileNotFoundError.
    """
    with Path(path).open("rb") as stream:
        service = pickle.load(stream)
    if not isinstance(service, PredictionService) or (
        service.artifact_version != ARTIFACT_VERSION
    ):
        raise ValueError("Unsupported prediction artifact")
    return service
