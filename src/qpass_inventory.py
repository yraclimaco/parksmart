"""Inventory the sheets, header rows, and columns of every QPASS workbook.

This is a read-only audit step for GitHub issue #1. It opens each workbook,
looks at every sheet, guesses which row holds the column headers, and writes
the results to a table. It never modifies the workbooks.

Run from the repo root:
    python -m src.qpass_inventory
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

# Paths are built from this file's location (src/ -> repo root), so the
# script works no matter which folder it is run from.
REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_QPASS_DIR = REPO_ROOT / "data" / "raw" / "QPASS"
RESULTS_DIR = REPO_ROOT / "results"
INVENTORY_CSV_NAME = "qpass_inventory.csv"
INVENTORY_MD_NAME = "qpass_inventory.md"

QPASS_FILE_GLOB = "QPASS*.xls*"

# Header rows sit near the top of each sheet; data rows below them can look
# header-like (e.g. a "Structure" value), so only the first rows are searched.
HEADER_SEARCH_ROWS = 15

# A row counts as a header only if at least this many of its cells contain a
# header keyword. Chosen by inspecting the workbooks: real header rows match
# 5+ cells, while title and data rows match 0-2.
MIN_HEADER_KEYWORD_CELLS = 3

# First cell of the real label row in each known layout: "Date" for the
# newer long sheets, "Structure" for the 2018-2019 wide sheets. Checked before
# keyword scoring, because the wide sheets have an "Available Available ..."
# row that scores higher than the real label row.
KNOWN_HEADER_FIRST_CELLS = {"Date", "Structure"}

# Words that appear in QPASS column headers across both old and new layouts.
HEADER_KEYWORDS = {
    "date", "day", "week", "location", "lot", "structure", "type",
    "total", "stall", "stalls", "spaces", "open", "available", "count",
}

# Filenames look like "QPASS 2024-2025-2 Fall.xlsm", sometimes with two
# spaces before the quarter name. \s+ tolerates the extra space.
FILENAME_PATTERN = re.compile(
    r"^QPASS\s+(?P<academic_year>\d{4}-\d{4})-(?P<quarter_number>\d)\s+(?P<quarter_name>[A-Za-z]+)"
)

# UCSD numbers quarters within an academic year starting with Summer.
QUARTER_NUMBER_TO_NAME = {1: "Summer", 2: "Fall", 3: "Winter", 4: "Spring"}


def parse_qpass_filename(filename: str) -> dict:
    """Extract academic year and quarter from a QPASS workbook filename.

    Args:
        filename: Workbook filename, e.g. "QPASS 2024-2025-2 Fall.xlsm".

    Returns:
        Dict with academic_year, quarter_number, quarter_name, and
        name_matches_number (False when the number and name disagree, e.g.
        "-2 Spring"). Values are None if the filename does not match the
        expected pattern.
    """
    match = FILENAME_PATTERN.match(filename)
    if match is None:
        return {
            "academic_year": None,
            "quarter_number": None,
            "quarter_name": None,
            "name_matches_number": None,
        }
    quarter_number = int(match.group("quarter_number"))
    quarter_name = match.group("quarter_name").title()
    return {
        "academic_year": match.group("academic_year"),
        "quarter_number": quarter_number,
        "quarter_name": quarter_name,
        "name_matches_number": QUARTER_NUMBER_TO_NAME.get(quarter_number) == quarter_name,
    }


def clean_column_name(value) -> str:
    """Turn a raw header cell into a readable single-line string.

    Header cells in newer workbooks contain line breaks
    ("Total\\nStall\\nCount"); these are collapsed to single spaces.

    Args:
        value: Raw cell value from the header row.

    Returns:
        The cleaned text, or an empty string for blank cells.
    """
    if pd.isna(value):
        return ""
    return " ".join(str(value).split())


def count_header_keyword_cells(row: pd.Series) -> int:
    """Count how many cells in a row contain at least one header keyword.

    Matching is by whole word, so "Monday" does not match the keyword "day".

    Args:
        row: One row of a sheet read with header=None.

    Returns:
        Number of cells containing a keyword.
    """
    hits = 0
    for value in row:
        words = set(re.findall(r"[a-z]+", clean_column_name(value).lower()))
        if words & HEADER_KEYWORDS:
            hits += 1
    return hits


def find_header_row(sheet: pd.DataFrame) -> int | None:
    """Guess which row of a sheet holds the column headers.

    First looks for a row whose first cell is a known label
    (KNOWN_HEADER_FIRST_CELLS). If there is none, picks the row with the most
    header-keyword cells.

    Args:
        sheet: Sheet contents read with header=None.

    Returns:
        Zero-based row index of the header row, or None if no known label
        row exists and no row in the first HEADER_SEARCH_ROWS rows has enough
        keyword cells.
    """
    search_rows = range(min(HEADER_SEARCH_ROWS, len(sheet)))
    for row_index in search_rows:
        if clean_column_name(sheet.iat[row_index, 0]) in KNOWN_HEADER_FIRST_CELLS:
            return row_index

    best_row, best_hits = None, 0
    for row_index in search_rows:
        hits = count_header_keyword_cells(sheet.iloc[row_index])
        if hits > best_hits:
            best_row, best_hits = row_index, hits
    if best_hits < MIN_HEADER_KEYWORD_CELLS:
        return None
    return best_row


def inventory_workbook(path: Path) -> list[dict]:
    """Describe every sheet in one QPASS workbook.

    A workbook that cannot be opened produces a single row with
    status "load_error" and the error message, instead of being skipped.

    Args:
        path: Path to a .xlsx or .xlsm QPASS workbook.

    Returns:
        One dict per sheet with file, sheet, size, header row, and columns.
    """
    file_info = {"source_file": path.name, **parse_qpass_filename(path.name)}
    try:
        sheets = pd.read_excel(path, sheet_name=None, header=None)
    except Exception as error:  # report any failure rather than crash the audit
        logger.error("Could not load %s: %s", path.name, error)
        return [{**file_info, "sheet_name": None, "status": "load_error", "error": str(error)}]

    rows = []
    for sheet_name, sheet in sheets.items():
        header_row = find_header_row(sheet)
        columns = []
        if header_row is not None:
            columns = [name for name in map(clean_column_name, sheet.iloc[header_row]) if name]
        rows.append({
            **file_info,
            "sheet_name": sheet_name,
            "status": "ok" if header_row is not None else "no_header_found",
            "error": None,
            "n_rows": sheet.shape[0],
            "n_cols": sheet.shape[1],
            # Excel numbers rows from 1, so +1 matches what you see in Excel.
            "header_excel_row": None if header_row is None else header_row + 1,
            "n_columns_named": len(columns),
            "columns": " | ".join(columns),
        })
    return rows


def build_inventory(raw_dir: Path = RAW_QPASS_DIR) -> pd.DataFrame:
    """Inventory every QPASS workbook in a folder.

    Args:
        raw_dir: Folder containing the downloaded QPASS workbooks.

    Returns:
        DataFrame with one row per sheet (or per unloadable file).

    Raises:
        FileNotFoundError: If raw_dir does not exist or has no QPASS files.
    """
    paths = sorted(raw_dir.glob(QPASS_FILE_GLOB))
    if not paths:
        raise FileNotFoundError(f"No files matching {QPASS_FILE_GLOB!r} in {raw_dir}")
    rows = []
    for path in paths:
        rows.extend(inventory_workbook(path))
    return pd.DataFrame(rows)


def write_markdown_summary(inventory: pd.DataFrame, path: Path) -> None:
    """Write a per-file summary table in Markdown for easy reading.

    Args:
        inventory: Output of build_inventory.
        path: Where to write the .md file.
    """
    lines = [
        "| File | Year | Q# | Quarter | Name OK | Sheets | Sheets with header | Load error |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for source_file, group in inventory.groupby("source_file", sort=True):
        first = group.iloc[0]
        has_error = (group["status"] == "load_error").any()
        lines.append(
            f"| {source_file} | {first['academic_year']} | {first['quarter_number']} "
            f"| {first['quarter_name']} | {first['name_matches_number']} "
            f"| {0 if has_error else len(group)} | {(group['status'] == 'ok').sum()} "
            f"| {first['error'] if has_error else ''} |"
        )
    path.write_text("\n".join(lines) + "\n")


def main() -> None:
    """Build the inventory and save it as CSV (detail) and Markdown (summary)."""
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    inventory = build_inventory(RAW_QPASS_DIR)
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = RESULTS_DIR / INVENTORY_CSV_NAME
    md_path = RESULTS_DIR / INVENTORY_MD_NAME
    inventory.to_csv(csv_path, index=False)
    write_markdown_summary(inventory, md_path)
    logger.info("Wrote %d sheet rows to %s and %s", len(inventory), csv_path, md_path)


if __name__ == "__main__":
    main()
