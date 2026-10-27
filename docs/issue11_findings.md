# Issue #11: parking patterns and first benchmarks

Snapshot verified locally on 2026-10-27 against pipeline base commit `9f606a9`.
Dataset SHA-256: `5b5e25e60a7fa12f8e6ac94a8a9b7ced1f5892ee977b05bb5356a26be9ff4135`.
Python 3.15.0, pandas 3.0.6, scikit-learn 1.9.1.

Reproduce from the repository root:

```powershell
.\.venv\Scripts\python.exe -m src.parking_analysis
.\.venv\Scripts\python.exe scripts/execute_parking_notebook.py
```

The walkthrough is [11_parking_patterns.ipynb](../notebooks/11_parking_patterns.ipynb).
Generated CSVs and PNGs stay local in `results/issue11/`; this document preserves
compact results for review. Regenerate and update this snapshot if inputs change.
The notebook was successfully rerun on October 27. The earlier local pandas
Application Control import failure did not recur; no policy was changed.
Dataset review with Dylan remains pending.


## Data and evaluation design

76,102 readings; 86 facilities. No further rows
were removed. Each row, rather than each parking space, receives equal weight.
The latest 20% of unique survey dates (rounded up) is test;
this rule was selected before fitting. Dates never cross the split.

- Train: 2018-06-18 to 2025-10-07,
  59,979 readings, 136 dates,
  83 facilities.
- Test: 2025-10-08 to 2026-10-09,
  16,123 readings, 34 dates,
  68 facilities.
- Test facilities absent from training: ['P671', 'Triton', 'P031'];
  288 readings.

Historical averages first match facility/category/subtype/level, weekday, time,
and quarter; then back off to parking group + time, parking group alone, and the
training-wide mean. Fallback counts: {'level_1': 10249, 'global': 4458, 'level_2': 1416}.
Restrictions are retained; pooled/global fallback is a prediction of availability,
not a claim of permit eligibility. Empty subtype/level means unspecified.

Regression uses one-hot indicators for facility, category, subtype, level, weekday, observation_time, quarter.
All averages, encoders and regression coefficients are fitted on training only.
Unknown categories have zero indicators. Open counts, capacity, target, quality
flags, source identifiers and capacity decisions are excluded from predictors.
This is an additive ordinary least-squares benchmark, without tuning.

## Results

Primary predictions are clipped to [0, 1] for both methods. Raw regression errors
and out-of-range rates are also reported. MAE is in percentage points (pp): a
10 pp error means, for example, predicting 30% available when 20% were available.
Near full means actual fraction available <= 10%; its
overprediction metric is the mean positive excess in predicted availability,
including zero for near-full cases without overprediction.

| method | test_readings | mae_pp | raw_mae_pp | near_full_readings | near_full_mae_pp | near_full_overprediction_pp | out_of_range_count | out_of_range_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| historical_average | 16123.0 | 26.3821 | 26.3821 | 3650.0 | 16.3136 | 15.9004 | 0.0 | 0.0 |
| linear_regression | 16123.0 | 25.76 | 25.9945 | 3650.0 | 18.3358 | 17.9737 | 833.0 | 5.1665 |

Regression improves
on the baseline overall on this holdout: baseline 26.38 pp versus
regression 25.76 pp, a baseline-minus-regression difference of
0.62 pp. This single split is not evidence of
performance in every quarter or at every facility. See facility_errors.csv.
Near-full MAE is 16.31 pp for historical averages versus
18.34 pp for regression. Overall improvement must not be read as
improvement under near-full conditions; review both rows before choosing a model.

## Exploratory findings

- Highest mean availability among the 15 most-observed facilities:
  Torrey Pines Center South (52.3%).
- Highest aggregate survey-time mean: 08:00
  (50.8%).
- Highest aggregate quarter mean: 2026-2027
  Summer (50.5%).
- Facilities with fewer than 100 readings: ['P752', 'P671', 'P031'].
  This threshold is a descriptive review flag; those readings remain included.
- eda_coverage.csv reports dates, quarters, counts and standard deviations for
  every facility. The five highest standard deviations are at ['P106', 'P416', 'Torrey Pines Center North', 'P401', 'P706'].
  High variation can reflect changing category/time composition,
  capacity or actual demand; it does not by itself establish inconsistent data.

Charts: facility_category.png, weekday_time.png and quarters.png. EDA uses the
whole historical dataset descriptively; it does not tune the holdout models.
Category comparisons are descriptive and do not establish permit eligibility.

## Example predictions

One earliest test reading per facility, first ten facilities alphabetically;
not selected by error. Fractions below are on a 0-1 scale.

| record_id | facility | observation_date | fraction_available | historical_average | linear_regression |
| --- | --- | --- | --- | --- | --- |
| QPASS 2025-2026-2 Fall.xlsm\|QPASS Data Entry (Week 2)\|303\|2025-10-08\|open_10am | 8980 | 2025-10-08 00:00:00 | 0.8235 | 0.5 | 0.5548 |
| QPASS 2025-2026-2 Fall.xlsm\|QPASS Data Entry (Week 2)\|308\|2025-10-08\|open_10am | Athena | 2025-10-08 00:00:00 | 0.8502 | 0.3347 | 0.2457 |
| QPASS 2025-2026-2 Fall.xlsm\|QPASS Data Entry (Week 2)\|313\|2025-10-08\|open_10am | Campus Point East | 2025-10-08 00:00:00 | 0.3829 | 0.2788 | 0.118 |
| QPASS 2025-2026-4 Spring.xlsm\|Data Entry\|20\|2026-03-30\|open_10am | Campus Point West | 2026-03-30 00:00:00 | 0.8571 | 0.3889 | 0.1588 |
| QPASS 2025-2026-2 Fall.xlsm\|QPASS Data Entry (Week 2)\|358\|2025-10-08\|open_10am | Gilman | 2025-10-08 00:00:00 | 0.2397 | 0.155 | 0.2078 |
| QPASS 2025-2026-2 Fall.xlsm\|QPASS Data Entry (Week 2)\|330\|2025-10-08\|open_10am | Hopkins | 2025-10-08 00:00:00 | 0.3193 | 0.3005 | 0.3696 |
| QPASS 2025-2026-2 Fall.xlsm\|QPASS Data Entry (Week 2)\|343\|2025-10-08\|open_10am | Mesa Canyon | 2025-10-08 00:00:00 | 0.2544 | 0.0 | 0.0 |
| QPASS 2025-2026-4 Spring.xlsm\|Data Entry\|37\|2026-03-30\|open_10am | P002 | 2026-03-30 00:00:00 | 0.3871 | 0.5968 | 0.4445 |
| QPASS 2025-2026-4 Spring.xlsm\|Data Entry\|38\|2026-03-30\|open_10am | P003 | 2026-03-30 00:00:00 | 0.3438 | 0.4062 | 0.285 |
| QPASS 2025-2026-4 Spring.xlsm\|Data Entry\|39\|2026-03-30\|open_10am | P006 | 2026-03-30 00:00:00 | 0.0 | 0.3333 | 0.1876 |

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
