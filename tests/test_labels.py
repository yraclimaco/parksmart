"""Synthetic checks for preserving loader labels and audit metadata."""

import pandas as pd
import pytest
from src.labels import prepare_label_records, format_labels, format_label


def test_loader_adapter_preserves_raw_values_and_audit():
    source = pd.DataFrame(
        {
            "location": [" Athena ", "P602"],
            "type": ["2 hour Visitor", "Reserved"],
            "sub_type": [pd.NA, "Gold Pool"],
            "source_file": ["example.xlsx"] * 2,
            "sheet_name": ["Data Entry"] * 2,
            "source_row": [3, 4],
            "academic_year": ["2024-2025"] * 2,
            "quarter": ["Fall"] * 2,
            "raw_structure": [" Athena ", ""],
            "raw_lot": ["", "P602"],
        }
    )
    source.attrs = {"dropped_rows": {"example.xlsx": {"template": 2}}}
    records = prepare_label_records(source)
    cleaned = format_labels(records)
    assert records.facility_raw.tolist() == source.location.tolist()
    assert records.quarter_label.tolist() == ["2024-2025 Fall"] * 2
    assert cleaned.category_raw.tolist() == source.type.tolist()
    assert cleaned.iloc[1].subtype == "Gold Pool"
    assert cleaned.source_row.tolist() == [3, 4]
    pd.testing.assert_series_equal(records.raw_structure, source.raw_structure)
    records.attrs["dropped_rows"]["example.xlsx"]["template"] = 99
    assert source.attrs["dropped_rows"]["example.xlsx"]["template"] == 2


def test_loader_adapter_rejects_missing_required_fields():
    with pytest.raises(ValueError, match="Missing loader columns"):
        prepare_label_records(pd.DataFrame({"location": ["Athena"]}))


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("TDLLN", "TDLLN"),
        ("Nuevo West/Vela", "Nuevo West/Vela"),
        ("nuevo west/vela", "Nuevo West/Vela"),
        ("P386 (Gliderport)", "P386 (Gliderport)"),
        ("P602 ", "P602"),
        ("  visitor   loading ", "Visitor Loading"),
        ("SIO B", "SIO B"),
        ("Patient/Visitor Reserved", "Patient/Visitor Reserved"),
        ("0", "0"),
    ],
)
def test_formatting_preserves_codes_and_word_boundaries(raw, expected):
    assert format_label(raw) == expected
    assert format_label(format_label(raw)) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("2hr As", "2hr As"),
        ("3hr A", "3hr A"),
        ("2HR As", "2hr As"),
        ("2HRS Visitor", "2hrs Visitor"),
        ("30MIN Loading", "30min Loading"),
        ("2 hour Visitor", "2 Hour Visitor"),
        ("24/7 Enforced", "24/7 Enforced"),
    ],
)
def test_duration_formatting_preserves_restrictions(raw, expected):
    assert format_label(raw) == expected
    assert format_label(expected) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("3 hour Visitor", "Visitor 3 Hour"),
        ("2 Hour A", "A 2 Hour"),
        ("2 hour B", "B 2 Hour"),
        ("A 2 Hour", "A 2 Hour"),
        ("3 hours Visitor", "Visitor 3 Hour"),
        ("Visitor Patient/Visitor Reserved", "Visitor Patient/Visitor Reserved"),
        ("Visitor 2 hour 2 hour", "Visitor 2 Hour 2 Hour"),
        ("2 Hour Visitor Loading", "2 Hour Visitor Loading"),
        ("3hr Visitor", "Visitor 3 Hour"),
    ],
)
def test_category_order_changes_only_complete_hour_labels(raw, expected):
    from src.labels import format_category

    assert format_category(raw) == expected
    assert format_category(expected) == expected


def test_category_order_does_not_move_subtype_restrictions():
    records = pd.DataFrame(
        {
            "facility_raw": ["Gilman"] * 2,
            "category_raw": ["Visitor", "3 Hour Visitor"],
            "subtype_raw": ["2 Hours", "Patient/Visitor Reserved"],
        }
    )
    clean = format_labels(records)
    assert clean.category.tolist() == ["Visitor", "Visitor 3 Hour"]
    assert clean.subtype.tolist() == ["2 Hours", "Patient/Visitor Reserved"]
    assert clean.category_raw.tolist() == records.category_raw.tolist()
    assert clean.subtype_raw.tolist() == records.subtype_raw.tolist()


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("3hr A", "A 3 Hour"),
        ("2hr A", "A 2 Hour"),
        ("3hr B", "B 3 Hour"),
        ("A 3 Hours", "A 3 Hour"),
        ("A 2hr 12", "A 2hr 12"),
        ("2hr As", "2hr As"),
        ("Visitor Loading 2", "Visitor Loading 2"),
    ],
)
def test_duration_units_are_narrow_and_preserve_extra_text(raw, expected):
    from src.labels import format_category

    assert format_category(raw) == expected
    assert format_category(expected) == expected
