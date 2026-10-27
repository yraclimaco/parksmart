"""Reproduce Issue #11 summaries, benchmark results, and exploratory charts."""

import argparse
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd

from src.parking_benchmarks import (
    DEFAULT_DATASET, FEATURES, MIN_FACILITY_READINGS, NEAR_FULL_THRESHOLD,
    TARGET, TEST_DATE_FRACTION, facility_coverage, load_analysis_dataset,
    run_benchmarks,
)

DEFAULT_OUTPUT = Path("results/issue11")
WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday",
            "Saturday", "Sunday"]
CHART_FACILITIES = 15  # Keep facility chart labels readable.
CHART_CATEGORIES = 12


def build_eda_tables(records):
    """Return count/mean EDA tables from prepared records, without filtering.

    Args:
        records: Prepared integrated dataset.
    Returns:
        Dict of DataFrames grouped by facility, category, weekday, time, period,
        and quality/capacity metadata. Means weight each reading equally.
    """
    groups = {
        "facility": ["facility"], "category": ["category"],
        "weekday": ["weekday"], "time": ["observation_time"],
        "period": ["academic_year", "quarter"],
        "weekday_time": ["weekday", "observation_time"],
    }
    tables = {}
    for name, columns in groups.items():
        tables[name] = records.groupby(columns).agg(
            readings=(TARGET, "size"), mean_available=(TARGET, "mean"),
            std_available=(TARGET, "std"),
            first_date=("observation_date", "min"),
            last_date=("observation_date", "max"),
        ).reset_index()
    for column in ["quality_flag", "label_status", "capacity_source"]:
        tables[column] = records.groupby(column, dropna=False).size().rename(
            "readings"
        ).reset_index()
    tables["coverage"] = facility_coverage(records).reset_index()
    return tables


def plot_patterns(tables):
    """Return named matplotlib figures for EDA tables from build_eda_tables.

    The facility chart uses the most-observed locations; all CSV summaries
    retain all groups. Aggregate means do not adjust for category composition.
    """
    figures = {}
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), layout="constrained")
    facility = tables["facility"].nlargest(CHART_FACILITIES, "readings")
    facility = facility.sort_values("mean_available")
    axes[0].barh(facility.facility, facility.mean_available * 100)
    axes[0].set(title="15 most-observed facilities", xlabel="Mean available (%)")
    category = tables["category"].nlargest(CHART_CATEGORIES, "readings")
    category = category.sort_values("mean_available")
    axes[1].barh(category.category, category.mean_available * 100)
    axes[1].set(title="12 most-observed categories", xlabel="Mean available (%)")
    figures["facility_category"] = fig

    table = tables["weekday_time"].pivot(
        index="weekday", columns="observation_time", values="mean_available"
    ).reindex([day for day in WEEKDAYS if day in tables["weekday_time"].weekday.values])
    fig, ax = plt.subplots(figsize=(7, 4), layout="constrained")
    image = ax.imshow(table * 100, vmin=0, vmax=100, cmap="YlGnBu", aspect="auto")
    ax.set_xticks(range(len(table.columns)), table.columns)
    ax.set_yticks(range(len(table.index)), table.index)
    ax.set(title="Availability by weekday and survey time", xlabel="Survey time")
    fig.colorbar(image, ax=ax, label="Mean available (%)")
    figures["weekday_time"] = fig

    period = tables["period"].sort_values("first_date")
    fig, axes = plt.subplots(2, 1, figsize=(11, 7), layout="constrained", sharex=True)
    labels = period.academic_year + " " + period.quarter
    axes[0].bar(labels, period.mean_available * 100)
    axes[0].set(ylabel="Mean available (%)", title="Historical quarter summaries")
    axes[1].bar(labels, period.readings)
    axes[1].set(ylabel="Usable readings")
    axes[1].tick_params(axis="x", rotation=65)
    figures["quarters"] = fig
    return figures


def _markdown_table(frame):
    """Render a small frame without requiring the optional tabulate package."""
    frame = frame.copy().astype(object).fillna("not applicable")
    header = "| " + " | ".join(map(str, frame.columns)) + " |"
    divider = "| " + " | ".join("---" for _ in frame.columns) + " |"
    rows = ["| " + " | ".join(str(value).replace("|", "\\|") for value in row) + " |"
            for row in frame.itertuples(index=False, name=None)]
    return "\n".join([header, divider] + rows)


def export_analysis(records, output_dir=DEFAULT_OUTPUT):
    """Run EDA/benchmarks and write reproducible local reports and figures.

    Args:
        records: Prepared integrated records; no extra exclusions are applied.
        output_dir: Destination for CSVs, PNGs and summary.md.
    Returns:
        Tuple (benchmark result dict, EDA tables dict). Large predictions stay
        local under the repository's existing results ignore rule.
    """
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    tables = build_eda_tables(records)
    result = run_benchmarks(records)
    train, test = result["train"], result["test"]
    predictions, metrics = result["predictions"], result["metrics"]
    for name, table in tables.items():
        table.to_csv(output / f"eda_{name}.csv", index=False)
    metrics.to_csv(output / "metrics.csv", index_label="method")
    predictions.to_csv(output / "test_predictions.csv", index=False)
    fallback = predictions.baseline_group.value_counts().rename("readings")
    fallback.to_csv(output / "baseline_fallback.csv", index_label="group")
    examples = predictions.sort_values(
        ["facility", "observation_date", "record_id"]
    ).groupby("facility", sort=True).head(1).head(10)
    examples = examples[["record_id", "facility", "observation_date", TARGET,
                         "historical_average", "linear_regression"]]
    example_values = [TARGET, "historical_average", "linear_regression"]
    examples[example_values] = examples[example_values].round(4)
    examples.to_csv(output / "example_predictions.csv", index=False)
    # Facility-level errors reveal whether an aggregate score hides poor groups.
    errors = predictions.assign(
        historical_error_pp=(
            predictions.historical_average - predictions[TARGET]
        ).abs() * 100,
        regression_error_pp=(
            predictions.linear_regression - predictions[TARGET]
        ).abs() * 100,
    ).groupby("facility").agg(
        readings=(TARGET, "size"), historical_mae_pp=("historical_error_pp", "mean"),
        regression_mae_pp=("regression_error_pp", "mean"),
        unseen_facility=("unseen_facility", "first"),
    )
    errors.to_csv(output / "facility_errors.csv")
    for name, fig in plot_patterns(tables).items():
        fig.savefig(output / f"{name}.png", dpi=140)
        plt.close(fig)
    baseline_mae = metrics.loc["historical_average", "mae_pp"]
    regression_mae = metrics.loc["linear_regression", "mae_pp"]
    near_scores = []
    for method in ["historical_average", "linear_regression"]:
        score = metrics.loc[method, "near_full_mae_pp"]
        near_scores.append(f"{score:.2f} pp" if pd.notna(score) else "not applicable")
    baseline_near, regression_near = near_scores
    best_time = tables["time"].sort_values("mean_available", ascending=False).iloc[0]
    top_locations = tables["facility"].nlargest(CHART_FACILITIES, "readings")
    top_location = top_locations.sort_values(
        "mean_available", ascending=False
    ).iloc[0]
    best_period = tables["period"].sort_values(
        "mean_available", ascending=False
    ).iloc[0]
    sparse = tables["coverage"].query("limited_readings").facility.tolist()
    variable = tables["coverage"].nlargest(5, "std_available").facility.tolist()
    unseen = predictions.loc[predictions.unseen_facility, "facility"].unique().tolist()
    summary = f"""# Issue #11: parking patterns and first benchmarks

## Data and evaluation design

{len(records):,} readings; {records.facility.nunique()} facilities. No further rows
were removed. Each row, rather than each parking space, receives equal weight.
The latest {TEST_DATE_FRACTION:.0%} of unique survey dates (rounded up) is test;
this rule was selected before fitting. Dates never cross the split.

- Train: {train.observation_date.min().date()} to {train.observation_date.max().date()},
  {len(train):,} readings, {train.observation_date.nunique()} dates,
  {train.facility.nunique()} facilities.
- Test: {test.observation_date.min().date()} to {test.observation_date.max().date()},
  {len(test):,} readings, {test.observation_date.nunique()} dates,
  {test.facility.nunique()} facilities.
- Test facilities absent from training: {unseen or 'none'};
  {int(predictions.unseen_facility.sum()):,} readings.

Historical averages first match facility/category/subtype/level, weekday, time,
and quarter; then back off to parking group + time, parking group alone, and the
training-wide mean. Fallback counts: {fallback.to_dict()}.
Restrictions are retained; pooled/global fallback is a prediction of availability,
not a claim of permit eligibility. Empty subtype/level means unspecified.

Regression uses one-hot indicators for {', '.join(FEATURES)}.
All averages, encoders and regression coefficients are fitted on training only.
Unknown categories have zero indicators. Open counts, capacity, target, quality
flags, source identifiers and capacity decisions are excluded from predictors.
This is an additive ordinary least-squares benchmark, without tuning.

## Results

Primary predictions are clipped to [0, 1] for both methods. Raw regression errors
and out-of-range rates are also reported. MAE is in percentage points (pp): a
10 pp error means, for example, predicting 30% available when 20% were available.
Near full means actual fraction available <= {NEAR_FULL_THRESHOLD:.0%}; its
overprediction metric is the mean positive excess in predicted availability,
including zero for near-full cases without overprediction.

{_markdown_table(metrics.round(4).reset_index(names='method'))}

Regression {'improves' if regression_mae < baseline_mae else 'does not improve'}
on the baseline overall on this holdout: baseline {baseline_mae:.2f} pp versus
regression {regression_mae:.2f} pp, a baseline-minus-regression difference of
{baseline_mae - regression_mae:.2f} pp. This single split is not evidence of
performance in every quarter or at every facility. See facility_errors.csv.
Near-full MAE is {baseline_near} for historical averages versus
{regression_near} for regression. Overall improvement must not be read as
improvement under near-full conditions; review both rows before choosing a model.

## Exploratory findings

- Highest mean availability among the 15 most-observed facilities:
  {top_location.facility} ({top_location.mean_available:.1%}).
- Highest aggregate survey-time mean: {best_time.observation_time}
  ({best_time.mean_available:.1%}).
- Highest aggregate quarter mean: {best_period.academic_year}
  {best_period.quarter} ({best_period.mean_available:.1%}).
- Facilities with fewer than {MIN_FACILITY_READINGS} readings: {sparse}.
  This threshold is a descriptive review flag; those readings remain included.
- eda_coverage.csv reports dates, quarters, counts and standard deviations for
  every facility. The five highest standard deviations are at {variable}.
  High variation can reflect changing category/time composition,
  capacity or actual demand; it does not by itself establish inconsistent data.

Charts: facility_category.png, weekday_time.png and quarters.png. EDA uses the
whole historical dataset descriptively; it does not tune the holdout models.
Category comparisons are descriptive and do not establish permit eligibility.

## Example predictions

One earliest test reading per facility, first ten facilities alphabetically;
not selected by error. Fractions below are on a 0-1 scale.

{_markdown_table(examples)}

## Limitations and next investigations

- QPASS mainly surveys the first weeks of quarters, with missing years/quarters;
  these results cannot establish full-quarter accuracy or live availability.
- Uneven facility/category/time coverage confounds aggregate comparisons.
  Compare common parking groups and time slots before explaining quarter shifts.
- Quarter-wide Inventory fallback assumes capacity holds across survey dates;
  capacity_source, quality_flag and label_status counts are in the EDA CSVs.
  Unchanged labels are not proof of human review.
- Subtype/level and facility histories change; global fallback and unknown
  indicators have limited information for new groups. Review them separately.
- Survey readings on a date are correlated. This holdout reports descriptive
  errors without confidence intervals or claims of statistical significance.
- Review columns, flags, sparse locations and capacity assumptions with Dylan
  (human coordination remains pending; no messages have been sent).
- Next: rolling date-based validation, common-group quarter comparisons,
  and analysis of near-full errors before considering more complex models.
"""
    (output / "summary.md").write_text(summary, encoding="utf-8")
    return result, tables


def main():
    """Parse dataset/output CLI paths, generate local artifacts, and print scores."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=DEFAULT_DATASET)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    records = load_analysis_dataset(args.dataset)
    result, _ = export_analysis(records, args.output_dir)
    print(result["metrics"].to_string())
    print(f"Reports written to {args.output_dir}")


if __name__ == "__main__":
    main()
