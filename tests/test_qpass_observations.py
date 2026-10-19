import numpy as np
import pandas as pd
import pytest

from src.qpass_observations import (
    TIME_COLUMNS,
    load_representative_workbook,
    reshape_observations,
    validate_observations,
)


def table():
    return pd.DataFrame({"Date": [pd.Timestamp("2026-06-29")], "Location": [" Athena "],
                         "Type": [" Visitor Infusion "], "Report Type": [" Visitor "],
                         "Total\nStall\nCount": [10],
                         **{c: [i] for i, c in enumerate(TIME_COLUMNS)}})


def reshape(t):
    return reshape_observations(
        t, source_file="sample.xlsm", academic_year="2026-2027", quarter="Summer"
    )


def test_reshape_preserves_inputs_and_all_times():
    original = table()
    before = original.copy(deep=True)
    out, summary = validate_observations(reshape(original))
    pd.testing.assert_frame_equal(original, before)
    assert len(out) == 4
    assert out.observation_datetime.dt.hour.tolist() == [8, 10, 12, 14]
    assert out.quality_pass.all()
    assert out.raw_facility_name.iloc[0] == " Athena "
    assert out.parking_subtype.iloc[0] == "Visitor Infusion"
    assert summary.failed.sum() == 0


def test_bad_records_are_retained_with_multiple_flags():
    t = pd.concat([table()] * 2, ignore_index=True).astype(object)
    t.loc[0, "Open Spaces 8am"] = 11
    t.loc[0, "Open Spaces 10am"] = -1
    t.loc[0, "Open Spaces 12pm"] = "not a number"
    t.loc[0, "Open Spaces 2pm"] = np.inf
    out, summary = validate_observations(reshape(t))
    assert len(out) == 8
    assert out.quality_flag.str.contains("duplicate_observation").all()
    for flag in [
        "open_exceeds_capacity", "negative_open_spaces",
        "missing_open_spaces", "nonfinite_open_spaces",
    ]:
        assert out.quality_flag.str.contains(flag).any()
    assert summary.set_index("check").loc["any_check", "failed"] == 8


def test_distinct_subtypes_are_not_duplicates():
    t = pd.concat([table()] * 2, ignore_index=True)
    t.loc[1, "Type"] = "Visitor Radiation"
    out, _ = validate_observations(reshape(t))
    assert out.quality_pass.all()


@pytest.mark.parametrize(
    "capacity,flag",
    [(0, "zero_capacity"), (-1, "negative_capacity"), (1.5, "fractional_capacity")],
)
def test_capacity_checks(capacity, flag):
    t = table()
    t["Total\nStall\nCount"] = capacity
    out, _ = validate_observations(reshape(t))
    assert out.quality_flag.str.contains(flag).all()


def test_bad_dates_and_missing_identity():
    t = table()
    t["Date"] = 46202
    t["Location"] = " "
    out, _ = validate_observations(reshape(t))
    assert out.quality_flag.str.contains("missing_observation_datetime").all()
    assert out.quality_flag.str.contains("missing_facility_name").all()


def test_missing_time_header_fails_explicitly():
    with pytest.raises(ValueError, match="Missing input columns"):
        reshape(table().drop(columns=["Open Spaces 8am"]))


def test_workbook_adapter_keeps_partial_rows_and_source_row(tmp_path):
    t = pd.concat([table(), pd.DataFrame([{}]), table()], ignore_index=True)
    t.loc[2, "Date"] = pd.NaT
    path = tmp_path / "sample.xlsx"
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        t.to_excel(writer, sheet_name="Data Entry", startrow=1, index=False)
    out = load_representative_workbook(
        path, academic_year="2026-2027", quarter="Summer"
    )
    assert len(out) == 8
    assert out.attrs["blank_padding_rows"] == 1
    assert set(out.source_row) == {3, 5}
    audited, _ = validate_observations(out)
    missing_dates = audited.quality_flag.str.contains("missing_observation_datetime")
    assert missing_dates.sum() == 4


def test_duplicates_across_files_with_repeated_dataframe_indexes():
    first = reshape(table())
    second = reshape(table())
    second["source_file"] = "copy.xlsm"
    audited, _ = validate_observations(pd.concat([first, second]))
    assert len(audited) == 8
    assert audited.quality_flag.str.contains("duplicate_observation").all()


def test_connects_real_loader_and_preserves_audits(tmp_path):
    from src.qpass_loader import load_all_qpass
    from src.qpass_observations import reshape_loaded_observations

    for year, date in [("2025-2026", "2025-06-30"),
                       ("2026-2027", "2026-06-29")]:
        wide = table()
        wide["Date"] = pd.Timestamp(date)
        path = tmp_path / f"QPASS {year}-1 Summer.xlsx"
        with pd.ExcelWriter(path, engine="openpyxl") as writer:
            wide.to_excel(
                writer, sheet_name="Data Entry", startrow=1, index=False
            )
    loaded = load_all_qpass(tmp_path)
    before = loaded.copy(deep=True)
    out = reshape_loaded_observations(loaded)
    pd.testing.assert_frame_equal(loaded, before)
    assert len(out) == 4 * len(loaded) == 8
    assert out.groupby("source_file").size().tolist() == [4, 4]
    assert set(out.academic_year) == {"2025-2026", "2026-2027"}
    assert set(out.source_sheet) == {"Data Entry"}
    assert set(out.source_row) == {3}
    assert out.attrs == loaded.attrs
    audited, _ = validate_observations(out)
    assert audited.quality_pass.all()


def test_loader_adapter_keeps_levels_text_and_missing_categories():
    from src.qpass_loader import OUTPUT_COLUMNS
    from src.qpass_observations import reshape_loaded_observations

    rows = []
    for level in ["Level 1", "Level 2"]:
        rows.append(dict(source_file="old.xlsx", sheet_name="Week 1", source_row=6,
                         academic_year="2018-2019", quarter="Fall",
                         date=pd.Timestamp("2018-10-01"), location="Athena",
                         type="A", report_type="A", level=level,
                         total_stall_count=10, open_8am="FULL", open_10am=5,
                         open_12pm=4, open_2pm=3))
    loaded = pd.DataFrame(rows).reindex(columns=OUTPUT_COLUMNS)
    out = reshape_loaded_observations(loaded)
    audited, _ = validate_observations(out)
    assert not audited.quality_flag.str.contains("duplicate_observation").any()
    assert audited.raw_open_spaces.eq("FULL").sum() == 2
    assert audited.quality_flag.str.contains("missing_open_spaces").sum() == 2
    loaded["report_type"] = pd.NA
    audited, _ = validate_observations(reshape_loaded_observations(loaded))
    assert audited.quality_flag.str.contains("missing_parking_category").all()


def test_loader_adapter_reports_missing_columns():
    from src.qpass_observations import reshape_loaded_observations

    with pytest.raises(ValueError, match="Missing loader columns"):
        reshape_loaded_observations(pd.DataFrame())


def test_empty_validation_returns_zero_counts():
    empty = reshape(table()).iloc[:0].copy()
    before = empty.copy(deep=True)
    audited, summary = validate_observations(empty)
    pd.testing.assert_frame_equal(empty, before)
    assert audited.empty
    assert str(audited.quality_flag.dtype).startswith("string")
    assert pd.api.types.is_bool_dtype(audited.quality_pass.dtype)
    assert len(summary) == 16
    assert summary[["failed", "passed"]].eq(0).all().all()


def test_optional_sub_type_distinctions_and_repeated_identities():
    first = reshape(table())
    first["level"] = "Level 1"
    first["sub_type"] = "Allocation One"
    second = first.copy()
    second["sub_type"] = "Allocation Two"
    audited, _ = validate_observations(pd.concat([first, second], ignore_index=True))
    assert audited.quality_pass.all()

    repeated = pd.concat([first, second, first], ignore_index=True)
    audited, summary = validate_observations(repeated)
    duplicates = audited.quality_flag.str.contains("duplicate_observation")
    assert duplicates.tolist() == [True] * 4 + [False] * 4 + [True] * 4
    counts = summary.set_index("check")
    assert counts.loc["duplicate_observation", "failed"] == 8
    assert counts.loc["duplicate_observation", "passed"] == 4
    assert counts.loc["any_check", "failed"] == 8


def test_normalized_duplicate_headers_fail_explicitly():
    wide = table()
    wide[" Location "] = wide["Location"]
    with pytest.raises(ValueError, match="Duplicate headers"):
        reshape(wide)


def test_summary_counts_overlapping_checks_once_overall():
    wide = table().astype(object)
    wide["Open Spaces 8am"] = -1
    wide["Open Spaces 10am"] = 11
    wide["Open Spaces 12pm"] = "unknown"
    wide["Open Spaces 2pm"] = 1.5
    _, summary = validate_observations(reshape(wide))
    counts = summary.set_index("check")
    for check in ["negative_open_spaces", "open_exceeds_capacity",
                  "missing_open_spaces", "fractional_open_spaces"]:
        assert counts.loc[check, "failed"] == 1
        assert counts.loc[check, "passed"] == 3
    assert counts.loc["any_check", "failed"] == 4
    assert counts.loc["any_check", "passed"] == 0
