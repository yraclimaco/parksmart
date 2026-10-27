"""Explore integrated parking readings and compare chronological benchmarks.

No observed count, capacity, quality flag, or source identifier is a predictor.
Subtype and level are retained so restricted parking groups remain distinct.
"""

from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

DEFAULT_DATASET = Path("data/processed/pipeline/analysis_dataset.csv")
TEST_DATE_FRACTION = 0.20
NEAR_FULL_THRESHOLD = 0.10
MIN_FACILITY_READINGS = 100  # Descriptive review flag, not an exclusion rule.
TARGET = "fraction_available"
GROUP_COLUMNS = ["facility", "category", "subtype", "level"]
FEATURES = GROUP_COLUMNS + ["weekday", "observation_time", "quarter"]
# Progressively pool sparse groups, ending at the training-wide mean.
BASELINE_LEVELS = [
    FEATURES,
    GROUP_COLUMNS + ["observation_time"],
    GROUP_COLUMNS,
]


def prepare_records(records):
    """Validate exported readings and add calendar features without dropping rows.

    Args:
        records: DataFrame from Dylan's analysis_dataset.csv.
    Returns:
        Copy with parsed dates, weekday names, and blank subtype/level as "".
        Missing required fields, duplicate IDs, and invalid fractions raise
        ValueError; the original records are never modified.
    """
    required = set(FEATURES) - {"weekday"}
    required.update(["record_id", "observation_date", TARGET])
    missing = required - set(records.columns)
    if missing:
        raise ValueError(f"Missing required columns: {sorted(missing)}")
    data = records.copy()
    if data.empty:
        raise ValueError("The analysis dataset is empty")
    if data.record_id.isna().any() or data.record_id.duplicated().any():
        raise ValueError("record_id must be populated and unique")
    data["observation_date"] = pd.to_datetime(
        data.observation_date, errors="raise"
    ).dt.normalize()
    if data.observation_date.isna().any():
        raise ValueError("Every reading needs a survey date")
    data[TARGET] = pd.to_numeric(data[TARGET], errors="raise")
    if (data[TARGET].isna().any() or not np.isfinite(data[TARGET]).all()
            or not data[TARGET].between(0, 1).all()):
        raise ValueError("fraction_available must be finite and between 0 and 1")
    for column in GROUP_COLUMNS[2:]:
        data[column] = data[column].fillna("").astype(str)
    for column in ["facility", "category", "quarter", "observation_time"]:
        blank = data[column].astype(str).str.strip().eq("")
        if data[column].isna().any() or blank.any():
            raise ValueError(f"{column} must be populated")
        data[column] = data[column].astype(str)
    times = pd.to_datetime(data.observation_time, format="%H:%M", errors="raise")
    data["observation_time"] = times.dt.strftime("%H:%M")
    data["weekday"] = data.observation_date.dt.day_name()
    return data


def load_analysis_dataset(path=DEFAULT_DATASET):
    """Read and validate a pipeline CSV at path; return prepared records.

    Identifier and label fields are read as strings to preserve text forms.
    """
    return prepare_records(pd.read_csv(
        path, dtype={column: "string" for column in GROUP_COLUMNS},
        low_memory=False,
    ))


def chronological_split(records, test_fraction=TEST_DATE_FRACTION):
    """Split prepared records on unique survey dates, keeping dates intact.

    Args:
        records: Prepared DataFrame containing observation_date.
        test_fraction: Fraction of distinct dates reserved for the latest test
            period, rounded up. At least one training date must remain.
    Returns:
        Independent (train, test) DataFrames in date then record-ID order.
    """
    if not 0 < test_fraction < 1:
        raise ValueError("test_fraction must be between 0 and 1")
    dates = sorted(records.observation_date.unique())
    test_dates = int(np.ceil(len(dates) * test_fraction))
    if len(dates) < 2 or test_dates >= len(dates):
        raise ValueError("Need at least one training and one test survey date")
    cutoff = dates[-test_dates]
    ordered = records.sort_values(["observation_date", "record_id"])
    return (
        ordered.loc[ordered.observation_date < cutoff].copy(),
        ordered.loc[ordered.observation_date >= cutoff].copy(),
    )


class HistoricalAverage:
    """Training-only grouped means with explicit fallback for unseen groups.

    No constructor parameters. fit(train) returns self; predict(records)
    returns prediction and baseline_group columns indexed like records.
    """

    def fit(self, train):
        """Fit means from nonempty prepared training records; return self."""
        if train.empty:
            raise ValueError("Training data must not be empty")
        self.global_mean_ = float(train[TARGET].mean())
        self.tables_ = [
            train.groupby(columns, dropna=False)[TARGET].mean()
            for columns in BASELINE_LEVELS
        ]
        return self

    def predict(self, records):
        """Return training-based predictions and fallback labels for records."""
        prediction = np.full(len(records), np.nan)
        used = np.full(len(records), "global", dtype=object)
        for number, (columns, table) in enumerate(
            zip(BASELINE_LEVELS, self.tables_), start=1
        ):
            keys = pd.MultiIndex.from_frame(records[columns])
            values = table.reindex(keys).to_numpy(dtype=float)
            select = np.isnan(prediction) & np.isfinite(values)
            prediction[select] = values[select]
            used[select] = f"level_{number}"
        prediction[np.isnan(prediction)] = self.global_mean_
        return pd.DataFrame(
            {"prediction": prediction, "baseline_group": used},
            index=records.index,
        )


def fit_linear_regression(train):
    """Fit one-hot preprocessing and ordinary linear regression on train only.

    Args:
        train: Prepared training records. Only FEATURES enter preprocessing.
    Returns:
        Fitted sklearn Pipeline. Unseen categories produce all-zero indicators;
        raw predictions can be outside [0, 1] and are retained for evaluation.
    """
    encoding = ColumnTransformer([
        ("categories", OneHotEncoder(handle_unknown="ignore"), FEATURES)
    ])
    model = Pipeline([
        ("encoding", encoding), ("regression", LinearRegression())
    ])
    return model.fit(train[FEATURES], train[TARGET])


def evaluate_predictions(actual, predicted, threshold=NEAR_FULL_THRESHOLD):
    """Return errors in percentage points and raw out-of-range diagnostics.

    Args:
        actual: Finite true fractions in [0, 1], in test-row order.
        predicted: Finite raw predictions in the same order.
        threshold: Near-full condition is actual <= threshold (default 10%).
    Returns:
        Dict of counts, raw/clipped MAE, near-full MAE and overprediction error.
        Empty near-full subsets have None metrics rather than misleading zeros.
        Clipping to [0, 1] is the reported primary policy for both methods.
    """
    actual = np.asarray(actual, dtype=float)
    predicted = np.asarray(predicted, dtype=float)
    if (actual.ndim != 1 or predicted.shape != actual.shape or not len(actual)
            or not np.isfinite(actual).all()
            or not np.isfinite(predicted).all()
            or ((actual < 0) | (actual > 1)).any()):
        raise ValueError("Expected aligned finite vectors and valid actual fractions")
    if not 0 <= threshold <= 1:
        raise ValueError("Near-full threshold must be in [0, 1]")
    clipped = np.clip(predicted, 0, 1)
    near = actual <= threshold
    outside = (predicted < 0) | (predicted > 1)
    return {
        "test_readings": len(actual),
        "mae_pp": float(np.abs(clipped - actual).mean() * 100),
        "raw_mae_pp": float(np.abs(predicted - actual).mean() * 100),
        "near_full_readings": int(near.sum()),
        "near_full_mae_pp": (
            float(np.abs(clipped[near] - actual[near]).mean() * 100)
            if near.any() else None
        ),
        "near_full_overprediction_pp": (
            float(np.maximum(clipped[near] - actual[near], 0).mean() * 100)
            if near.any() else None
        ),
        "out_of_range_count": int(outside.sum()),
        "out_of_range_pct": float(outside.mean() * 100),
    }


def run_benchmarks(records, test_fraction=TEST_DATE_FRACTION):
    """Fit both benchmarks and evaluate identical chronological test rows.

    Args:
        records: Prepared dataset from load_analysis_dataset or prepare_records.
        test_fraction: Fraction of latest unique dates assigned to test.
    Returns:
        Dict with train/test frames, row-aligned predictions, metrics, and model.
        The test target is used only for reporting, never for fitting.
    """
    train, test = chronological_split(records, test_fraction)
    baseline = HistoricalAverage().fit(train).predict(test)
    model = fit_linear_regression(train)
    predictions = test[["record_id", "observation_date"] + FEATURES + [TARGET]].copy()
    predictions["historical_average"] = baseline.prediction
    predictions["baseline_group"] = baseline.baseline_group
    predictions["linear_regression_raw"] = model.predict(test[FEATURES])
    predictions["linear_regression"] = predictions.linear_regression_raw.clip(0, 1)
    predictions["unseen_facility"] = ~test.facility.isin(train.facility)
    metrics = pd.DataFrame({
        "historical_average": evaluate_predictions(
            test[TARGET], predictions.historical_average
        ),
        "linear_regression": evaluate_predictions(
            test[TARGET], predictions.linear_regression_raw
        ),
    }).T
    return {"train": train, "test": test, "predictions": predictions,
            "metrics": metrics, "model": model}


def facility_coverage(records):
    """Summarize prepared records per facility; return counts and variability.

    Flags fewer than MIN_FACILITY_READINGS readings for review, without exclusion.
    Variation mixes category, time and period effects; it is not model instability.
    """
    data = records.assign(
        period=records.academic_year.astype(str) + " " + records.quarter
    )
    result = data.groupby("facility").agg(
        readings=(TARGET, "size"), dates=("observation_date", "nunique"),
        quarters=("period", "nunique"), mean_available=(TARGET, "mean"),
        std_available=(TARGET, "std"), first_date=("observation_date", "min"),
        last_date=("observation_date", "max"),
    )
    result["limited_readings"] = result.readings < MIN_FACILITY_READINGS
    return result.sort_values(["readings", "facility"])
