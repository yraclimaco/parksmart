"""Decision checks use synthetic records, never the source workbooks."""

import pandas as pd
import pytest
from src.label_decisions import standardize_labels


def sample():
    return pd.DataFrame(
        {
            "facility_raw": ["Pangea"] * 3,
            "category_raw": ["V", "V", "Visitor Loading"],
            "subtype_raw": [pd.NA] * 3,
            "source_file": ["QPASS 2019-2020-1 Summer.xlsx"] * 3,
            "sheet_name": ["S19 W2 Data"] * 3,
            "source_row": [100, 101, 102],
            "raw_structure": ["Pangea", "", "Pangea"],
            "raw_lot": ["", "", ""],
            "total_stall_count": [145, 9, 5],
        }
    )


def test_alias_and_ambiguous_facility_are_independent():
    records = sample()
    clean = standardize_labels(records)
    assert clean.category.tolist() == ["Visitor", "Visitor", "Visitor Loading"]
    assert clean.iloc[0].facility == "Pangea"
    assert clean.iloc[0].label_status == "standardized"
    assert pd.isna(clean.iloc[1].facility)
    assert clean.iloc[1].facility_raw == "Pangea"
    assert clean.iloc[1].category_status == "standardized"
    assert clean.iloc[1].label_status == "unresolved"
    assert clean.iloc[2].label_status == "keep_separate"
    assert records.iloc[1].facility_raw == "Pangea"
    assert len(clean) == len(records)


def test_uncertain_rule_cannot_flag_other_workbooks():
    records = sample()
    records["source_file"] = "other.xlsx"
    clean = standardize_labels(records)
    assert clean.iloc[1].facility == "Pangea"
    assert clean.iloc[1].label_status == "standardized"


def test_missing_subtype_allowed_and_zero_facility_unresolved():
    records = sample()
    records["facility_raw"] = records["facility_raw"].astype(object)
    records.loc[0, "facility_raw"] = 0
    clean = standardize_labels(records)
    assert clean.iloc[0].label_status == "unresolved"
    assert clean.iloc[2].subtype_status == "unchanged"


def test_restriction_status_and_unresolved_precedence():
    records = sample()
    mappings = {
        "category": [
            {
                "raw_value": "Visitor Loading",
                "standard_value": "Visitor Loading",
                "status": "keep_separate",
                "notes": "Additional restriction retained",
            }
        ]
    }
    clean = standardize_labels(records, mappings)
    assert clean.iloc[2].label_status == "keep_separate"
    assert clean.iloc[1].label_status == "unresolved"


def test_visitor_qualifiers_and_verified_wording_remain_distinct():
    categories = [
        "V",
        "Visitor",
        "Visitor 2 Hour",
        "1 Hr Visitor",
        "Visitor: PAD",
        "Visitor Loading",
        "Visitor 2 hour 2 hour",
        "Carpool 2 Person Carpool",
        "A Physician A",
    ]
    records = pd.DataFrame(
        {
            "facility_raw": ["Athena"] * len(categories),
            "category_raw": categories,
            "subtype_raw": [pd.NA] * len(categories),
        }
    )
    cleaned = standardize_labels(records)
    assert cleaned.iloc[0].category == "Visitor"
    assert cleaned.iloc[0].label_status == "standardized"
    assert cleaned.iloc[1].label_status == "unchanged"
    for i in range(2, 6):
        assert cleaned.iloc[i].label_status == "keep_separate"
        assert cleaned.iloc[i].category != "Visitor"
    for i in range(6, 9):
        assert cleaned.iloc[i].label_status == "keep_separate"
        assert pd.notna(cleaned.iloc[i].category)
    assert cleaned.category_raw.tolist() == categories


def test_visitor_subtypes_preserved_even_when_alias_is_applied():
    records = pd.DataFrame(
        {
            "facility_raw": ["Athena", "Athena"],
            "category_raw": ["V", "Visitor"],
            "subtype_raw": ["Loading", "Infusion"],
        }
    )
    cleaned = standardize_labels(records)
    assert cleaned.category.tolist() == ["Visitor", "Visitor"]
    assert cleaned.subtype.tolist() == ["Loading", "Infusion"]
    assert cleaned.label_status.tolist() == ["keep_separate", "keep_separate"]


def test_reordered_two_hour_visitor_alias_preserves_restriction():
    records = pd.DataFrame(
        {
            "facility_raw": ["Athena"] * 4,
            "category_raw": [
                "2 hour Visitor",
                "Visitor 2 Hour",
                "Visitor",
                "3 Hour Visitor",
            ],
            "subtype_raw": [pd.NA] * 4,
        }
    )
    clean = standardize_labels(records)
    assert clean.category.tolist() == [
        "Visitor 2 Hour",
        "Visitor 2 Hour",
        "Visitor",
        "Visitor 3 Hour",
    ]
    assert clean.category_status.tolist() == [
        "keep_separate",
        "keep_separate",
        "unchanged",
        "keep_separate",
    ]
    assert clean.category_raw.tolist() == records.category_raw.tolist()
    again = standardize_labels(clean)
    pd.testing.assert_series_equal(clean.category, again.category)
    pd.testing.assert_series_equal(clean.label_status, again.label_status)


def test_verified_repeated_wording_keeps_all_restrictions():
    raw = [
        "Visitor 5 Minute 5 minutes",
        "Visitor 2 hour 2 hour",
        "Carpool 2 Person Carpool",
        "A Physician A",
    ]
    records = pd.DataFrame(
        {"facility_raw": ["P759"] * 4, "category_raw": raw, "subtype_raw": [pd.NA] * 4}
    )
    clean = standardize_labels(records)
    assert clean.category.tolist() == [
        "Visitor 5 Minute",
        "Visitor 2 Hour",
        "Carpool 2 Person",
        "Physician A",
    ]
    assert clean.label_status.tolist() == ["keep_separate"] * 4
    assert clean.category_raw.tolist() == raw
    assert clean.subtype.isna().all()


def test_physician_subtype_never_collapses_to_generic_a():
    records = pd.DataFrame(
        {
            "facility_raw": ["P759", "P759"],
            "category_raw": ["A", "A"],
            "subtype_raw": ["Physician A", pd.NA],
        }
    )
    clean = standardize_labels(records)
    assert clean.category.tolist() == ["A", "A"]
    assert clean.iloc[0].subtype == "Physician A"
    assert clean.label_status.tolist() == ["keep_separate", "unchanged"]


def test_a_enforcement_and_two_person_aliases_preserve_distinctions():
    raw = [
        "24/7 A",
        "A (24/7)",
        "A 24/7 Enforced",
        "A",
        "24/7",
        "2 Person Carpool",
        "Carpool",
        "2hr As",
        "Visitor 2-Hour Limit 6",
        "VA",
    ]
    records = pd.DataFrame(
        {
            "facility_raw": ["P402"] * len(raw),
            "category_raw": raw,
            "subtype_raw": [pd.NA] * len(raw),
        }
    )
    clean = standardize_labels(records)
    assert clean.category.tolist()[:7] == [
        "A 24/7 Enforced",
        "A 24/7 Enforced",
        "A 24/7 Enforced",
        "A",
        "24/7",
        "Carpool 2 Person",
        "Carpool",
    ]
    for i in [0, 1, 2, 5]:
        assert clean.iloc[i].label_status == "keep_separate"
    assert clean.category.tolist()[7:] == raw[7:]
    assert clean.category_raw.tolist() == raw


def test_p602_typo_correction_is_scoped_and_preserves_time_limit():
    records = pd.DataFrame(
        {
            "facility_raw": ["P602", "Other"],
            "category_raw": ["2hr As", "2hr As"],
            "subtype_raw": [pd.NA] * 2,
        }
    )
    clean = standardize_labels(records)
    assert clean.category.tolist() == ["A 2 Hour", "2hr As"]
    assert clean.iloc[0].label_status == "keep_separate"
    assert clean.category_raw.tolist() == ["2hr As", "2hr As"]


def test_va_is_not_an_alias_for_historical_ss():
    records = pd.DataFrame(
        {
            "facility_raw": ["P782"] * 2,
            "category_raw": ["SS", "VA"],
            "subtype_raw": [pd.NA] * 2,
        }
    )
    clean = standardize_labels(records)
    assert clean.category.tolist() == ["SS", "VA"]
    assert clean.iloc[1].label_status == "keep_separate"


def test_verified_facility_aliases_preserve_raw_names_and_history():
    raw = ["Gliderport", "P386 (Gliderport)", "P386", "Osler", "South"]
    records = pd.DataFrame(
        {"facility_raw": raw, "category_raw": ["A"] * 5, "subtype_raw": [pd.NA] * 5}
    )
    clean = standardize_labels(records)
    assert clean.facility.tolist() == ["P386", "P386", "P386", "South", "South"]
    assert clean.facility_raw.tolist() == raw


def test_unverified_as_keeps_wording_and_is_unresolved():
    records = pd.DataFrame(
        {
            "facility_raw": ["P602", "P103"],
            "category_raw": ["2hr As"] * 2,
            "subtype_raw": [pd.NA] * 2,
        }
    )
    clean = standardize_labels(records)
    assert clean.category.tolist() == ["A 2 Hour", "2hr As"]
    assert clean.label_status.tolist() == ["keep_separate", "unresolved"]


@pytest.mark.parametrize("field", ["facility", "category"])
@pytest.mark.parametrize("value", [0, 0.0, -0.0, "0", "0.0", "0.00", " 0.0 "])
def test_zero_identifiers_are_unresolved_in_all_numeric_forms(field, value):
    records = pd.DataFrame(
        {
            "facility_raw": pd.Series(["Athena"], dtype=object),
            "category_raw": pd.Series(["A"], dtype=object),
            "subtype_raw": pd.Series([pd.NA], dtype=object),
        }
    )
    records.loc[0, f"{field}_raw"] = value
    clean = standardize_labels(records)
    assert clean.iloc[0][f"{field}_status"] == "unresolved"
    assert clean.iloc[0].label_status == "unresolved"
    pd.testing.assert_series_equal(clean[f"{field}_raw"], records[f"{field}_raw"])
    assert "missing or zero identifier" in clean.iloc[0].label_notes


def test_zero_detection_does_not_flag_nonzero_or_alphanumeric_identifiers():
    records = pd.DataFrame(
        {
            "facility_raw": [8980, "P000", "P602"],
            "category_raw": ["A", "B", "S"],
            "subtype_raw": [pd.NA] * 3,
        }
    )
    clean = standardize_labels(records)
    assert clean.facility_status.tolist() == ["unchanged"] * 3
    assert clean.label_status.tolist() == ["unchanged"] * 3


@pytest.mark.parametrize(
    "category",
    [
        "Reserved",
        "Accessible",
        "Carpool",
        "Electric Vehicle",
        "Reserved Gold Pool",
        "A Carpool",
        "Electric Vehicle Charging",
        "RESERVED",
        "accessible",
        "electric vehicle",
    ],
)
def test_restricted_categories_are_flagged_without_losing_wording(category):
    records = pd.DataFrame(
        {
            "facility_raw": ["P602"],
            "category_raw": [category],
            "subtype_raw": ["Patient/Visitor Reserved"],
        }
    )
    clean = standardize_labels(records)
    assert clean.iloc[0].category_status == "keep_separate"
    assert clean.iloc[0].subtype_status == "keep_separate"
    assert clean.iloc[0].label_status == "keep_separate"
    assert clean.iloc[0].category.casefold() == category.casefold()
    pd.testing.assert_series_equal(clean.category_raw, records.category_raw)
    pd.testing.assert_series_equal(clean.subtype_raw, records.subtype_raw)
    assert clean.iloc[0].subtype == "Patient/Visitor Reserved"


@pytest.mark.parametrize(
    "category",
    [
        "Closed For Improvements / Constrruction",
        "CLOSED FOR IMPROVEMENTS / CONSTRUCTION",
        "Closed",
    ],
)
def test_closure_categories_are_standardized_and_raw_wording_retained(category):
    records = pd.DataFrame(
        {
            "facility_raw": ["P602"],
            "category_raw": [category],
            "subtype_raw": [pd.NA],
        }
    )
    clean = standardize_labels(records)
    assert clean.iloc[0].category_status == "unresolved"
    assert clean.iloc[0].label_status == "unresolved"
    assert clean.iloc[0].category == "Closure"
    assert clean.iloc[0].category_raw == category
    assert "closure label" in clean.iloc[0].label_notes


@pytest.mark.parametrize(
    "missing",
    [
        "source_file",
        "sheet_name",
        "source_row",
        "raw_structure",
        "raw_lot",
        "total_stall_count",
    ],
)
def test_summer_2019_missing_guards_are_reported(missing, caplog):
    records = sample().drop(columns=[missing])
    clean = standardize_labels(records)
    audit = clean.attrs["summer_2019_check"]
    assert audit == {
        "status": "skipped_missing_columns",
        "missing_columns": [missing],
        "matched_records": None,
    }
    assert "Summer 2019 ownership check skipped" in caplog.text
    assert missing in caplog.text
    assert clean.iloc[1].facility == "Pangea"
    assert len(clean) == len(records)


def test_summer_2019_complete_guards_report_check_and_match_count():
    clean = standardize_labels(sample())
    assert clean.attrs["summer_2019_check"] == {
        "status": "checked",
        "missing_columns": [],
        "matched_records": 1,
    }


@pytest.mark.parametrize("reverse", [False, True])
def test_scoped_p602_decision_wins_regardless_of_config_order(reverse):
    import json
    from src.label_decisions import DEFAULT_CATEGORY_REVIEW

    decisions = [
        d
        for d in json.loads(DEFAULT_CATEGORY_REVIEW.read_text())
        if d["raw_value"] == "2hr As"
    ]
    if reverse:
        decisions.reverse()
    records = pd.DataFrame(
        {
            "facility_raw": ["P602", "P103", "Other"],
            "category_raw": ["2hr As"] * 3,
            "subtype_raw": [pd.NA] * 3,
        }
    )
    clean = standardize_labels(records, {"category": decisions})
    assert clean.category.tolist() == ["A 2 Hour", "2hr As", "2hr As"]
    assert clean.category_status.tolist() == [
        "keep_separate",
        "unresolved",
        "unresolved",
    ]
    assert "Unverified meaning" not in clean.iloc[0].label_notes
    pd.testing.assert_series_equal(clean.category_raw, records.category_raw)


def test_closure_is_limited_to_its_dated_record():
    from src.label_reports import validate_label_output

    records = pd.DataFrame(
        {
            "facility_raw": ["P602", "P602"],
            "category_raw": ["Closed For Improvements / Constrruction", "A"],
            "subtype_raw": [pd.NA, pd.NA],
            "date": pd.to_datetime(["2024-09-30", "2024-10-01"]),
        }
    )
    clean = standardize_labels(records)
    assert clean.category.tolist() == ["Closure", "A"]
    assert clean.category_status.tolist() == ["unresolved", "unchanged"]
    assert clean.facility.tolist() == ["P602", "P602"]
    assert "survey time only" in clean.iloc[0].label_notes
    validate_label_output(records, clean)
    pd.testing.assert_series_equal(clean.date, records.date)
