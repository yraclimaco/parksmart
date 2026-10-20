"""Exercise the shared workbook loader and label pipeline with generated data."""

import datetime as dt

import pandas as pd
from openpyxl import Workbook

from src.label_decisions import standardize_labels
from src.label_reports import validate_label_output
from src.labels import prepare_label_records
from src.qpass_loader import load_all_qpass


def test_shared_loader_and_labels_preserve_records_and_source_values(tmp_path):
    """Two real Excel fixtures run end to end without private/raw workbooks."""
    header = [
        "Date",
        "Day",
        "Zone",
        "Order",
        "Report Area",
        "Neighborhood",
        "Lot / Structure",
        "Location",
        "Type",
        "Report Type",
        "Total Stall Count",
        "Open Spaces 8am",
        "Open Spaces 10am",
        "Open Spaces 12pm",
        "Open Spaces 2pm",
    ]
    date = dt.datetime(2024, 9, 30)
    fixtures = [
        ("QPASS 2024-2025-2 Fall.xlsx", " Gliderport ", "V"),
        ("QPASS 2024-2025-1 Summer.xlsx", "P602", "2hr As"),
    ]
    for name, facility, category in fixtures:
        workbook = Workbook()
        sheet = workbook.active
        sheet.title = "QPASS Data Entry (Week 1)"
        sheet.append(["Name(s):"])
        sheet.append(header)
        sheet.append(
            [
                date,
                "Monday",
                1,
                1,
                "Main Campus",
                "Central",
                "Lot",
                facility,
                category,
                category,
                10,
                8,
                6,
                4,
                2,
            ]
        )
        workbook.save(tmp_path / name)
        workbook.close()

    loaded = load_all_qpass(tmp_path)
    original = loaded.copy(deep=True)
    records = prepare_label_records(loaded)
    cleaned = standardize_labels(records)

    assert len(loaded) == len(records) == len(cleaned) == 2
    for raw, source in [
        ("facility_raw", "location"),
        ("category_raw", "type"),
        ("subtype_raw", "sub_type"),
    ]:
        pd.testing.assert_series_equal(cleaned[raw], loaded[source], check_names=False)
    for column in loaded.columns:
        pd.testing.assert_series_equal(cleaned[column], loaded[column])
    pd.testing.assert_frame_equal(loaded, original)
    assert set(cleaned.facility) == {"P386", "P602"}
    assert set(cleaned.category) == {"Visitor", "A 2 Hour"}
    assert cleaned.attrs["summer_2019_check"]["status"] == "checked"
    validate_label_output(records, cleaned)
