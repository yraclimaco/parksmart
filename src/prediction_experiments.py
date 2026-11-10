"""Issue #27 train-only recency experiments; never replace serving artifacts."""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .availability_prediction import PredictionService, dependency_versions
from .parking_benchmarks import (
    BASELINE_LEVELS, DEFAULT_DATASET, FEATURES, GROUP_COLUMNS,
    NEAR_FULL_THRESHOLD, TARGET, HistoricalAverage, chronological_split,
    evaluate_predictions, load_analysis_dataset,
)
from .train_availability import date_folds

METHODS = ("historical_average", "recent_3_years", "decay_2_years")
RECENT_YEARS = 3
HALF_LIFE_DAYS = 365.25 * 2
LARGE_OVERPREDICTION = 0.20
# Declared before running: a small pooled gain alone is insufficient evidence.
MIN_GAIN_PP = 1.0
MAX_FOLD_REGRESSION_PP = 0.5
HISTORY_BINS = [0, 4, 19, 49, np.inf]
HISTORY_LABELS = ["1-4 dates", "5-19 dates", "20-49 dates", "50+ dates"]


class RecencyAverage:
    """Fit a recent-window or decayed baseline without changing exact groups.

    Args:
        method: recent_3_years or decay_2_years. Window estimates use full
            history for exact groups absent recently. Decay retains all rows.
    """

    def __init__(self, method):
        if method not in METHODS[1:]:
            raise ValueError(f"Unknown recency method: {method}")
        self.method = method

    def fit(self, train):
        """Fit only prepared training records; return this fitted estimator."""
        self.full = HistoricalAverage().fit(train)
        self.reference_date = train.observation_date.max()
        if self.method == "recent_3_years":
            self.cutoff = self.reference_date - pd.DateOffset(years=RECENT_YEARS)
            recent = train.loc[train.observation_date >= self.cutoff]
            self.recent = HistoricalAverage().fit(recent)
            self.recent_groups = set(
                recent[GROUP_COLUMNS].itertuples(index=False, name=None))
        else:
            age = (self.reference_date - train.observation_date).dt.days
            weights = np.exp2(-age / HALF_LIFE_DAYS)
            weighted = train.assign(_weight=weights, _target=train[TARGET] * weights)
            self.weighted = HistoricalAverage().fit(train)
            self.weighted.tables_ = []
            for columns in BASELINE_LEVELS:
                totals = weighted.groupby(columns, dropna=False)[
                    ["_weight", "_target"]].sum()
                self.weighted.tables_.append(totals._target / totals._weight)
            self.weighted.global_mean_ = float(
                weighted._target.sum() / weighted._weight.sum())
        return self

    def predict(self, records):
        """Return aligned estimates with the existing historical fallback levels."""
        if self.method == "decay_2_years":
            return self.weighted.predict(records)
        result = self.full.predict(records)
        use_recent = np.array([
            group in self.recent_groups for group in
            records[GROUP_COLUMNS].itertuples(index=False, name=None)], dtype=bool)
        if use_recent.any():
            result.loc[use_recent, :] = self.recent.predict(records.loc[use_recent])
        return result


def history_details(train, validation):
    """Return validation-aligned exact-group training counts, dates and spans.

    Both inputs are prepared records. Counts never include validation targets.
    Unknown exact groups have zero history and a missing span.
    """
    history = train.groupby(GROUP_COLUMNS).agg(
        training_readings=(TARGET, "size"),
        training_dates=("observation_date", "nunique"),
        first_training_date=("observation_date", "min"),
        last_training_date=("observation_date", "max"),
    )
    keys = pd.MultiIndex.from_frame(validation[GROUP_COLUMNS])
    result = history.reindex(keys).reset_index(drop=True)
    result.index = validation.index
    result[["training_readings", "training_dates"]] = result[
        ["training_readings", "training_dates"]].fillna(0).astype(int)
    result["training_span_days"] = (
        result.last_training_date - result.first_training_date).dt.days
    result["history_bin"] = pd.cut(result.training_dates, HISTORY_BINS,
                                   labels=HISTORY_LABELS).astype("string").fillna(
                                       "no history")
    return result


def error_metrics(frame):
    """Return supported-row errors and coverage for a prediction frame.

    frame contains TARGET and served_prediction. Unsupported rows count in the
    coverage denominator only; empty supported/near-full metrics remain null.
    """
    supported = frame.served_prediction.notna()
    scored = frame.loc[supported]
    result = dict(rows=len(frame), supported_rows=int(supported.sum()),
                  coverage_pct=float(supported.mean() * 100),
                  mae_pp=None, near_full_mae_pp=None,
                  near_full_overprediction_pp=None, near_full_readings=0,
                  large_near_full_overpredictions=0)
    if not scored.empty:
        result.update(evaluate_predictions(scored[TARGET], scored.served_prediction))
        near = scored[TARGET] <= NEAR_FULL_THRESHOLD
        result["large_near_full_overpredictions"] = int((near & (
            scored.served_prediction - scored[TARGET] > LARGE_OVERPREDICTION)).sum())
    return result


def choose_method(summary, fold_metrics):
    """Return conservative validation-only recommendation from metric tables.

    Requires at least 1 pp pooled MAE gain, no worse near-full MAE, equal
    coverage and no fold losing over 0.5 pp. No holdout metrics are accepted.
    Returns an experimental recommendation, never changes approved artifacts.
    """
    if not fold_metrics.split.str.startswith("validation_").all():
        raise ValueError("Selection accepts development validation folds only")
    baseline = summary.loc["historical_average"]
    fold_base = fold_metrics.query("method == 'historical_average'").set_index("split")
    eligible = []
    for name in METHODS[1:]:
        row = summary.loc[name]
        folds = fold_metrics[fold_metrics.method.eq(name)].set_index("split")
        if (baseline.mae_pp - row.mae_pp >= MIN_GAIN_PP
                and row.near_full_mae_pp <= baseline.near_full_mae_pp
                and row.supported_rows == baseline.supported_rows
                and folds.index.equals(fold_base.index)
                and (folds.mae_pp - fold_base.mae_pp).le(
                    MAX_FOLD_REGRESSION_PP).all()):
            eligible.append(name)
    return min(eligible, key=lambda name: (summary.loc[name, "mae_pp"], name)) if (
        eligible) else "historical_average"


def run_experiments(records, output_dir="results/issue27"):
    """Export chronological validation diagnostics and two fixed experiments.

    Args:
        records: Complete prepared integrated readings; latest 20% of survey
            dates are excluded before analysis and never scored here.
        output_dir: Local, gitignored CSV/metadata directory.
    Returns:
        JSON-compatible metadata. No production model path is read or written.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    development, holdout = chronological_split(records)
    predictions, folds = [], []
    for number, (train, validation) in enumerate(date_folds(development), 1):
        split = f"validation_{number}"
        details = history_details(train, validation)
        expected_ids = None
        for method in METHODS:
            service = PredictionService(train)
            if method != "historical_average":
                service.baseline = RecencyAverage(method).fit(train)
            estimates = service.predict(validation)
            frame = validation[["record_id", "observation_date"] + FEATURES + [TARGET]]
            frame = frame.join(details).copy()
            frame["served_prediction"] = estimates.prediction
            frame["support_reason"] = service.support_labels(validation)
            frame["baseline_group"] = estimates.baseline_group
            frame["method"], frame["split"] = method, split
            ids = frame.loc[frame.served_prediction.notna(), "record_id"].tolist()
            if expected_ids is not None and ids != expected_ids:
                raise ValueError("Candidates must predict identical supported record IDs")
            expected_ids = ids
            predictions.append(frame)
            folds.append(dict(method=method, split=split,
                              train_rows=len(train), train_start=str(
                                  train.observation_date.min().date()),
                              train_end=str(train.observation_date.max().date()),
                              validation_start=str(validation.observation_date.min().date()),
                              validation_end=str(validation.observation_date.max().date()),
                              **error_metrics(frame)))
    predictions = pd.concat(predictions, ignore_index=True)
    fold_metrics = pd.DataFrame(folds)
    summary = pd.DataFrame([
        dict(method=method, **error_metrics(predictions[predictions.method.eq(method)]))
        for method in METHODS]).set_index("method")
    recommendation = choose_method(summary, fold_metrics)
    predictions.to_csv(output / "predictions.csv", index=False)
    fold_metrics.to_csv(output / "fold_metrics.csv", index=False)
    summary.to_csv(output / "validation_summary.csv")
    baseline = predictions[predictions.method.eq("historical_average")]
    for dimension in ("facility", "category", "quarter", "history_bin", "baseline_group"):
        pd.DataFrame([
            {dimension: label, **error_metrics(group)}
            for label, group in baseline.groupby(dimension, dropna=False)
        ]).to_csv(output / f"errors_by_{dimension}.csv", index=False)
    baseline.groupby(["split", "support_reason"]).size().rename("rows").to_csv(
        output / "support_counts.csv")
    metadata = dict(
        recommended_method=recommendation, approved_method="historical_average",
        development_rows=len(development), excluded_holdout_rows=len(holdout),
        excluded_holdout_start=str(holdout.observation_date.min().date()),
        holdout_scored=False, holdout_previously_inspected=True,
        selection_rule=dict(min_mae_gain_pp=MIN_GAIN_PP,
                            max_fold_regression_pp=MAX_FOLD_REGRESSION_PP,
                            near_full_must_not_worsen=True, equal_supported_ids=True),
        recent_years=RECENT_YEARS, decay_half_life_days=HALF_LIFE_DAYS,
        development_sha256=hashlib.sha256(
            development.sort_values("record_id").to_csv(index=False)
            .encode("utf-8")).hexdigest(),
        dependency_versions=dependency_versions(),
        validation_is_exploratory=True,
    )
    (output / "metadata.json").write_text(json.dumps(metadata, indent=2) + "\n",
                                           encoding="utf-8")
    return metadata


def main():
    """Read CLI dataset/output paths, run local experiments and print metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=Path("results/issue27"))
    args = parser.parse_args()
    print(json.dumps(run_experiments(load_analysis_dataset(args.dataset),
                                     args.output_dir), indent=2))


if __name__ == "__main__":
    main()
