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
    allowed_headers = [
        CATEGORY_HEADERS,
        CATEGORY_HEADERS[:3] + ["D"] + CATEGORY_HEADERS[3:],
    ]
    layouts_found = []
    for header_row in range(min(10, len(data))):
        for expected in allowed_headers:
            headers = data.iloc[
                header_row,
                first_category:first_category + len(expected),
            ].tolist()
            if headers == expected:
                layouts_found.append((header_row, expected))

    if len(layouts_found) != 1:
        raise ValueError(
            f"{sheet}: unrecognized or ambiguous category headers"
        )

    header_row, headers = layouts_found[0]
    if len(data) <= header_row + 2:
        raise ValueError(f"{sheet}: no data rows after category headers")

    year_match = re.fullmatch(r"(\d{4})-(\d{4})", academic_year)
    if not year_match or int(year_match[2]) != int(year_match[1]) + 1:
        raise ValueError("Academic year must be consecutive years, e.g. 2018-2019")
    calendar_year = int(year_match[1]) + (quarter in {"Winter", "Spring"})
    report_title = " ".join(str(value) for value in data.iloc[1] if not pd.isna(value) and str(value).strip())
    if not re.search(rf"\b{re.escape(quarter)}\s*,?\s*{calendar_year}\b", report_title):
        raise ValueError(f"{sheet}: requested year/quarter does not match {report_title!r}")

    records = []
    for index in range(header_row + 2, len(data)):
        values = data.iloc[index]
        if all(pd.isna(value) or str(value).strip() == "" for value in values):
            continue
        facility = values.iloc[facility_col]
        if pd.isna(facility) or not str(facility).strip():
            raise ValueError(f"{sheet} row {index + 1}: populated row has no facility")
        if grain == "lot" and not re.fullmatch(r"P\d+[A-Za-z]?(?: \(closed for construction\))?", str(facility)):
            raise ValueError(f"{sheet} row {index + 1}: unexpected lot {facility!r}")
        if str(facility).strip().casefold() in {"total", "grand total", "subtotal"}:
            raise ValueError(f"{sheet} row {index + 1}: unexpected subtotal row")
        for offset, raw_header in enumerate(headers):
            column = first_category + offset
            continuation = data.iloc[header_row + 1, column]
            continuation = "" if pd.isna(continuation) else str(continuation)
            raw_value = values.iloc[column]
            blank = pd.isna(raw_value) or str(raw_value).strip() == ""
            capacity, status = capacity_status(pd.Series([None if blank else raw_value]))
            closure_note = "(closed for construction)" if (
                grain == "lot"
                and str(facility).endswith(" (closed for construction)")
            ) else ""
            if closure_note:
                capacity, status = pd.NA, "closure_review"
            category = " ".join(part for part in (raw_header, continuation) if part)
            records.append({
                "academic_year": academic_year,
                "quarter": quarter,
                "facility_raw": facility,
                "facility_note_raw": closure_note,
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


def clean_legacy_inventory(path, academic_year, quarter,
                           output_dir=Path("data/interim/inventory")):
    """Read supported legacy tables and write a capacity CSV plus audit JSON.

    Args:
        path: Original Inventory workbook; read only.
        academic_year: Academic year verified against the table titles.
        quarter: Quarter verified against the table titles.
        output_dir: Directory for extracted records and the schema audit.

    Returns:
        Path to the generated capacity CSV. No historical capacity is verified.
    """
    path, output_dir = Path(path), Path(output_dir)
    tables = pd.read_excel(
        path, sheet_name=[name for name, *_ in TABLES], header=None,
        keep_default_na=False, engine="openpyxl",
    )
    records = []
    for name, *_ in TABLES:
        records.extend(extract_legacy_table(
            tables[name], path.name, name, academic_year, quarter,
        ))
    cleaned = pd.DataFrame(records)
    if cleaned.empty:
        raise ValueError("No capacity records found in the supported tables")
    cleaned["capacity"] = cleaned["capacity"].astype("Int64")
    duplicate = cleaned.duplicated(
        ["academic_year", "quarter", "facility", "category"], keep=False,
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
        "capacity_status_counts": cleaned["capacity_status"].value_counts().to_dict(),
        "excluded_columns": [
            "All-category Total: not an individual parking category",
            "Motorcycle Parking Sections: sections are not individual space counts",
        ],
        "assumptions_and_limits": [
            "Blank source cells stay missing; zero is flagged for review.",
            "Text such as Closed for construction is preserved as invalid_numeric.",
            "Lot rows include garage components; never sum lot and structure tables together.",
            "Separate category breakdown tabs are not added to these totals.",
            "Summary categories do not establish subtype or time-limit equivalence.",
            "Formula capacities use workbook caches; no formulas are recalculated.",
            "Historical capacity verification remains pending.",
        ],
    }
    (output_dir / f"{path.stem}_legacy_audit.json").write_text(
        json.dumps(audit, indent=2), encoding="utf-8",
    )
    print(f"Capacity records: {len(cleaned)}")
    print(cleaned["capacity_status"].value_counts().to_string())
    print(f"Saved to: {destination}")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--quarter", required=True,
                        choices=["Summer", "Fall", "Winter", "Spring"])
    parser.add_argument("--output-dir", type=Path,
                        default=Path("data/interim/inventory"))
    args = parser.parse_args()
    clean_legacy_inventory(args.workbook, args.academic_year,
                           args.quarter, args.output_dir)
