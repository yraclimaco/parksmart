"""Recency statistics, unchanged serving support and holdout isolation."""

import json

import numpy as np
import pandas as pd
import pytest

from src.availability_prediction import PredictionService
from src.parking_benchmarks import chronological_split, prepare_records
from src.prediction_experiments import (
    HALF_LIFE_DAYS, INSPECTED_HOLDOUT_START, METHODS, RecencyAverage,
    choose_method, error_metrics, history_details, run_experiments,
    split_experiment_records,
)


def sample(rows):
    """Prepare (date, facility, target) tuples with distinct exact groups."""
    return prepare_records(pd.DataFrame([
        dict(record_id=str(index), observation_date=date, facility=facility,
             category="S", subtype="EV" if facility == "restricted" else "",
             level="", quarter="Fall", observation_time="08:00",
             fraction_available=target)
        for index, (date, facility, target) in enumerate(rows)
    ]))


def test_recent_window_falls_back_to_exact_old_group():
    records = sample([("2018-10-02", "old", 0.1),
                      ("2018-10-02", "active", 0.9),
                      ("2025-10-07", "active", 0.4),
                      ("2025-10-07", "restricted", 0.8)])
    estimator = RecencyAverage("recent_3_years").fit(records)
    result = estimator.predict(records)
    assert result.prediction.tolist() == pytest.approx([0.1, 0.4, 0.4, 0.8])
    assert estimator.cutoff == pd.Timestamp("2022-10-07")


def test_decay_uses_training_reference_date_and_weighted_targets():
    records = sample([("2020-10-06", "P1", 0.8),
                      ("2022-10-06", "P1", 0.2)])
    model = RecencyAverage("decay_2_years").fit(records)
    # Same exact feature stratum, so the older target gets about half the weight.
    query = records.iloc[[0]].copy()
    query["weekday"] = "unknown weekday"  # Exercise group/time fallback table.
    age = (pd.Timestamp("2022-10-06") - pd.Timestamp("2020-10-06")).days
    weight = 2 ** (-age / HALF_LIFE_DAYS)
    assert model.predict(query).prediction.iloc[0] == pytest.approx(
        (0.8 * weight + 0.2) / (weight + 1))
    query["observation_date"] = pd.Timestamp("2099-01-01")
    assert model.reference_date == pd.Timestamp("2022-10-06")


@pytest.mark.parametrize("method", METHODS[1:])
def test_experiment_retains_service_support_and_blank_quarter_fallback(method):
    records = sample([("2020-10-06", "P1", 0.9),
                      ("2025-10-07", "P1", 0.2)])
    service = PredictionService(records)
    service.baseline = RecencyAverage(method).fit(records)
    queries = pd.concat([records.iloc[[0]]] * 5, ignore_index=True)
    queries.loc[1, "subtype"] = "Reserved"
    queries.loc[2, "observation_time"] = "22:00"
    queries.loc[3, "weekday"] = "Sunday"
    queries.loc[4, "quarter"] = ""
    result = service.predict(queries)
    assert result.prediction.notna().tolist() == [True, False, False, False, True]
    assert result.baseline_group.tolist()[1:] == [
        "unsupported_group", "unsupported_time", "unsupported_calendar", "level_2"]


def test_history_counts_preserve_restrictions_and_do_not_use_validation():
    train = sample([("2020-10-06", "P1", 0.9),
                    ("2020-10-07", "P1", 0.2)])
    validation = sample([("2025-10-07", "P1", 0.2),
                         ("2025-10-07", "restricted", 0.9)])
    details = history_details(train, validation)
    assert details.training_readings.tolist() == [2, 0]
    assert details.training_dates.tolist() == [2, 0]
    assert details.history_bin.tolist() == ["1-4 dates", "no history"]
    assert details.training_span_days.iloc[0] == 1
    assert pd.isna(details.training_span_days.iloc[1])


def test_near_full_errors_and_unsupported_coverage():
    frame = pd.DataFrame({"fraction_available": [0.0, 0.1, 0.9, 0.0],
                          "served_prediction": [0.3, 0.0, 0.8, np.nan]})
    metrics = error_metrics(frame)
    assert metrics["coverage_pct"] == 75
    assert metrics["near_full_readings"] == 2
    assert metrics["near_full_mae_pp"] == pytest.approx(20)
    assert metrics["near_full_overprediction_pp"] == pytest.approx(15)
    assert metrics["large_near_full_overpredictions"] == 1


def test_selection_requires_useful_gain_and_near_full_nonregression():
    summary = pd.DataFrame([
        dict(method=method, mae_pp=error, near_full_mae_pp=near, supported_rows=10)
        for method, error, near in zip(METHODS, [20, 19.5, 18], [10, 9, 11])
    ]).set_index("method")
    folds = pd.DataFrame([
        dict(method=method, split="validation_1", mae_pp=summary.loc[method, "mae_pp"])
        for method in METHODS])
    assert choose_method(summary, folds) == "historical_average"
    summary.loc["decay_2_years", "near_full_mae_pp"] = 9
    assert choose_method(summary, folds) == "decay_2_years"
    folds.loc[folds.method.eq("decay_2_years"), "mae_pp"] = 21
    assert choose_method(summary, folds) == "historical_average"
    folds.loc[0, "split"] = "holdout"
    with pytest.raises(ValueError, match="validation folds only"):
        choose_method(summary, folds)


def test_exports_use_identical_ids_and_ignore_holdout_targets(tmp_path):
    records = sample([(str(date.date()), facility, target)
                      for date in pd.date_range("2025-09-01", periods=48)
                      for facility, target in [("P1", 0.2), ("restricted", 0.8)]])
    first = run_experiments(records, tmp_path / "first")
    changed = records.copy()
    _, holdout = split_experiment_records(records)
    changed.loc[holdout.index, "fraction_available"] = 1 - changed.loc[
        holdout.index, "fraction_available"]
    second = run_experiments(changed, tmp_path / "second")
    assert first == second
    for filename in ("validation_summary.csv", "fold_metrics.csv", "predictions.csv"):
        assert (tmp_path / "first" / filename).read_bytes() == (
            tmp_path / "second" / filename).read_bytes()
    exported = pd.read_csv(tmp_path / "first/predictions.csv")
    assert exported.observation_date.max() < str(holdout.observation_date.min().date())
    for _, fold in exported.groupby("split"):
        ids = [group.loc[group.served_prediction.notna(), "record_id"].tolist()
               for _, group in fold.groupby("method")]
        assert ids[0] == ids[1] == ids[2]
    assert json.loads((tmp_path / "first/metadata.json").read_text()) == first


def test_appending_future_dates_keeps_inspected_holdout_out_of_development(tmp_path):
    records = sample([(str(date.date()), "P1", 0.2)
                      for date in pd.date_range("2025-09-01", periods=48)])
    future = sample([(str(date.date()), "P1", 0.9)
                     for date in pd.date_range("2027-01-01", periods=100)])
    future["record_id"] = "future-" + future.record_id
    expanded = pd.concat([records, future], ignore_index=True)
    # Demonstrate the failure that a recalculated latest-20% split would cause.
    moving_development, _ = chronological_split(expanded)
    assert (moving_development.observation_date >= INSPECTED_HOLDOUT_START).any()

    first = run_experiments(records, tmp_path / "original")
    second = run_experiments(expanded, tmp_path / "expanded")
    assert first["development_rows"] == second["development_rows"] == 37
    assert first["development_sha256"] == second["development_sha256"]
    assert first["recommended_method"] == second["recommended_method"]
    assert first["excluded_holdout_start"] == second[
        "excluded_holdout_start"] == "2025-10-08"
    assert second["excluded_holdout_rows"] == first["excluded_holdout_rows"] + 100
    for filename in ("validation_summary.csv", "fold_metrics.csv", "predictions.csv"):
        assert (tmp_path / "original" / filename).read_bytes() == (
            tmp_path / "expanded" / filename).read_bytes()
    predictions = pd.read_csv(tmp_path / "expanded/predictions.csv")
    assert pd.to_datetime(predictions.observation_date).lt(
        INSPECTED_HOLDOUT_START).all()
    assert not predictions.record_id.astype(str).str.startswith("future-").any()


def test_fixed_split_preserves_boundary_when_first_excluded_date_is_missing():
    records = sample([("2025-10-07", "P1", 0.2),
                      ("2025-10-09", "P1", 0.9)])
    development, excluded = split_experiment_records(records)
    assert development.observation_date.tolist() == [pd.Timestamp("2025-10-07")]
    assert excluded.observation_date.tolist() == [pd.Timestamp("2025-10-09")]


def test_fixed_split_rejects_missing_development_history():
    records = sample([("2025-10-08", "P1", 0.2),
                      ("2026-10-08", "P1", 0.9)])
    with pytest.raises(ValueError, match="fixed inspected holdout boundary 2025-10-08"):
        split_experiment_records(records)
