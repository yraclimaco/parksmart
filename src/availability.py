"""Attach historical availability estimates to current parking groups.

For one request this picks the survey time and quarter that match the arrival,
predicts each group, and keeps the basis of every estimate so ranking can say
when an estimate is limited (a different survey time, or a broader fallback
average). Estimates describe past survey conditions, never live availability.

Prediction contract (any model can be plugged in; Issue #18 improves on the
default Issue #11 HistoricalAverage):

- ``predict(features)`` takes a DataFrame with facility, category, subtype,
  level, weekday (e.g. "Tuesday"), observation_time ("HH:MM", a survey time)
  and quarter ("Fall"..."Summer", or "" outside a quarter).
- It returns a DataFrame indexed like ``features`` with ``prediction`` (an
  available fraction from 0 to 1, or NaN when the request is unsupported) and
  ``baseline_group`` (a basis label; see ``basis_descriptions``).
- ``fit(records)`` is only needed if the estimator fits the model itself; a
  model loaded from a saved artifact can be passed already fitted.
"""

import pandas as pd

from .eligibility import clock, to_ucsd_time
from .parking_benchmarks import HistoricalAverage
from .ucsd_calendar import quarter_for

# HistoricalAverage.predict labels: level_1 matches group + weekday + survey
# time + quarter; later levels pool more data (see BASELINE_LEVELS). None means
# a full match, which needs no label.
FULL_MATCH = "level_1"
BASIS_DESCRIPTIONS = {
    FULL_MATCH: None,
    "level_2": "same time, any weekday or quarter",
    "level_3": "all-day average for these stalls",
    "global": "campus-wide average; no history for these stalls",
    "model": None,  # Regression type is not itself a coverage limitation.
}
# Bases that ignore the time of day, so naming the survey time would mislead.
ALL_DAY_BASES = {"level_3", "global"}


class AvailabilityEstimator:
    """Availability estimates for a requested arrival time.

    Default use: ``AvailabilityEstimator().fit(records)`` once at startup, then
    ``attach(groups, arrival)`` per request. With a model loaded from a saved
    artifact: ``AvailabilityEstimator(model, survey_times=[...])``, no fit.

    Args:
        model: object following the prediction contract (module docstring);
            defaults to an unfitted HistoricalAverage.
        survey_times: "HH:MM" survey times the model was trained on; set by
            ``fit`` when omitted.
        basis_descriptions: basis label -> note text (None = full match).
            Labels not listed are described as "fallback estimate (<label>)".
    """

    def __init__(self, model=None, survey_times=None, basis_descriptions=None):
        self.model = model if model is not None else HistoricalAverage()
        self.survey_times = sorted(survey_times) if survey_times else None
        self.basis_descriptions = (BASIS_DESCRIPTIONS if basis_descriptions
                                   is None else basis_descriptions)

    def fit(self, records):
        """Fit the model on prepared analysis records; return self.

        Args:
            records: output of ``src.parking_benchmarks.load_analysis_dataset``.
        Returns:
            self, with ``survey_times`` (sorted "HH:MM" strings in the data).
        """
        self.model.fit(records)
        self.survey_times = sorted(records["observation_time"].unique())
        return self

    def survey_time_for(self, arrival):
        """Return the nearest survey time ("HH:MM"); ties go to the earlier one."""
        minutes = arrival.hour * 60 + arrival.minute
        return min(self.survey_times,
                   key=lambda time: abs(_minutes(time) - minutes))

    def attach(self, groups, arrival):
        """Return a copy of ``groups`` with estimate columns added.

        Args:
            groups: DataFrame with facility, category, subtype and level
                (e.g. from ``src.location_registry.current_groups``).
            arrival: datetime; naive values are UCSD local time, aware
                values are converted to it.
        Returns:
            Copy with ``estimated_available_fraction``, ``estimate_basis``
            (HistoricalAverage level), ``estimate_survey_time``,
            ``estimate_quarter`` (None outside a verified quarter) and
            ``estimate_note`` (None for a full match at the requested time,
            otherwise a short plain-language limitation).
        """
        if not self.survey_times:
            raise ValueError("Estimator is not ready: call fit(records) or "
                             "pass a fitted model with survey_times")
        arrival = to_ucsd_time(arrival)
        survey_time = self.survey_time_for(arrival)
        quarter = quarter_for(arrival.date())
        features = groups.copy()
        for column in ("subtype", "level"):
            features[column] = features[column].fillna("").astype(str)
        features["weekday"] = arrival.strftime("%A")
        features["observation_time"] = survey_time
        features["quarter"] = quarter if quarter else ""
        prediction = self.model.predict(features)

        result = groups.copy()
        result["estimated_available_fraction"] = prediction["prediction"].to_numpy()
        result["estimate_basis"] = prediction["baseline_group"].to_numpy()
        result["estimate_survey_time"] = survey_time
        result["estimate_quarter"] = quarter
        # Unsupported (NaN) rows get no note: ranking reports them as missing.
        result["estimate_note"] = [
            None if pd.isna(value) else self.note(basis, survey_time, arrival)
            for value, basis in prediction[["prediction", "baseline_group"]]
            .itertuples(index=False)
        ]
        return result

    def note(self, basis, survey_time, arrival):
        """Describe how an estimate differs from a full match at ``arrival``.

        Returns:
            None for a full match at the requested time, otherwise text such
            as "2:00 PM surveys; none cover 10:00 PM".
        """
        parts = []
        minutes = arrival.hour * 60 + arrival.minute
        first, last = (_minutes(time) for time in
                       (self.survey_times[0], self.survey_times[-1]))
        if basis not in ALL_DAY_BASES and _minutes(survey_time) != minutes:
            parts.append(f"{clock(survey_time)} surveys")
        if not first <= minutes <= last:
            parts.append(f"none cover {clock(arrival)}")
        if basis in self.basis_descriptions:
            if self.basis_descriptions[basis]:
                parts.append(self.basis_descriptions[basis])
        else:
            parts.append(f"fallback estimate ({basis})")
        return "; ".join(parts) or None


def _minutes(time_text):
    hour, minute = time_text.split(":")
    return int(hour) * 60 + int(minute)

