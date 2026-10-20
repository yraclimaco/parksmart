"""Checks for reported-total comparisons and conservative matching."""

import pandas as pd
import pytest

from src import compare_capacities as matching


@pytest.mark.parametrize(
    "reported,capacity,groups,merge,expected,difference",
    [
        (25, 25, 1, "both", "agree_unverified", 0),
        (30, 25, 1, "both", "conflict", 5),
        (20, 25, 1, "both", "conflict", -5),
        ("25", 25, 1, "both", "agree_unverified", 0),
        (0, 25, 1, "both", "not_comparable", None),
        (None, 25, 1, "both", "not_comparable", None),
        ("", 25, 1, "both", "not_comparable", None),
        ("n/a", 25, 1, "both", "not_comparable", None),
        (-1, 25, 1, "both", "not_comparable", None),
        (2.5, 25, 1, "both", "not_comparable", None),
        (float("inf"), 25, 1, "both", "not_comparable", None),
        (25, 0, 1, "both", "not_comparable", None),
        (25, -1, 1, "both", "not_comparable", None),
        (25, None, 2, "both", "not_comparable", None),
        (25, 25, 2, "both", "not_comparable", None),
        (25, 25, 1, "left_only", "not_comparable", None),
    ],
)
def test_reported_totals(reported, capacity, groups, merge, expected, difference):
    frame = pd.DataFrame([{
        "qpass_capacity_raw": reported,
        "candidate_capacity": capacity,
        "inventory_group_count": groups,
        "_merge": merge,
    }])
    audited = matching.audit_reported_capacities(frame)
    assert audited.loc[0, "reported_capacity_comparison"] == expected
    if difference is None:
        assert pd.isna(audited.loc[0, "capacity_difference"])
    else:
        assert audited.loc[0, "capacity_difference"] == difference
    assert "reported_capacity_comparison" not in frame


def test_audit_reports_preserve_raw_values_and_uncertainty(tmp_path, monkeypatch):
    inventory_path = tmp_path / "inventory.csv"
    pd.DataFrame([
        {"academic_year": "2025-2026", "quarter": "Summer",
         "facility_raw": " P1 ", "category_raw": category,
         "capacity": capacity, "capacity_status": "positive_unverified",
         "capacity_raw_values": str([capacity]), "source_file": "inventory.xlsm",
         "source_rows": str(index)}
        for index, (category, capacity) in enumerate(
            [(" A ", 25), ("B", 10), ("B", 15)], start=5
        )
    ]).to_csv(inventory_path, index=False)

    base = {
        "academic_year": "2025-2026", "quarter": "Summer",
        "location": "P1  ", "type": "A  ", "sub_type": None,
        "level": None, "date": "2025-07-01", "total_stall_count": 25,
        "source_file": "qpass.xlsm", "sheet_name": "Survey", "source_row": 5,
        "open_8am": 5, "open_10am": 5, "open_12pm": 5, "open_2pm": 5,
    }
    rows = [
        base,
        {**base, "total_stall_count": 30, "source_row": 6},
        {**base, "total_stall_count": 0, "source_row": 7},
        {**base, "quarter": "Fall", "source_row": 8},
        {**base, "type": "B", "source_row": 9},
        {**base, "open_8am": "n/a", "open_10am": "", "source_row": 10},
    ]
    monkeypatch.setattr(matching, "load_qpass", lambda _: pd.DataFrame(rows))
    output = tmp_path / "reports"
    matching.compare_capacities(inventory_path, tmp_path / "qpass.xlsm", output)
    results = pd.read_csv(output / "capacity_comparison.csv", keep_default_na=False)

    assert len(results) == 24
    # The wrong-quarter Inventory cannot contradict that row's own QPASS total.
    assert results.loc[results.quarter.eq("Fall"), "selected_capacity"].eq("25").all()
    assert results.loc[results.quarter.eq("Summer"), "selected_capacity"].eq("").all()
    assert results["qpass_facility_raw"].eq("P1  ").all()
    assert results["facility"].eq("P1").all()
    assert results.loc[0, "qpass_category_raw"] == "A  "
    assert results.loc[0, "category"] == "A"
    assert " P1 " in results.loc[0, "inventory_facility_raw_values"]
    assert results["reported_capacity_comparison"].eq("conflict").sum() == 4
    zero = results.loc[results["qpass_source_row"].eq(7)]
    assert zero["qpass_capacity_status"].eq("zero_review").all()
    assert zero["reported_capacity_comparison"].eq("not_comparable").all()
    wrong_quarter = results.loc[results["qpass_source_row"].eq(8)]
    assert wrong_quarter["comparison_status"].eq("accepted_qpass").all()
    ambiguous = results.loc[results["qpass_source_row"].eq(9)]
    assert ambiguous["comparison_status"].eq("subtype_mapping_required").all()
    assert ambiguous["candidate_capacity"].eq("").all()
    assert results["exclusion_reason"].eq("invalid_open_spaces").sum() == 1
    assert results["exclusion_reason"].eq("missing_open_spaces").sum() == 1

    assert len(pd.read_csv(output / "unmatched_records.csv")) == 4
    conflicts = pd.read_csv(output / "conflicting_records.csv")
    assert len(conflicts) == 14  # Eligible slots affected by the group disagreement.
    direct_conflicts = conflicts.loc[conflicts.reported_capacity_comparison.eq("conflict")]
    assert len(direct_conflicts) == 4
    assert direct_conflicts["capacity_difference"].eq(5).all()
    assert len(pd.read_csv(output / "unresolved_cases.csv")) == 20
    overall = pd.read_csv(output / "overall_summary.csv").iloc[0]
    assert overall["eligible_observation_slots"] == 22
    assert overall["excluded_observation_slots"] == 2
    assert overall["exact_key_candidates"] == 18
    assert overall["accepted_capacity_matches"] == 4
    assert overall["exact_key_candidate_rate"] == pytest.approx(18 / 22)
    quarters = pd.read_csv(output / "quarter_summary.csv")
    assert set(quarters["quarter"]) == {"Summer", "Fall"}
    assert quarters["eligible_observation_slots"].sum() == 22
