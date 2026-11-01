"""Reproduce Issue #18 chronological comparisons and saved serving artifacts."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression, Ridge
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import OneHotEncoder

from .availability_prediction import PredictionService, engineer_features
from .parking_benchmarks import (
    DEFAULT_DATASET, FEATURES, GROUP_COLUMNS, TARGET, HistoricalAverage,
    chronological_split, evaluate_predictions, load_analysis_dataset,
)

SEED = 42
VALIDATION_SPLITS = 3
# Small fixed comparison budget; no search against the already inspected holdout.
FOREST_TREES = 60
TREE_DEPTH = 12
MIN_LEAF = 10
BOOST_STAGES = 60
BOOST_DEPTH = 3
RIDGE_ALPHA = 10  # Fixed regularization starting point; not holdout-tuned.
CANDIDATES = ("historical_average", "linear_original", "ridge_original",
              "ridge_engineered", "forest_engineered", "boost_engineered")


def date_folds(records, splits=VALIDATION_SPLITS):
    """Yield expanding training/validation frames on disjoint whole survey dates.

    Args:
        records: Prepared development records, excluding the final holdout.
        splits: Number of chronological validation blocks after initial training.
    Returns:
        Iterator of (training, validation) DataFrames; no date crosses a split.
    """
    dates = np.array(sorted(records.observation_date.unique()))
    if len(dates) < splits + 1:
        raise ValueError("Not enough distinct dates for validation")
    blocks = np.array_split(dates, splits + 1)
    for index in range(1, len(blocks)):
        yield (records[records.observation_date.isin(np.concatenate(blocks[:index]))],
               records[records.observation_date.isin(blocks[index])])


def fit_candidate(name, train):
    """Fit named candidate on prepared train records; return fitted estimator.

    name must be one of CANDIDATES. All preprocessing is fitted on train only.
    """
    if name == "historical_average":
        return HistoricalAverage().fit(train)
    estimators = {
        "linear_original": LinearRegression(),
        "ridge_original": Ridge(alpha=RIDGE_ALPHA),
        "ridge_engineered": Ridge(alpha=RIDGE_ALPHA),
        "forest_engineered": RandomForestRegressor(
            n_estimators=FOREST_TREES, max_depth=TREE_DEPTH,
            min_samples_leaf=MIN_LEAF, random_state=SEED, n_jobs=2),
        "boost_engineered": GradientBoostingRegressor(
            n_estimators=BOOST_STAGES, max_depth=BOOST_DEPTH,
            min_samples_leaf=MIN_LEAF, random_state=SEED),
    }
    model = make_pipeline(OneHotEncoder(handle_unknown="ignore"), estimators[name])
    return model.fit(candidate_features(name, train), train[TARGET])


def candidate_features(name, records):
    """Return original or engineered prediction-time features for named model."""
    return (engineer_features(records) if name.endswith("engineered")
            else records[FEATURES])


def predict_candidate(name, model, records):
    """Return raw aligned predictions from a fitted candidate on records."""
    if name == "historical_average":
        return model.predict(records).prediction.to_numpy()
    return model.predict(candidate_features(name, records))


def score_rows(name, model, train, test, split):
    """Return (metric dictionaries, prediction frame) for prepared test rows.

    name identifies the fitted model; train defines exact-group history, and
    split labels exported rows. All candidates score identical test records.
    """
    prediction = predict_candidate(name, model, test)
    groups = set(train[GROUP_COLUMNS].itertuples(index=False, name=None))
    history = np.array([key in groups for key in
                        test[GROUP_COLUMNS].itertuples(index=False, name=None)])
    rows = []
    for label, mask in (("all", np.ones(len(test), dtype=bool)),
                        ("matching_history", history), ("no_history", ~history)):
        if mask.any():
            rows.append(dict(model=name, split=split, coverage=label,
                             **evaluate_predictions(test[TARGET].to_numpy()[mask],
                                                    prediction[mask])))
    predictions = test[["record_id", "observation_date"] + FEATURES + [TARGET]].copy()
    predictions["prediction_raw"] = prediction
    predictions["matching_history"] = history
    predictions["model"] = name
    predictions["split"] = split
    return rows, predictions


def run_training(records, output_dir="results/issue18", model_dir="models/issue18"):
    """Evaluate candidates, select on validation only, save reports and artifacts.

    Args:
        records: Complete prepared analysis dataset.
        output_dir: Local output tables, row predictions and metadata directory.
        model_dir: Local baseline and selected serving artifact directory.
    Returns:
        JSON-compatible run metadata. Final serving fits use all records only
        after holdout scoring; metrics refer to pre-refit models.
    """
    output_dir, model_dir = Path(output_dir), Path(model_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    train, holdout = chronological_split(records)
    # Deliver a fitted baseline before the more expensive comparison begins.
    PredictionService(records).save(model_dir / "baseline.pkl")
    metrics, predictions = [], []
    for fold, (development, validation) in enumerate(date_folds(train), 1):
        for name in CANDIDATES:
            model = fit_candidate(name, development)
            rows, predicted = score_rows(name, model, development, validation,
                                         f"validation_{fold}")
            metrics.extend(rows)
            predictions.append(predicted)
        print(f"Completed validation fold {fold}", flush=True)
    validation_metrics = pd.DataFrame(metrics)
    overall = validation_metrics[validation_metrics.coverage.eq("all")].copy()
    overall["absolute_error"] = overall.mae_pp * overall.test_readings
    summary = overall.groupby("model")[["absolute_error", "test_readings"]].sum()
    summary["mae_pp"] = summary.absolute_error / summary.test_readings
    selected = summary.mae_pp.sort_values(kind="stable").index[0]
    # Holdout results cannot influence the selected model or its settings.
    for name in CANDIDATES:
        model = fit_candidate(name, train)
        rows, predicted = score_rows(name, model, train, holdout, "holdout")
        metrics.extend(rows)
        predictions.append(predicted)
    pd.DataFrame(metrics).to_csv(output_dir / "metrics.csv", index=False)
    pd.concat(predictions).to_csv(output_dir / "predictions.csv", index=False)
    summary.to_csv(output_dir / "validation_summary.csv")
    serving_model = (None if selected == "historical_average"
                     else fit_candidate(selected, records))
    PredictionService(records, serving_model, selected).save(model_dir / "selected.pkl")
    metadata = dict(selected=selected, seed=SEED, records=len(records),
                    sklearn_version=sklearn.__version__,
                    pandas_version=pd.__version__,
                    dataset_sha256=hashlib.sha256(
                        records.sort_values("record_id").to_csv(index=False)
                        .encode("utf-8")).hexdigest(),
                    development_rows=len(train), holdout_rows=len(holdout),
                    holdout_start=str(holdout.observation_date.min().date()),
                    survey_times=sorted(records.observation_time.unique()),
                    validation_mae_pp=summary.mae_pp.to_dict(),
                    holdout_previously_inspected=True,
                    serving_refit="all records after frozen evaluation")
    (output_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return metadata


def main():
    """Run reproducible comparisons from CLI paths and print selection metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", default="results/issue18")
    parser.add_argument("--model-dir", default="models/issue18")
    args = parser.parse_args()
    print(json.dumps(run_training(load_analysis_dataset(args.dataset),
                                  args.output_dir, args.model_dir), indent=2))


if __name__ == "__main__":
    main()
