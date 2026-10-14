"""Tests for src/qpass_inventory.py, using small fake workbooks in a temp folder."""

import datetime as dt

import pandas as pd
import pytest
from openpyxl import Workbook

from src import qpass_inventory
from src.qpass_inventory import (
    build_inventory,
    clean_column_name,
    count_header_keyword_cells,
    find_header_row,
    inventory_workbook,
    write_markdown_summary,
)


def _sheet(rows):
    """Build a DataFrame shaped like a sheet read with header=None."""
    return pd.DataFrame(rows)


def _save_workbook(folder, filename):
    """Save a two-sheet fake QPASS workbook: one data sheet, one notes sheet."""
    workbook = Workbook()
    data = workbook.active
    data.title = "Data Entry"
    data.append(["Name(s):"])
    data.append(["Date", "Day", "Location", "Type", "Total\nStall\nCount", "Open Spaces 8am"])
    data.append([dt.datetime(2026, 9, 28), "Monday", "Gilman", "A", 100, 50])
    workbook.create_sheet("Directions & Links").append(["Read me first"])
    path = folder / filename
    workbook.save(path)
    return path


# ---------- helpers ----------

def test_clean_column_name_collapses_line_breaks():
    assert clean_column_name("Total\nStall\nCount") == "Total Stall Count"
    assert clean_column_name(None) == ""


def test_keyword_match_is_whole_word():
    # "Monday" contains "day" but must not count as a header keyword
    assert count_header_keyword_cells(pd.Series(["Monday", "Tuesday"])) == 0
    assert count_header_keyword_cells(pd.Series(["Day", "Total Spaces", "Monday"])) == 2


# ---------- find_header_row ----------

def test_find_header_row_prefers_structure_row_over_available_row():
    """Old wide sheets: the 'Available' row scores higher but is not the label row."""
    sheet = _sheet([
        [None, None, None, None, "Monday"],
        ["Structure", "Lot", "Type", "Total Spaces", "08:00"],
        [None, None, None, None] + ["Available"] * 8,
        ["Athena", "Level 1", "A", 40, 30],
    ])
    assert find_header_row(sheet) == 1


def test_find_header_row_finds_date_row():
    sheet = _sheet([["Name(s):"], ["Date", "Day", "Location"], ["2024-09-30", "Monday", "Athena"]])
    assert find_header_row(sheet) == 1


def test_find_header_row_falls_back_to_keyword_scoring():
    sheet = _sheet([
        ["Summary"],
        ["Location", "Type", "Total Spaces", "Open Spaces 8am"],
        ["Athena", "A", 40, 30],
    ])
    assert find_header_row(sheet) == 1


def test_find_header_row_returns_none_without_headers():
    assert find_header_row(_sheet([["Read me first"], ["https://example.com"]])) is None


# ---------- inventory_workbook / build_inventory ----------

def test_inventory_workbook_describes_each_sheet(tmp_path):
    rows = inventory_workbook(_save_workbook(tmp_path, "QPASS 2026-2027-2  Fall.xlsx"))
    by_sheet = {row["sheet_name"]: row for row in rows}
    assert by_sheet["Data Entry"]["status"] == "ok"
    assert by_sheet["Data Entry"]["header_excel_row"] == 2
    assert by_sheet["Data Entry"]["columns"].startswith("Date | Day | Location")
    assert by_sheet["Directions & Links"]["status"] == "no_header_found"
    assert by_sheet["Data Entry"]["academic_year"] == "2026-2027"


def test_inventory_workbook_records_load_error_instead_of_skipping(tmp_path):
    broken = tmp_path / "QPASS 2024-2025-2 Fall.xlsx"
    broken.write_text("this is not an Excel file")
    rows = inventory_workbook(broken)
    assert len(rows) == 1
    assert rows[0]["status"] == "load_error"
    assert rows[0]["error"]  # the reason is recorded, not empty
    assert rows[0]["source_file"] == broken.name


def test_build_inventory_raises_on_empty_folder(tmp_path):
    with pytest.raises(FileNotFoundError):
        build_inventory(tmp_path)


def test_build_inventory_includes_broken_files(tmp_path):
    _save_workbook(tmp_path, "QPASS 2026-2027-2  Fall.xlsx")
    (tmp_path / "QPASS 2024-2025-2 Fall.xlsx").write_text("not Excel")
    inventory = build_inventory(tmp_path)
    assert set(inventory["source_file"]) == {"QPASS 2026-2027-2  Fall.xlsx", "QPASS 2024-2025-2 Fall.xlsx"}
    assert (inventory["status"] == "load_error").sum() == 1


# ---------- outputs ----------

def test_write_markdown_summary_lists_files_and_errors(tmp_path):
    _save_workbook(tmp_path, "QPASS 2026-2027-2  Fall.xlsx")
    (tmp_path / "QPASS 2024-2025-2 Fall.xlsx").write_text("not Excel")
    output = tmp_path / "summary.md"
    write_markdown_summary(build_inventory(tmp_path), output)
    text = output.read_text()
    assert text.startswith("| File | Year |")
    assert "| QPASS 2026-2027-2  Fall.xlsx | 2026-2027 | 2 | Fall | True | 2 | 1 |  |" in text
    fall_2024_line = next(line for line in text.splitlines() if "2024-2025-2 Fall" in line)
    assert "| 0 | 0 |" in fall_2024_line  # broken file: no sheets read, error shown


def test_main_writes_csv_and_markdown(tmp_path, monkeypatch):
    raw_dir, results_dir = tmp_path / "raw", tmp_path / "results"
    raw_dir.mkdir()
    _save_workbook(raw_dir, "QPASS 2026-2027-2  Fall.xlsx")
    monkeypatch.setattr(qpass_inventory, "RAW_QPASS_DIR", raw_dir)
    monkeypatch.setattr(qpass_inventory, "RESULTS_DIR", results_dir)
    qpass_inventory.main()
    assert (results_dir / qpass_inventory.INVENTORY_CSV_NAME).exists()
    assert (results_dir / qpass_inventory.INVENTORY_MD_NAME).exists()
