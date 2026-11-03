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
    holdout = metrics[metrics.split.eq("holdout") & metrics.coverage.eq("supported")]
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


def test_artifact_checks_dependencies_before_deserializing_model(records, tmp_path):
    import pickle

    path = PredictionService(records).save(tmp_path / "model.pkl")
    envelope = pickle.loads(path.read_bytes())
    assert "scikit-learn" in envelope["dependency_versions"]
    envelope["dependency_versions"]["scikit-learn"] = "0.0.0"
    envelope["payload"] = b"invalid model pickle must not be read"
    path.write_bytes(pickle.dumps(envelope))
    with pytest.raises(ValueError, match="Incompatible prediction dependencies"):
        load_prediction_service(path)


def test_old_artifacts_request_retraining(records, tmp_path):
    import pickle

    path = tmp_path / "old.pkl"
    path.write_bytes(pickle.dumps({"artifact_version": 1}))
    with pytest.raises(ValueError, match="rerun src.train_availability"):
        load_prediction_service(path)


def test_feature_mode_survives_model_rename_and_roundtrip(records, tmp_path):
    from src.train_availability import candidate_features

    model = fit_candidate("ridge_engineered", records)
    service = PredictionService(records, model, "ridge_engineered")
    service.name = "deployment-label-with-no-feature-suffix"
    restored = load_prediction_service(service.save(tmp_path / "renamed.pkl"))
    expected = model.predict(candidate_features("ridge_engineered", records))
    np.testing.assert_allclose(restored.predict(records).prediction,
                               np.clip(expected, 0, 1))


def test_regression_blank_quarter_uses_baseline_without_model_call(
        records, tmp_path, monkeypatch):
    model = fit_candidate("ridge_engineered", records)
    service = load_prediction_service(PredictionService(
        records, model, "ridge_engineered").save(tmp_path / "regression.pkl"))

    def must_not_predict(*args):
        raise AssertionError("Blank quarter must use baseline")

    monkeypatch.setattr(service.model, "predict", must_not_predict)
    features = records[FEATURES].copy()
    features["quarter"] = ""
    expected = service.baseline.predict(features)
    actual = service.predict(features)
    pd.testing.assert_frame_equal(actual, expected)
    assert actual.baseline_group.eq("level_2").all()


def test_selection_ignores_experimental_and_holdout_wins():
    from src.train_availability import select_model

    rows = [dict(model=model, split=split, coverage=coverage, test_readings=10,
                 near_full_readings=2, mae_pp=error, near_full_mae_pp=error)
            for model, error, split, coverage in [
                ("historical_average", 10, "validation_1", "supported"),
                ("ridge_engineered", 12, "validation_1", "supported"),
                ("historical_average", 90, "validation_1", "all_experimental"),
                ("ridge_engineered", 0, "validation_1", "all_experimental"),
                ("historical_average", 100, "holdout", "supported"),
                ("ridge_engineered", 0, "holdout", "supported"),
            ]]
    assert select_model(pd.DataFrame(rows))[0] == "historical_average"


def test_training_holdout_target_changes_cannot_change_selection(
        records, tmp_path, monkeypatch):
    import src.train_availability as training
    from src.parking_benchmarks import chronological_split

    monkeypatch.setattr(training, "CANDIDATES",
                        ("historical_average", "ridge_engineered"))
    changed = records.copy()
    _, holdout = chronological_split(records)
    changed.loc[holdout.index, "fraction_available"] = (
        1 - changed.loc[holdout.index, "fraction_available"])
    first = training.run_training(records, tmp_path / "r1", tmp_path / "m1")
    second = training.run_training(changed, tmp_path / "r2", tmp_path / "m2")
    assert first["selected"] == second["selected"]
    pd.testing.assert_frame_equal(
        pd.read_csv(tmp_path / "r1/validation_summary.csv"),
        pd.read_csv(tmp_path / "r2/validation_summary.csv"))
    assert not pd.read_csv(tmp_path / "r1/holdout_coverage.csv").equals(
        pd.read_csv(tmp_path / "r2/holdout_coverage.csv"))


def test_serving_and_scoring_share_supported_rows(records):
    from src.train_availability import score_rows

    test = records.copy()
    test.loc[0, "facility"] = "unknown"
    test.loc[1, "observation_time"] = "22:00"
    test.loc[2, "weekday"] = "invalid"
    expected = PredictionService(records).predict(test).prediction.notna()
    supported_ids = []
    for name in ("historical_average", "ridge_engineered"):
        model = fit_candidate(name, records)
        metrics, predictions = score_rows(name, model, records, test, "validation_1")
        supported_ids.append(predictions.loc[
            predictions.support_reason.eq("supported"), "record_id"].tolist())
        np.testing.assert_array_equal(predictions.served_prediction.notna(), expected)
        counts = {row["coverage"]: row["test_readings"] for row in metrics}
        assert counts["supported"] + counts["unsupported_experimental"] == len(test)
    assert supported_ids[0] == supported_ids[1]


@pytest.mark.parametrize("name", ["historical_average", "ridge_engineered"])
def test_saved_service_through_estimator_recommender_and_fastapi(
        tmp_path, monkeypatch, name):
    from fastapi.testclient import TestClient
    from src.api.saved_model import create_saved_app
    from src.api.schemas import RecommendationResponse
    from src.parking_benchmarks import HistoricalAverage

    data = prepare_records(pd.DataFrame([
        dict(record_id=facility, facility=facility, category="S", subtype="",
             level="", observation_date="2026-10-06", observation_time="10:00",
             academic_year="2026-2027", quarter="Fall", fraction_available=value)
        for facility, value in (("Gilman", 0.6), ("Hopkins", 0.4))
    ]))
    fitted = None if name == "historical_average" else fit_candidate(name, data)
    path = PredictionService(data, fitted, name).save(tmp_path / "service.pkl")
    data.to_csv(tmp_path / "data.csv", index=False)

    def no_retraining(*args):
        raise AssertionError("Startup/prediction must not fit the saved service")

    monkeypatch.setattr(HistoricalAverage, "fit", no_retraining)
    app = create_saved_app(artifact_path=path, dataset_path=tmp_path / "data.csv")
    with TestClient(app) as client:
        for time in ("10:00:00", "09:00:00"):
            response = client.post("/recommendations", json={
                "destination": {"name": "Test", "coordinates": None},
                "arrival_time": f"2026-11-03T{time}", "permit_type": "S"})
            assert response.status_code == 200
            body = response.json()
            RecommendationResponse.model_validate(body)
            assert body["status"] == "ready"
            first, backup = body["first_choice"], body["backup_choice"]
            assert first["location"]["location_id"] != backup["location"]["location_id"]
            assert all(0 <= choice["estimated_available_fraction"] <= 1
                       for choice in (first, backup))
            if name != "historical_average":
                assert "Model estimate based on historical surveys" in first["explanation"]
                limited = [note for note in body["limitations"]
                           if "estimate is limited" in note]
                assert bool(limited) == (time == "09:00:00")


def test_saved_api_does_not_silently_replace_missing_artifacts(tmp_path):
    from src.api.saved_model import create_saved_app

    with pytest.raises(FileNotFoundError):
        create_saved_app(artifact_path=tmp_path / "missing.pkl")


def test_no_supported_validation_rows_cannot_select_a_model():
    from src.train_availability import select_model

    metrics = pd.DataFrame([dict(model="historical_average", split="validation_1",
                                 coverage="supported", test_readings=0)])
    with pytest.raises(ValueError, match="No supported validation rows"):
        select_model(metrics)
