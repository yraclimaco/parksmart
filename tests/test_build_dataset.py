"""Tests for the integrated pipeline: joins, inclusion rules, and exports."""

import datetime as dt
import gzip
import json
import os
import shutil
from pathlib import Path

import pandas as pd
import pytest

from src.build_dataset import (
    QUALITY_FLAG_BLOCKS,
    decide_inclusion,
    join_capacity,
    load_observations,
    run_pipeline,
    summarize,
    validate_outputs,
)
from src.qpass_loader import RAW_QPASS_DIR
from src.qpass_observations import validate_observations
from tests.test_capacity_integration import write_inventory, write_qpass

# Real-data checks read this folder; point it at any --output-dir to check it.
REAL_OUTPUT = Path(os.environ.get("PARKSMART_PIPELINE_DIR", "data/processed/pipeline"))
OUTPUT_FILES = ["analysis_dataset.csv", "audit.csv.gz", "summary.md",
                "exclusion_reasons.csv", "coverage_by_facility_quarter.csv",
                "loader_audit.json"]
EXCLUDED_NAME = "QPASS 2025-2026-3 Winter.xlsx"


def run_generated(tmp_path, rows, excluded_rows=None):
    """Run the full pipeline on a generated Fall 2024 QPASS workbook.

    excluded_rows, when given, also writes a Winter 2025-2026 workbook that is
    listed in the manifest but excluded by name.
    """
    qpass_dir = tmp_path / "QPASS"
    qpass_dir.mkdir(parents=True)
    qpass_path = qpass_dir / "QPASS 2024-2025-2 Fall.xlsx"
    write_qpass(qpass_path, rows)
    inventory = tmp_path / "Inventory 2024-2025-2 Fall.xlsx"
    write_inventory(inventory)
    records = [dict(academic_year="2024-2025", quarter="Fall",
                    qpass_file=qpass_path.name, inventory_path=str(inventory),
                    download_status="already_present", reason="")]
    if excluded_rows is not None:
        write_qpass(qpass_dir / EXCLUDED_NAME, excluded_rows,
                    date=dt.datetime(2026, 1, 5))
        records.append(dict(academic_year="2025-2026", quarter="Winter",
                            qpass_file=EXCLUDED_NAME, inventory_path="",
                            download_status="not_listed_in_archive", reason=""))
    manifest = tmp_path / "manifest.csv"
    pd.DataFrame(records).to_csv(manifest, index=False)
    output = tmp_path / "out"
    analysis, audit = run_pipeline(qpass_dir, manifest, tmp_path / "clean",
                                   tmp_path / "capacity", output,
                                   excluded_files=[EXCLUDED_NAME])
    return analysis, audit, output


def joined_row(**values):
    """Return a one-row joined table that passes every check by default."""
    row = dict(source_file="f.xlsx", sheet_name="Week 1", source_row=3,
               date=pd.Timestamp("2024-09-30"), source_time_column="open_8am",
               selected_capacity="10", quality_flag="pass", capacity_match="matched",
               exclusion_reason="",
               capacity_acceptance_reason="valid_qpass_exact_group",
               open_spaces=4.0, observation_group=1)
    row.update(values)
    frame = pd.DataFrame([row])
    frame["source_row"] = frame["source_row"].astype("Int64")
    frame["open_spaces"] = frame["open_spaces"].astype("Float64")
    frame["date"] = pd.to_datetime(frame["date"])
    return frame


# ---------- end-to-end on generated workbooks ----------

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
    for name in OUTPUT_FILES:
        assert (output / name).is_file()
    assert validate_outputs(output, expected_total=12) == {
        "total": 12, "included": 7, "excluded": 5,
    }


def test_exact_repeats_are_counted_once_and_kept_in_audit(tmp_path):
    analysis, audit, output = run_generated(tmp_path, [
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
    validate_outputs(output, expected_total=8)


def test_excluded_workbook_is_left_out_of_both_sides_and_reported(tmp_path):
    analysis, audit, output = run_generated(
        tmp_path, [("P100", "B", 20, [10, 9, 8, 7])],
        excluded_rows=[("P200", "A", 30, [1, 2, 3, 4])],
    )
    assert len(audit) == 4
    assert not audit["source_file"].eq(EXCLUDED_NAME).any()
    used = pd.read_csv(tmp_path / "capacity" / "inventory_sources_used.csv")
    assert used["qpass_file"].tolist() == ["QPASS 2024-2025-2 Fall.xlsx"]
    loader_audit = json.loads((output / "loader_audit.json").read_text())
    assert loader_audit["excluded_files"] == [EXCLUDED_NAME]
    summary = (output / "summary.md").read_text()
    assert f"Not loaded (team decision): {EXCLUDED_NAME}." in summary
    validate_outputs(output, expected_total=4, excluded_files=[EXCLUDED_NAME])


def test_rerun_reproduces_identical_outputs(tmp_path):
    rows = [("P100", "B", 20, [10, 9, 8, 7]),
            (" Gliderport ", "V", None, [1, 2, 3, 4])]
    _, _, first = run_generated(tmp_path / "a", rows)
    _, _, second = run_generated(tmp_path / "b", rows)
    for name in OUTPUT_FILES:
        assert (first / name).read_bytes() == (second / name).read_bytes(), name
    audits = [gzip.decompress((run / "audit.csv.gz").read_bytes())
              for run in (first, second)]
    assert audits[0] == audits[1]


# ---------- output validation on temporary folders ----------

def tamper(output, tmp_path, name, change):
    """Copy outputs to a new folder and apply change() to one CSV file."""
    copy = tmp_path / "tampered"
    shutil.copytree(output, copy)
    frame = pd.read_csv(copy / name, dtype=str, keep_default_na=False)
    change(frame)
    frame.to_csv(copy / name, index=False)
    return copy


@pytest.fixture
def generated_output(tmp_path):
    """Pipeline outputs with one exact repeat, for validation tests."""
    _, _, output = run_generated(tmp_path / "run", [
        ("P100", "B", 20, [10, 9, 8, 7]),
        ("P100", "B", 20, [10, 9, 8, 7]),
        ("P386", "V", None, [None, 6, 4, 2]),
    ])
    return output


def test_validation_catches_lost_audit_rows(generated_output, tmp_path):
    copy = tamper(generated_output, tmp_path, "audit.csv.gz",
                  lambda frame: frame.drop(frame.index[-1], inplace=True))
    with pytest.raises(ValueError, match="audit has 11 rows; source has 12"):
        validate_outputs(copy, expected_total=12)


def test_validation_catches_invalid_fraction(generated_output, tmp_path):
    def change(frame):
        frame.loc[0, "fraction_available"] = "1.5"
    copy = tamper(generated_output, tmp_path, "analysis_dataset.csv", change)
    with pytest.raises(ValueError, match="fraction_available"):
        validate_outputs(copy)


def test_validation_catches_blocking_flag_on_included_row(generated_output, tmp_path):
    def change(frame):
        first = frame.index[frame["included"].eq("True")][0]
        frame.loc[first, "quality_flag"] = "conflicting_observation"
    copy = tamper(generated_output, tmp_path, "audit.csv.gz", change)
    with pytest.raises(ValueError, match="1 included rows have blocking flags"):
        validate_outputs(copy)


def test_validation_catches_broken_duplicate_link(generated_output, tmp_path):
    def change(frame):
        copies = frame.index[frame["duplicate_of"].ne("")]
        excluded = frame.loc[frame["included"].eq("False")
                             & frame["duplicate_of"].eq(""), "record_id"]
        frame.loc[copies[0], "duplicate_of"] = excluded.iloc[0]
    copy = tamper(generated_output, tmp_path, "audit.csv.gz", change)
    with pytest.raises(ValueError, match="duplicate_of does not point"):
        validate_outputs(copy)


def _set(column, value, where=None):
    """Return a change() that sets one cell, optionally on the first matching row."""
    def change(frame):
        rows = frame.index if where is None else frame.index[where(frame)]
        frame.loc[rows[0], column] = value
    return change


def _included(frame):
    return frame["included"].eq("True")


@pytest.mark.parametrize("name,change,message", [
    ("audit.csv.gz", lambda f: _set("record_id", f.loc[0, "record_id"],
                                    lambda g: g.index == 1)(f),
     "record_id values are not unique"),
    ("audit.csv.gz", _set("included", "yes"), "values other than True/False"),
    ("analysis_dataset.csv", lambda f: f.drop(f.index[0], inplace=True),
     "analysis rows do not match"),
    ("audit.csv.gz", _set("exclusion_reasons", "x", _included),
     "included rows have exclusion reasons"),
    ("audit.csv.gz", _set("exclusion_reasons", "", lambda f: ~_included(f)),
     "excluded rows have no exclusion reason"),
    ("analysis_dataset.csv", _set("selected_capacity", "0"),
     "invalid selected capacity"),
    ("audit.csv.gz", _set("duplicate_of", "nope", lambda f: f["duplicate_of"].ne("")),
     "duplicate_of points to unknown records"),
    ("audit.csv.gz", _set("source_file", EXCLUDED_NAME),
     "excluded workbooks appear"),
])
def test_validation_catches_each_problem(generated_output, tmp_path, name, change,
                                         message):
    copy = tamper(generated_output, tmp_path, name, change)
    with pytest.raises(ValueError, match=message):
        validate_outputs(copy, excluded_files=[EXCLUDED_NAME])


# ---------- inclusion rules ----------

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


@pytest.mark.parametrize("capacity", ["0", "-5", "inf", "-inf", "nan", "12.5", "abc"])
@pytest.mark.parametrize("open_spaces", [0.0, 4.0])
def test_invalid_selected_capacity_is_excluded(capacity, open_spaces):
    result = decide_inclusion(joined_row(selected_capacity=capacity,
                                         open_spaces=open_spaces))
    assert not result["included"].iloc[0]
    assert "invalid_selected_capacity" in result["exclusion_reasons"].iloc[0]
    assert pd.isna(result["fraction_available"].iloc[0])
    assert result["selected_capacity_raw"].iloc[0] == capacity


def test_zero_open_spaces_with_valid_capacity_is_included():
    result = decide_inclusion(joined_row(open_spaces=0.0))
    assert result["included"].iloc[0]
    assert result["fraction_available"].iloc[0] == 0


def test_missing_reading_without_flag_cannot_be_included():
    result = decide_inclusion(joined_row(open_spaces=None))
    assert result["exclusion_reasons"].iloc[0] == "invalid_fraction_available"


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


def test_observation_outside_capacity_manifest_is_excluded():
    result = decide_inclusion(joined_row(capacity_match="not_in_capacity_manifest",
                                         selected_capacity=""))
    assert result["exclusion_reasons"].iloc[0] == "capacity:not_in_capacity_manifest"


# ---------- join ----------

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
    assert joined["capacity_match"].tolist() == ["matched", "not_in_capacity_manifest"]


def test_join_rejects_capacity_rows_without_observation():
    audited, capacity = key_frames(capacity_rows=2, observation_rows=1)
    with pytest.raises(ValueError, match="match no observation"):
        join_capacity(audited, capacity)


def test_join_rejects_duplicate_keys():
    audited, capacity = key_frames()
    with pytest.raises(ValueError, match="not unique"):
        join_capacity(pd.concat([audited, audited]), capacity)


def test_join_rejects_missing_source_identifiers():
    audited, capacity = key_frames()
    audited["sheet_name"] = None
    with pytest.raises(ValueError, match="incomplete source identifiers"):
        join_capacity(audited, capacity)


def test_join_rejects_period_disagreement():
    audited, capacity = key_frames()
    capacity["quarter"] = "Winter"
    with pytest.raises(ValueError, match="quarter disagrees"):
        join_capacity(audited, capacity)


@pytest.mark.parametrize("capacity_date", ["", "2024-09-30"])
def test_missing_survey_date_is_audited_not_fatal(capacity_date):
    """Regression: an undated reading used to stop the whole build."""
    audited, capacity = key_frames(capacity_rows=2, observation_rows=2)
    audited.loc[1, "date"] = pd.NaT
    capacity.loc[1, "observation_date"] = capacity_date
    joined = join_capacity(audited, capacity)
    assert len(joined) == 2
    assert joined["capacity_match"].tolist() == ["matched", "missing_survey_date"]
    joined["quality_flag"] = ["pass", "missing_observation_datetime"]
    joined["exclusion_reason"] = ""
    joined["capacity_acceptance_reason"] = "valid_qpass_exact_group"
    joined["open_spaces"] = pd.Series([4.0, 4.0], dtype="Float64")
    joined["observation_group"] = [1, pd.NA]
    result = decide_inclusion(joined)
    assert result["included"].tolist() == [True, False]
    assert result["exclusion_reasons"].iloc[1] == (
        "quality:missing_observation_datetime|capacity:missing_survey_date"
    )
    assert result["record_id"].iloc[1] == "f.xlsx|Week 1|4|no-date|open_8am"


def test_undated_capacity_row_without_observation_still_fails():
    audited, capacity = key_frames(capacity_rows=2, observation_rows=1)
    capacity.loc[1, "observation_date"] = ""
    with pytest.raises(ValueError, match="1 capacity rows match no observation"):
        join_capacity(audited, capacity)


def test_undated_rows_from_one_excel_row_get_unique_ids():
    frame = pd.concat([joined_row(date=pd.NaT), joined_row(date=pd.NaT)],
                      ignore_index=True)
    ids = decide_inclusion(frame)["record_id"]
    assert ids.is_unique
    assert ids.str.endswith(("#1", "#2")).all()


# ---------- real data ----------

@pytest.mark.skipif(not (REAL_OUTPUT / "audit.csv.gz").is_file()
                    or not Path(RAW_QPASS_DIR).is_dir(),
                    reason="Needs QPASS workbooks and pipeline outputs "
                           "(set PARKSMART_PIPELINE_DIR for a custom --output-dir)")
def test_real_pipeline_outputs_are_consistent():
    _, source = load_observations(RAW_QPASS_DIR)
    counts = validate_outputs(REAL_OUTPUT, expected_total=len(source))
    assert counts["included"] + counts["excluded"] == len(source)
