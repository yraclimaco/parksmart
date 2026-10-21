"""Tests for the integrated pipeline: joins, inclusion rules, and exports."""

from pathlib import Path

import pandas as pd
import pytest

from src.build_dataset import (
    QUALITY_FLAG_BLOCKS, decide_inclusion, join_capacity, run_pipeline, summarize,
)
from src.qpass_observations import validate_observations
from tests.test_capacity_integration import write_inventory, write_qpass

REAL_OUTPUT = Path("data/processed/pipeline")


def run_generated(tmp_path, rows):
    """Run the full pipeline on one generated Fall 2024 QPASS workbook."""
    qpass_dir = tmp_path / "QPASS"
    qpass_dir.mkdir(parents=True)
    qpass_path = qpass_dir / "QPASS 2024-2025-2 Fall.xlsx"
    write_qpass(qpass_path, rows)
    inventory = tmp_path / "Inventory 2024-2025-2 Fall.xlsx"
    write_inventory(inventory)
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame([dict(academic_year="2024-2025", quarter="Fall",
                       qpass_file=qpass_path.name, inventory_path=str(inventory),
                       download_status="already_present", reason="")]
                 ).to_csv(manifest, index=False)
    output = tmp_path / "out"
    analysis, audit = run_pipeline(qpass_dir, manifest, tmp_path / "clean",
                                   tmp_path / "capacity", output)
    return analysis, audit, output


def joined_row(**values):
    """Return a one-row joined table that passes every check by default."""
    row = dict(source_file="f.xlsx", sheet_name="Week 1", source_row=3,
               date=pd.Timestamp("2024-09-30"), source_time_column="open_8am",
               selected_capacity="10", quality_flag="pass", capacity_row_found=True,
               exclusion_reason="",
               capacity_acceptance_reason="valid_qpass_exact_group",
               open_spaces=4.0, observation_group=1)
    row.update(values)
    frame = pd.DataFrame([row])
    frame["source_row"] = frame["source_row"].astype("Int64")
    frame["open_spaces"] = frame["open_spaces"].astype("Float64")
    return frame


def test_generated_workbooks_keep_every_record_and_select_valid_rows(tmp_path):
    analysis, audit, output = run_generated(tmp_path, [
        (" Gliderport ", "V", None, [None, 6, 4, 2]),
        ("P100", "B", 20, [10, 9, 8, 7]),
        (None, "B", 12, [1, 1, 1, 1]),
    ])
    assert len(audit) == 12  # 3 loader rows x 4 time slots, none lost or added
    assert audit["record_id"].is_unique
    assert audit["included"].sum() == len(analysis) == 7
    assert audit.loc[~audit["included"], "exclusion_reasons"].ne("").all()
    assert analysis["fraction_available"].between(0, 1).all()
    fallback = analysis[analysis["capacity_source"].eq("inventory_same_quarter")]
    assert fallback["facility_raw"].eq(" Gliderport ").all()
    assert fallback["fraction_available"].tolist() == pytest.approx([0.6, 0.4, 0.2])
    missing = audit[audit["location"].isna()]
    assert missing["exclusion_reasons"].str.contains(
        "invalid_facility_or_category"
    ).all()
    summary = (output / "summary.md").read_text()
    assert "RESULT: 7 usable parking readings (58.3% of 12)." in summary
    assert "- 1  Reading blank or invalid" in summary
    assert "- 4  Facility, category or date missing" in summary
    assert "= 7  usable readings in the analysis dataset" in summary
    assert "## Coverage by facility" in summary
    assert "| P386 | 1 | 3 |" in summary
    for name in ["analysis_dataset.csv", "audit.csv.gz", "summary.md",
                 "exclusion_reasons.csv", "coverage_by_facility_quarter.csv",
                 "loader_audit.json"]:
        assert (output / name).is_file()


def test_exact_repeats_are_counted_once_and_kept_in_audit(tmp_path):
    analysis, audit, _ = run_generated(tmp_path, [
        ("P100", "B", 20, [10, 9, 8, 7]),
        ("P100", "B", 20, [10, 9, 8, 7]),
    ])
    assert len(audit) == 8
    assert len(analysis) == 4
    assert analysis["duplicate_copies"].eq(2).all()
    copies = audit[audit["duplicate_of"].notna()]
    assert len(copies) == 4
    assert copies["exclusion_reasons"].eq("exact_repeat").all()
    assert copies["duplicate_of"].isin(analysis["record_id"]).all()
    removed = summarize(audit, {})["removed"]
    assert removed.to_dict("records") == [{
        "group": "Exact duplicate copy",
        "reason": "exact duplicate copy of a kept reading", "rows": 4,
    }]


def test_rerun_reproduces_identical_outputs(tmp_path):
    rows = [("P100", "B", 20, [10, 9, 8, 7]),
            (" Gliderport ", "V", None, [1, 2, 3, 4])]
    _, _, first = run_generated(tmp_path / "a", rows)
    _, _, second = run_generated(tmp_path / "b", rows)
    for name in ["analysis_dataset.csv", "summary.md"]:
        assert (first / name).read_text() == (second / name).read_text()


def test_every_quality_check_has_an_inclusion_policy():
    columns = ["observation_datetime", "location", "type", "total_stall_count",
               "open_spaces", "sub_type", "level", "raw_total_stall_count",
               "raw_open_spaces", "format_version"]
    empty = pd.DataFrame(columns=columns).astype(
        {"total_stall_count": "Float64", "open_spaces": "Float64"}
    )
    _, summary = validate_observations(empty)
    assert set(summary["check"]) - {"any_check"} == set(QUALITY_FLAG_BLOCKS)


def test_unknown_quality_flag_raises():
    with pytest.raises(ValueError, match="No inclusion policy"):
        decide_inclusion(joined_row(quality_flag="new_check"))


def test_open_spaces_above_selected_capacity_are_excluded_not_clipped():
    result = decide_inclusion(joined_row(open_spaces=12.0))
    assert not result["included"].iloc[0]
    assert result["exclusion_reasons"].iloc[0] == "open_exceeds_selected_capacity"
    assert pd.isna(result["fraction_available"].iloc[0])


def test_capacity_only_flags_do_not_block_but_reading_flags_do():
    capacity_flag = decide_inclusion(joined_row(quality_flag="zero_capacity"))
    assert capacity_flag["included"].iloc[0]
    reading_flag = decide_inclusion(
        joined_row(quality_flag="missing_type|zero_capacity")
    )
    assert reading_flag["exclusion_reasons"].iloc[0] == "quality:missing_type"


def test_unaccepted_capacity_is_excluded_with_reason():
    result = decide_inclusion(joined_row(
        selected_capacity="", capacity_acceptance_reason="source_capacity_conflict",
    ))
    assert result["exclusion_reasons"].iloc[0] == (
        "capacity_unresolved:source_capacity_conflict"
    )


def test_repeats_with_different_selected_capacity_are_all_excluded():
    frame = pd.concat([joined_row(), joined_row(source_row=4, selected_capacity="11")],
                      ignore_index=True)
    result = decide_inclusion(frame)
    assert not result["included"].any()
    assert result["exclusion_reasons"].eq("duplicate_capacity_disagreement").all()


def key_frames(capacity_rows=1, observation_rows=1):
    """Return minimal audited and capacity tables sharing source keys."""
    audited = pd.DataFrame({
        "source_file": "f.xlsx", "sheet_name": "Week 1",
        "source_row": range(3, 3 + observation_rows),
        "date": pd.Timestamp("2024-09-30"), "source_time_column": "open_8am",
        "academic_year": "2024-2025", "quarter": "Fall",
    })
    capacity = pd.DataFrame({
        "qpass_source_file": "f.xlsx", "qpass_source_sheet": "Week 1",
        "qpass_source_row": [str(r) for r in range(3, 3 + capacity_rows)],
        "observation_date": "2024-09-30", "observation_time": "8am",
        "academic_year": "2024-2025", "quarter": "Fall", "selected_capacity": "10",
    })
    return audited, capacity


def test_join_keeps_observations_missing_from_capacity_manifest():
    audited, capacity = key_frames(capacity_rows=1, observation_rows=2)
    joined = join_capacity(audited, capacity)
    assert len(joined) == 2
    assert joined["capacity_row_found"].tolist() == [True, False]


def test_join_rejects_capacity_rows_without_observation():
    audited, capacity = key_frames(capacity_rows=2, observation_rows=1)
    with pytest.raises(ValueError, match="match no observation"):
        join_capacity(audited, capacity)


def test_join_rejects_duplicate_keys():
    audited, capacity = key_frames()
    with pytest.raises(ValueError, match="not unique"):
        join_capacity(pd.concat([audited, audited]), capacity)


def test_join_rejects_incomplete_keys():
    audited, capacity = key_frames()
    audited["date"] = pd.NaT
    with pytest.raises(ValueError, match="incomplete source keys"):
        join_capacity(audited, capacity)


def test_observation_outside_capacity_manifest_is_excluded():
    result = decide_inclusion(joined_row(capacity_row_found=False,
                                         selected_capacity=""))
    assert result["exclusion_reasons"].iloc[0] == "capacity:not_in_capacity_manifest"


def test_join_rejects_period_disagreement():
    audited, capacity = key_frames()
    capacity["quarter"] = "Winter"
    with pytest.raises(ValueError, match="quarter disagrees"):
        join_capacity(audited, capacity)


@pytest.mark.skipif(not (REAL_OUTPUT / "audit.csv.gz").is_file(),
                    reason="Run python -m src.build_dataset on the real workbooks")
def test_real_pipeline_outputs_are_consistent():
    audit = pd.read_csv(REAL_OUTPUT / "audit.csv.gz", dtype=str, keep_default_na=False)
    analysis = pd.read_csv(REAL_OUTPUT / "analysis_dataset.csv", dtype=str,
                           keep_default_na=False)
    assert audit["record_id"].is_unique
    assert audit["included"].eq("True").sum() == len(analysis)
    assert analysis["record_id"].isin(audit["record_id"]).all()
    excluded = audit[audit["included"].eq("False")]
    assert excluded["exclusion_reasons"].ne("").all()
    fraction = pd.to_numeric(analysis["fraction_available"])
    assert fraction.between(0, 1).all()
    assert pd.to_numeric(analysis["selected_capacity"]).gt(0).all()
