"""Serving contract, leakage boundaries and reproducible evaluation checks."""

import numpy as np
import pandas as pd
import pytest

from src.availability_prediction import (
    PredictionService, engineer_features, load_prediction_service,
)
from src.parking_benchmarks import FEATURES, prepare_records
from src.train_availability import date_folds, fit_candidate, predict_candidate


@pytest.fixture
def records():
    """Twelve consecutive dates, with distinct restricted groups."""
    return prepare_records(pd.DataFrame([
        dict(record_id=f"{day}-{subtype}", observation_date=f"2025-10-{day:02}",
             facility="P1", category="S", subtype=subtype, level="",
             quarter="Fall", observation_time="08:00", fraction_available=value)
        for day in range(1, 13) for subtype, value in [("", 0.8), ("EV", 0.2)]
    ]))


def test_roundtrip_and_restrictions(records, tmp_path):
    service = PredictionService(records)
    features = records[FEATURES].copy()
    features.index = [4] * len(features)  # Contract allows arbitrary input indices.
    expected = service.predict(features)
    path = service.save(tmp_path / "baseline.pkl")
    restored = load_prediction_service(path)
    pd.testing.assert_frame_equal(expected, restored.predict(features))
    assert expected.prediction.iloc[0] == pytest.approx(0.8)
    assert expected.prediction.iloc[1] == pytest.approx(0.2)
    assert expected.index.equals(features.index)


@pytest.mark.parametrize("column,value,reason", [
    ("level", "Level 2", "unsupported_group"),
    ("subtype", "Reserved", "unsupported_group"),
    ("facility", "unknown", "unsupported_group"),
    ("observation_time", "22:00", "unsupported_time"),
    ("weekday", "invalid", "unsupported_calendar"),
    ("quarter", "invalid", "unsupported_calendar"),
])
def test_unsupported(records, column, value, reason):
    features = records[FEATURES].iloc[:1].copy()
    features[column] = value
    result = PredictionService(records).predict(features)
    assert np.isnan(result.prediction.iloc[0])
    assert result.baseline_group.iloc[0] == reason


def test_empty_and_missing_fields(records):
    service = PredictionService(records)
    assert service.predict(records[FEATURES].iloc[:0]).empty
    with pytest.raises(ValueError, match="Missing"):
        service.predict(records.drop(columns="category"))


def test_outside_quarter_has_explicit_fallback(records):
    features = records[FEATURES].iloc[:1].copy()
    features["quarter"] = ""
    result = PredictionService(records).predict(features)
    assert result.baseline_group.iloc[0] == "level_2"


def test_features_do_not_use_targets_or_metadata(records):
    changed = records.copy()
    changed["fraction_available"] = 1 - changed.fraction_available
    changed["selected_capacity"] = 999
    changed["source_file"] = "other"
    pd.testing.assert_frame_equal(engineer_features(records),
                                  engineer_features(changed))


def test_expanding_folds_are_disjoint(records):
    prior_dates = set()
    for train, validation in date_folds(records):
        assert train.observation_date.max() < validation.observation_date.min()
        assert not prior_dates.intersection(validation.observation_date)
        prior_dates.update(validation.observation_date)


@pytest.mark.parametrize("name", ["linear_original", "ridge_original",
                                 "ridge_engineered", "forest_engineered",
                                 "boost_engineered"])
def test_saved_regressors_match_fitted_predictions(records, tmp_path, name):
    model = fit_candidate(name, records)
    expected = np.clip(predict_candidate(name, model, records), 0, 1)
    path = PredictionService(records, model, name).save(tmp_path / "model.pkl")
    result = load_prediction_service(path).predict(records[FEATURES])
    np.testing.assert_allclose(result.prediction, expected)
    assert result.baseline_group.eq("model").all()


def test_missing_artifact_is_explicit(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_prediction_service(tmp_path / "missing.pkl")


def test_training_exports_and_frozen_selection(records, tmp_path, monkeypatch):
    import json
    import src.train_availability as training

    monkeypatch.setattr(training, "CANDIDATES",
                        ("historical_average", "ridge_engineered"))
    result = training.run_training(records, tmp_path / "reports", tmp_path / "models")
    summary = pd.read_csv(tmp_path / "reports/validation_summary.csv", index_col=0)
    assert result["selected"] == summary.mae_pp.sort_values(kind="stable").index[0]
    metrics = pd.read_csv(tmp_path / "reports/metrics.csv")
    holdout = metrics[metrics.split.eq("holdout") & metrics.coverage.eq("all")]
    assert holdout.test_readings.nunique() == 1
    predictions = pd.read_csv(tmp_path / "reports/predictions.csv")
    test_dates = predictions.loc[predictions.split.eq("holdout"), "observation_date"]
    validation_dates = predictions.loc[
        predictions.split.ne("holdout"), "observation_date"]
    assert test_dates.min() > validation_dates.max()
    assert len(result["dataset_sha256"]) == 64
    assert json.loads((tmp_path / "reports/metadata.json").read_text()) == result
    for artifact in ("baseline.pkl", "selected.pkl"):
        service = load_prediction_service(tmp_path / "models" / artifact)
        assert service.training_end == "2025-10-12"
