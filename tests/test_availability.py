"""Tests for request-time availability estimates and their basis labels."""

from datetime import datetime

import pandas as pd
import pytest

from src.availability import AvailabilityEstimator
from src.eligibility import clock

TUESDAY = datetime(2026, 10, 27)  # Fall 2026 quarter


def _records():
    """Prepared-style readings: one Gilman A group on Tuesdays in Fall."""
    rows = []
    for time, fraction in (("08:00", 0.9), ("10:00", 0.5), ("14:00", 0.2)):
        rows.append({"facility": "Gilman", "category": "A", "subtype": "",
                     "level": "", "weekday": "Tuesday",
                     "observation_time": time, "quarter": "Fall",
                     "fraction_available": fraction})
    rows.append({"facility": "Hopkins", "category": "S", "subtype": "",
                 "level": "", "weekday": "Monday", "observation_time": "10:00",
                 "quarter": "Winter", "fraction_available": 0.4})
    return pd.DataFrame(rows)


def _groups(*facilities):
    names = {"Gilman": "A", "Hopkins": "S", "Pangea": "B"}
    return pd.DataFrame([{"location_id": f.lower(), "facility": f,
                          "category": names[f], "subtype": None, "level": None}
                         for f in facilities])


@pytest.fixture
def estimator():
    return AvailabilityEstimator().fit(_records())


def test_full_match_at_a_survey_time_has_no_note(estimator):
    result = estimator.attach(_groups("Gilman"), TUESDAY.replace(hour=10))
    row = result.iloc[0]
    assert row.estimated_available_fraction == pytest.approx(0.5)
    assert row.estimate_basis == "level_1"
    assert row.estimate_survey_time == "10:00"
    assert row.estimate_quarter == "Fall"
    assert row.estimate_note is None


def test_between_surveys_snaps_to_nearest_and_says_so(estimator):
    row = estimator.attach(_groups("Gilman"), TUESDAY.replace(hour=9)).iloc[0]
    assert row.estimate_survey_time == "08:00"   # tie goes earlier
    assert row.estimated_available_fraction == pytest.approx(0.9)
    assert row.estimate_note == "8:00 AM surveys"


def test_night_request_is_labeled_as_outside_survey_hours(estimator):
    row = estimator.attach(_groups("Gilman"), TUESDAY.replace(hour=22)).iloc[0]
    assert row.estimate_survey_time == "14:00"
    assert row.estimate_note == "2:00 PM surveys; none cover 10:00 PM"


def test_fallback_levels_are_labeled(estimator):
    result = estimator.attach(_groups("Hopkins", "Pangea"),
                              TUESDAY.replace(hour=10)).set_index("facility")
    # Hopkins was surveyed at 10:00 but on another weekday and quarter.
    assert result.loc["Hopkins", "estimate_basis"] == "level_2"
    assert result.loc["Hopkins", "estimate_note"] == (
        "same time, any weekday or quarter")
    # Pangea has no history at all: campus-wide mean.
    assert result.loc["Pangea", "estimate_basis"] == "global"
    assert "no history" in result.loc["Pangea", "estimate_note"]


def test_break_between_quarters_has_no_quarter(estimator):
    winter_break = datetime(2026, 12, 22, 10)
    row = estimator.attach(_groups("Gilman"), winter_break).iloc[0]
    assert row.estimate_quarter is None
    assert row.estimate_basis != "level_1"
    assert row.estimate_note is not None


def test_input_groups_are_not_modified(estimator):
    groups = _groups("Gilman")
    estimator.attach(groups, TUESDAY.replace(hour=10))
    assert "estimated_available_fraction" not in groups


def test_clock_formats_strings_and_datetimes():
    assert clock("08:00") == "8:00 AM"
    assert clock("14:30") == "2:30 PM"
    assert clock(datetime(2026, 1, 1, 0, 5)) == "12:05 AM"


class _StubModel:
    """A pre-fitted model following the prediction contract (no fit method)."""

    def predict(self, features):
        supported = features["facility"].eq("Gilman")
        return pd.DataFrame({
            "prediction": supported.map({True: 0.7, False: float("nan")}),
            "baseline_group": supported.map({True: "model", False: "unsupported"}),
        }, index=features.index)


def test_prefitted_model_plugs_in_without_fit():
    estimator = AvailabilityEstimator(_StubModel(), survey_times=["10:00", "08:00"],
                                      basis_descriptions={"model": None})
    result = estimator.attach(_groups("Gilman", "Pangea"),
                              TUESDAY.replace(hour=10)).set_index("facility")
    assert result.loc["Gilman", "estimated_available_fraction"] == 0.7
    assert result.loc["Gilman", "estimate_note"] is None
    # Unsupported requests stay NaN (never filled) and carry no note.
    assert pd.isna(result.loc["Pangea", "estimated_available_fraction"])
    assert result.loc["Pangea", "estimate_note"] is None


def test_unknown_basis_labels_are_named_as_fallbacks():
    estimator = AvailabilityEstimator(_StubModel(), survey_times=["10:00"],
                                      basis_descriptions={})
    row = estimator.attach(_groups("Gilman"), TUESDAY.replace(hour=10)).iloc[0]
    assert row.estimate_note == "fallback estimate (model)"


def test_unsupported_predictions_lead_to_predictions_unavailable():
    from src.ranking import PREDICTIONS_UNAVAILABLE, recommend

    location = {"location_id": "pangea", "name": "Pangea", "kind": "structure",
                "dataset_facilities": ["Pangea"], "coordinates": None,
                "coordinate_status": "missing", "coordinate_source": None,
                "coordinate_verified_on": None, "registry_status": "supported",
                "access_note": None, "notes": None}
    estimator = AvailabilityEstimator(_StubModel(), survey_times=["10:00"])
    groups = estimator.attach(_groups("Pangea"), TUESDAY.replace(hour=10))
    result = recommend(groups, [location], "B", TUESDAY.replace(hour=10))
    assert result.status == PREDICTIONS_UNAVAILABLE


def test_attach_before_fit_explains_what_is_missing():
    with pytest.raises(ValueError, match="not ready"):
        AvailabilityEstimator().attach(_groups("Gilman"), TUESDAY)


def test_aware_arrivals_are_converted_to_ucsd_time(estimator):
    # 17:00 UTC on Oct 27 is 10:00 AM in San Diego (PDT).
    from datetime import timezone

    arrival = datetime(2026, 10, 27, 17, tzinfo=timezone.utc)
    row = estimator.attach(_groups("Gilman"), arrival).iloc[0]
    assert row.estimate_survey_time == "10:00"
    assert row.estimate_note is None
