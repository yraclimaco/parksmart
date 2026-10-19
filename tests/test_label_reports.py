"""Record and source-row counts must stay distinct in label reports."""

import pandas as pd
from src.label_decisions import standardize_labels
from src.label_reports import build_label_reports, validate_label_output


def test_reports_count_each_record_once_and_group_daily_repetitions():
    records = pd.DataFrame(
        {
            "facility_raw": [0, 0, "Athena"],
            "category_raw": [pd.NA, pd.NA, "A"],
            "subtype_raw": [pd.NA] * 3,
            "source_file": ["sample.xlsx"] * 3,
            "sheet_name": ["Data Entry"] * 3,
            "source_row": [65, 65, 66],
            "quarter_label": ["2024-2025 Fall"] * 3,
        }
    )
    cleaned = standardize_labels(records)
    reports = build_label_reports(cleaned)
    validate_label_output(records, cleaned)
    assert reports["unresolved_records"].shape[0] == 2
    assert reports["unresolved_sources"].shape[0] == 1
    assert reports["unresolved_sources"].affected_records.sum() == 2
    assert reports["by_file_quarter"].unresolved.sum() == 2
    # Two bad fields per record; field totals must not become record totals.
    assert reports["unresolved_values"].affected_records.sum() == 4
    assert reports["status_summary"].records.sum() == 3


def test_reports_allow_no_unresolved_records():
    records = pd.DataFrame(
        {
            "facility_raw": ["Athena"],
            "category_raw": ["A"],
            "subtype_raw": [pd.NA],
            "source_file": ["sample.xlsx"],
            "sheet_name": ["Data Entry"],
            "source_row": [3],
            "quarter_label": ["2024-2025 Fall"],
        }
    )
    reports = build_label_reports(standardize_labels(records))
    assert reports["unresolved_sources"].empty
    assert reports["unresolved_values"].empty
    assert reports["status_summary"].records.sum() == 1


def test_cleaned_inventory_retains_raw_variants_and_missing_values():
    from src.label_reports import build_cleaned_inventories

    records = pd.DataFrame(
        {
            "facility_raw": ["Athena", "Athena"],
            "category_raw": ["V", "Visitor"],
            "subtype_raw": [pd.NA, pd.NA],
            "source_file": ["sample.xlsx"] * 2,
            "source_row": [3, 4],
            "quarter_label": ["2024-2025 Fall"] * 2,
        }
    )
    inventories = build_cleaned_inventories(standardize_labels(records))
    assert inventories["category"].shape[0] == 1
    assert inventories["category"].iloc[0].raw_variants == ["'V'", "'Visitor'"]
    assert inventories["category"].records.sum() == 2
    assert inventories["subtype"].records.sum() == 2
    assert inventories["subtype"]["subtype"].isna().all()


def test_report_export_includes_required_cleaned_columns_and_summary(tmp_path):
    import json
    from src.label_reports import export_label_reports

    records = pd.DataFrame(
        {
            "facility_raw": ["Athena", "P103"],
            "category_raw": ["V", "2hr As"],
            "subtype_raw": [pd.NA] * 2,
            "source_file": ["sample.xlsx"] * 2,
            "sheet_name": ["Data Entry"] * 2,
            "source_row": [3, 4],
            "quarter_label": ["2024-2025 Fall"] * 2,
        }
    )
    cleaned = standardize_labels(records)
    paths = export_label_reports(records, cleaned, {}, tmp_path)
    assert all(path.exists() for path in paths)
    exported = json.loads((tmp_path / "standardized_records.json").read_text())
    assert exported[0]["category_raw"] == "V"
    assert exported[0]["category"] == "Visitor"
    assert exported[1]["label_status"] == "unresolved"
    assert "1 (50.00%)" in (tmp_path / "summary.md").read_text()
