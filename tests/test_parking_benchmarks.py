"""Correctness checks for chronological parking benchmark evaluation."""

import numpy as np
import pandas as pd
import pytest

from src.parking_benchmarks import (
    FEATURES, HistoricalAverage, chronological_split, evaluate_predictions,
    facility_coverage, fit_linear_regression, prepare_records, run_benchmarks,
)


def sample_records():
    """Return four dates with two restricted parking groups on each date."""
    return prepare_records(pd.DataFrame([
        dict(record_id=f"{day}-{group}", observation_date=f"2025-10-{day:02}",
             facility="P1", category="S", subtype=group, level=None,
             observation_time="08:00", quarter="Fall", academic_year="2025-2026",
             fraction_available=value, open_spaces=100 * value)
        for day in range(1, 5)
        for group, value in [("EV", 0.2), ("", 0.8)]
    ]))


def test_prepare_preserves_input_and_restrictions():
    source = sample_records()
    original = source.copy(deep=True)
    actual = prepare_records(source)
    pd.testing.assert_frame_equal(source, original)
    assert len(actual) == 8
    assert set(actual.subtype) == {"EV", ""}
    assert actual.level.eq("").all()
    assert actual.weekday.iloc[0] == "Wednesday"


@pytest.mark.parametrize("column,value", [
    ("fraction_available", np.nan), ("fraction_available", 1.1),
    ("fraction_available", -0.1), ("fraction_available", np.inf),
    ("observation_date", None), ("observation_date", "bad"),
    ("category", ""), ("facility", None), ("observation_time", "25:00"),
])
def test_prepare_rejects_invalid_records(column, value):
    data = sample_records()
    data[column] = data[column].astype(object)
    data.loc[0, column] = value
    with pytest.raises((ValueError, TypeError)):
        prepare_records(data)


def test_prepare_rejects_duplicate_ids_and_missing_columns():
    data = sample_records()
    with pytest.raises(ValueError, match="unique"):
        prepare_records(pd.concat([data, data]))
    with pytest.raises(ValueError, match="Missing"):
        prepare_records(data.drop(columns="subtype"))


def test_prepare_rejects_nullable_missing_target():
    data = sample_records()
    data["fraction_available"] = data.fraction_available.astype("Float64")
    data.loc[0, "fraction_available"] = pd.NA
    with pytest.raises(ValueError, match="finite"):
        prepare_records(data)


def test_split_keeps_dates_together_and_is_order_independent():
    data = sample_records().sample(frac=1, random_state=11)
    train, test = chronological_split(data, 0.25)
    assert len(train) == 6 and len(test) == 2
    assert train.observation_date.max() < test.observation_date.min()
    assert set(train.record_id).isdisjoint(test.record_id)
    assert len(train) + len(test) == len(data)
    expected = chronological_split(data.sort_index(), 0.25)
    pd.testing.assert_frame_equal(test, expected[1])
    with pytest.raises(ValueError):
        chronological_split(data, 1)
    with pytest.raises(ValueError):
        chronological_split(data.loc[
            data.observation_date == data.observation_date.min()
        ])


def test_baseline_restrictions_and_all_fallback_levels():
    train, test = chronological_split(sample_records(), 0.25)
    model = HistoricalAverage().fit(train)
    # Make full key present, including weekday, to exercise level 1.
    query = train.iloc[:1].copy()
    assert model.predict(query).baseline_group.iloc[0] == "level_1"
    query["weekday"] = "Sunday"
    assert model.predict(query).baseline_group.iloc[0] == "level_2"
    query["observation_time"] = "14:00"
    assert model.predict(query).baseline_group.iloc[0] == "level_3"
    query["facility"] = "new"
    result = model.predict(query)
    assert result.baseline_group.iloc[0] == "global"
    assert result.prediction.iloc[0] == pytest.approx(0.5)
    assert model.predict(test).prediction.tolist() == pytest.approx([0.8, 0.2])


def test_model_handles_unknowns_and_ignores_observed_counts():
    train, test = chronological_split(sample_records(), 0.25)
    model = fit_linear_regression(train)
    before = model.predict(test)
    changed = test.copy()
    changed["open_spaces"] = -99999
    changed["fraction_available"] = 0
    np.testing.assert_allclose(model.predict(changed), before)
    changed["facility"] = "unseen"
    assert np.isfinite(model.predict(changed)).all()
    assert "open_spaces" not in FEATURES


def test_test_targets_cannot_change_fitted_predictions():
    data = sample_records()
    first = run_benchmarks(data, 0.25)
    data.loc[data.observation_date == data.observation_date.max(),
             "fraction_available"] = 0
    second = run_benchmarks(data, 0.25)
    for name in ["historical_average", "linear_regression_raw"]:
        np.testing.assert_allclose(
            first["predictions"][name], second["predictions"][name]
        )
    assert first["predictions"].record_id.tolist() == first["test"].record_id.tolist()


def test_metrics_clipping_units_and_near_full_boundary():
    result = evaluate_predictions([0, 0.1, 1], [-0.2, 0.3, 1.2])
    assert result["mae_pp"] == pytest.approx(20 / 3)
    assert result["raw_mae_pp"] == pytest.approx(20)
    assert result["near_full_readings"] == 2
    assert result["near_full_mae_pp"] == pytest.approx(10)
    assert result["near_full_overprediction_pp"] == pytest.approx(10)
    assert result["out_of_range_count"] == 2
    assert evaluate_predictions([0.5], [0.5])["near_full_mae_pp"] is None
    for actual, predicted in [([], []), ([0], [np.nan]), ([0], [0, 1])]:
        with pytest.raises(ValueError):
            evaluate_predictions(actual, predicted)


def test_coverage_flags_without_dropping_readings():
    coverage = facility_coverage(sample_records())
    assert coverage.readings.sum() == 8
    assert coverage.limited_readings.all()
    assert coverage.dates.iloc[0] == 4
