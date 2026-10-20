"""Regressions for the reviewed QPASS-first and same-quarter fallback policy."""

import pandas as pd
import pytest

from src.capacity_acceptance import apply_capacity_acceptance


def row(**changes):
    record = dict(academic_year="2025-2026", quarter="Fall", facility="P100",
                  category="B", qpass_subtype="", qpass_level_raw="",
                  qpass_capacity_raw=28, open_spaces_raw=12,
                  observation_date="2025-09-29", exclusion_reason="",
                  candidate_capacity=28, inventory_group_count=1,
                  inventory_single_capacity_status="positive_unverified",
                  inventory_scope_compatible=True, _merge="both")
    return {**record, **changes}


def select(*rows):
    return apply_capacity_acceptance(pd.DataFrame(rows))


def test_valid_qpass_has_priority_without_same_day_requirement():
    result = select(row(observation_date="2025-10-10"))
    assert result.iloc[0].selected_capacity == 28
    assert result.iloc[0].capacity_source == "qpass"
    assert result.iloc[0].capacity_assumption == ""


def test_valid_qpass_does_not_require_inventory():
    result = select(row(_merge="left_only", inventory_group_count=0,
                        inventory_scope_compatible=False, candidate_capacity=None))
    assert result.iloc[0].selected_capacity == 28


@pytest.mark.parametrize("value", [None, "", "bad", -1, 2.5, float("inf")])
def test_missing_or_demonstrably_invalid_capacity_can_use_inventory(value):
    result = select(row(qpass_capacity_raw=value))
    assert result.iloc[0].selected_capacity == 28
    assert result.iloc[0].capacity_source == "inventory_same_quarter"
    assert result.iloc[0].capacity_acceptance_reason == "assumed_same_quarter_capacity"
    assert result.iloc[0].capacity_assumption
    assert result.iloc[0].qpass_capacity_raw == value or pd.isna(value)


def test_zero_is_not_proof_of_a_formula_error():
    assert select(row(qpass_capacity_raw=0)).selected_capacity.isna().all()
    fixed = select(row(qpass_capacity_raw=0, qpass_formula_error=True))
    assert fixed.iloc[0].selected_capacity == 28
    assert fixed.iloc[0].qpass_capacity_raw == 0


@pytest.mark.parametrize("changes", [
    dict(inventory_group_count=2), dict(candidate_capacity=0),
    dict(candidate_capacity=-1), dict(candidate_capacity=2.5),
    dict(inventory_scope_compatible=False), dict(_merge="left_only"),
    dict(inventory_single_capacity_status="period_metadata_review"),
    dict(inventory_single_capacity_status="closure_review"),
    dict(inventory_single_capacity_status="multiple_totals_review"),
])
def test_unsafe_inventory_never_fills_missing_qpass(changes):
    assert select(row(qpass_capacity_raw=None, **changes)).selected_capacity.isna().all()


def test_sources_disagree_and_qpass_is_not_overwritten():
    result = select(row(qpass_capacity_raw=30))
    assert result.selected_capacity.isna().all()
    assert result.iloc[0].qpass_capacity_raw == 30
    assert result.iloc[0].candidate_capacity == 28


def test_whole_structure_total_is_not_evidence_against_valid_level_capacity():
    result = select(row(qpass_level_raw="Level 1", candidate_capacity=100,
                        inventory_scope_compatible=False))
    assert result.iloc[0].selected_capacity == 28
    assert result.iloc[0].capacity_source == "qpass"
    assert select(row(qpass_level_raw="Level 1", qpass_capacity_raw=None,
                      inventory_scope_compatible=False)).selected_capacity.isna().all()


def test_missing_morning_reading_does_not_block_later_valid_slots():
    result = select(row(open_spaces_raw=None, exclusion_reason="missing_open_spaces"), row())
    assert pd.isna(result.iloc[0].selected_capacity)
    assert result.iloc[1].selected_capacity == 28
    assert not result.group_capacity_conflict.any()


def test_invalid_reading_is_excluded_from_conflict_calculation():
    result = select(row(open_spaces_raw=-1, qpass_capacity_raw=40,
                        exclusion_reason="invalid_open_spaces"), row())
    assert result.iloc[1].selected_capacity == 28


def test_real_capacity_disagreement_blocks_other_valid_slots():
    assert select(row(), row(qpass_capacity_raw=30)).selected_capacity.isna().all()


def test_conflicts_do_not_cross_date_level_or_subtype():
    result = select(row(), row(qpass_capacity_raw=30, observation_date="2025-09-30"),
                    row(qpass_capacity_raw=30, qpass_level_raw="Level 2"),
                    row(qpass_capacity_raw=30, qpass_subtype="Restricted"))
    assert result.iloc[0].selected_capacity == 28


@pytest.mark.parametrize("field", ["facility", "category"])
@pytest.mark.parametrize("value", [None, float("nan"), "nan", "", "  ", "0", "0.0"])
def test_missing_identifiers_never_accepted(field, value):
    assert select(row(**{field: value})).selected_capacity.isna().all()


def test_source_scope_and_unresolved_labels_block_qpass():
    for changes in (dict(qpass_scope_issue=True), dict(label_unresolved=True),
                    dict(qpass_formula_error=True, inventory_scope_compatible=False)):
        assert select(row(**changes)).selected_capacity.isna().all()


def test_empty_input_returns_auditable_schema():
    result = apply_capacity_acceptance(pd.DataFrame())
    assert result.empty
    assert {"selected_capacity", "capacity_source", "capacity_assumption"} <= set(result)


@pytest.mark.parametrize("date", ["1900-01-01", "2024-10-01", "bad", None])
@pytest.mark.parametrize("reported", [None, 28])
def test_period_conflicts_block_both_sources(date, reported):
    result = select(row(observation_date=date, qpass_capacity_raw=reported))
    assert result.selected_capacity.isna().all()
    assert result.qpass_period_metadata_conflict.all()
    assert result.iloc[0].capacity_acceptance_reason == "qpass_period_metadata_conflict"


@pytest.mark.parametrize("quarter,date", [
    ("Summer", "2025-07-01"), ("Fall", "2025-10-01"),
    ("Winter", "2026-01-01"), ("Spring", "2026-04-01"),
])
def test_quarter_calendar_years_without_exact_inventory_date(quarter, date):
    result = select(row(quarter=quarter, observation_date=date, qpass_capacity_raw=None))
    assert result.iloc[0].capacity_source == "inventory_same_quarter"
    assert not result.qpass_period_metadata_conflict.any()


@pytest.mark.parametrize("changes", [
    dict(academic_year="2025-2027"), dict(academic_year="bad"),
    dict(quarter="Unknown"), dict(quarter="Winter", observation_date="2025-01-01"),
])
def test_invalid_period_labels_are_flagged(changes):
    result = select(row(**changes))
    assert result.qpass_period_metadata_conflict.all()
    assert result.selected_capacity.isna().all()
