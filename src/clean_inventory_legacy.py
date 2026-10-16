"""Extract capacities from the audited legacy Inventory summary tables."""

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from src.clean_inventory import capacity_status


CATEGORY_HEADERS = [
    "A", "B", "S", "Visitor", "Reserved", "Allocated", "Accessible",
    "UC", "Service", "Loading",
]
TABLES = [
    ("5A By Lot", 1, 2, "lot"),
    ("6A By Structure", 0, 1, "structure"),
]


def extract_legacy_table(data, source_file, sheet, academic_year, quarter):
    """Reshape one audited legacy count table without replacing missing values.

    Args:
        data: Sheet read with header=None and default missing-value detection off.
        source_file: Original workbook filename.
        sheet: One of the supported sheet names in TABLES.
        academic_year: Verified academic year in YYYY-YYYY form.
        quarter: Verified quarter name matching the report title.

    Returns:
        List of capacity records with source cells and original header parts.
        Motorcycle sections and all-category totals are intentionally excluded.
    """
    layouts = {name: (facility_col, first_category, grain)
               for name, facility_col, first_category, grain in TABLES}
    facility_col, first_category, grain = layouts[sheet]
    if data.shape[0] < 8 or data.shape[1] < first_category + 10:
        raise ValueError(f"{sheet}: table is smaller than the audited layout")
    headers = data.iloc[5, first_category:first_category + 10].tolist()
    if headers != CATEGORY_HEADERS:
        raise ValueError(f"{sheet}: unrecognized category headers: {headers!r}")

    year_match = re.fullmatch(r"(\d{4})-(\d{4})", academic_year)
    if not year_match or int(year_match[2]) != int(year_match[1]) + 1:
        raise ValueError("Academic year must be consecutive years, e.g. 2018-2019")
    calendar_year = int(year_match[1]) + (quarter in {"Winter", "Spring"})
    report_title = str(data.iloc[1, facility_col])
    if not re.search(rf"\b{re.escape(quarter)},\s*{calendar_year}\b", report_title):
        raise ValueError(f"{sheet}: requested year/quarter does not match {report_title!r}")

    records = []
    for index in range(7, len(data)):
        values = data.iloc[index]
        if all(pd.isna(value) or str(value).strip() == "" for value in values):
            continue
        facility = values.iloc[facility_col]
        if pd.isna(facility) or not str(facility).strip():
            raise ValueError(f"{sheet} row {index + 1}: populated row has no facility")
        if grain == "lot" and not re.fullmatch(r"P\d+", str(facility)):
            raise ValueError(f"{sheet} row {index + 1}: unexpected lot {facility!r}")
        if str(facility).strip().casefold() in {"total", "grand total", "subtotal"}:
            raise ValueError(f"{sheet} row {index + 1}: unexpected subtotal row")
        for offset, raw_header in enumerate(CATEGORY_HEADERS):
            column = first_category + offset
            continuation = data.iloc[6, column]
            continuation = "" if pd.isna(continuation) else str(continuation)
            raw_value = values.iloc[column]
            blank = pd.isna(raw_value) or str(raw_value).strip() == ""
            capacity, status = capacity_status(pd.Series([None if blank else raw_value]))
            category = " ".join(part for part in (raw_header, continuation) if part)
            records.append({
                "academic_year": academic_year,
                "quarter": quarter,
                "facility_raw": facility,
                "facility": str(facility).strip(),
                "category_raw": raw_header,
                "category": category,
                "category_header_parts_raw": json.dumps([raw_header, continuation]),
                "subtype_raw": None,
                "time_limit_raw": None,
                "capacity": capacity,
                "capacity_status": status,
                "capacity_raw_values": repr([raw_value]),
                "source_file": source_file,
                "source_sheet": sheet,
                "source_rows": str(index + 1),
                "source_cell": f"{chr(65 + column)}{index + 1}",
                "facility_granularity": grain,
                "category_scope": "legacy_summary_category_requires_review",
                "schema_version": "legacy_summary_tables_v1",
                "report_title_raw": report_title,
            })
    return records



def clean_legacy_inventory(
    path,
    academic_year,
    quarter,
    output_dir=Path("data/interim/inventory"),
):
    """Read legacy Inventory tables and save capacity records and an audit.

    Args:
        path: Original workbook path.
        academic_year: Academic year checked against the report titles.
        quarter: Quarter checked against the report titles.
        output_dir: Directory for generated files.

    Returns:
        Path to the generated capacity CSV.
    """
    path = Path(path)
    output_dir = Path(output_dir)

    tables = pd.read_excel(
        path,
        sheet_name=[name for name, *_ in TABLES],
        header=None,
        keep_default_na=False,
        engine="openpyxl",
    )

    records = []
    for name, *_ in TABLES:
        records.extend(
            extract_legacy_table(
                tables[name],
                path.name,
                name,
                academic_year,
                quarter,
            )
        )

    cleaned = pd.DataFrame(records)
    if cleaned.empty:
        raise ValueError("No capacity records found")

    cleaned["capacity"] = cleaned["capacity"].astype("Int64")

    duplicate = cleaned.duplicated(
        ["academic_year", "quarter", "facility", "category"],
        keep=False,
    )
    cleaned.loc[duplicate, "capacity_status"] = "duplicate_key_review"
    cleaned.loc[duplicate, "capacity"] = pd.NA

    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{path.stem}_capacity_groups.csv"
    cleaned.to_csv(destination, index=False)

    audit = {
        "source_file": path.name,
        "schema_version": "legacy_summary_tables_v1",
        "source_sheets": list(tables),
        "capacity_records": len(cleaned),
        "capacity_status_counts": (
            cleaned["capacity_status"].value_counts().to_dict()
        ),
        "excluded_columns": [
            "All-category Total: not an individual parking category",
            "Motorcycle Parking Sections: sections are not space counts",
        ],
        "assumptions_and_limits": [
            "Blank cells remain missing; zero requires review.",
            "Closure text is preserved as invalid_numeric.",
            "Lot and structure tables overlap; do not sum them together.",
            "Category breakdown tabs are not added to these totals.",
            "Category and subtype equivalence requires verification.",
            "Formula capacities use saved workbook caches.",
            "Historical capacity verification remains pending.",
        ],
    }

    audit_path = output_dir / f"{path.stem}_legacy_audit.json"
    audit_path.write_text(
        json.dumps(audit, indent=2),
        encoding="utf-8",
    )

    print(f"Capacity records: {len(cleaned)}")
    print(cleaned["capacity_status"].value_counts().to_string())
    print(f"Saved to: {destination}")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument(
        "--quarter",
        required=True,
        choices=["Summer", "Fall", "Winter", "Spring"],
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/interim/inventory"),
    )
    args = parser.parse_args()

    clean_legacy_inventory(
        args.workbook,
        args.academic_year,
        args.quarter,
        args.output_dir,
    )