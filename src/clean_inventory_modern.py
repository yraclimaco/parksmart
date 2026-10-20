"""Extract newer Inventory layouts with raw values and explicit review flags."""

import argparse
import json
import re
from pathlib import Path

import pandas as pd

from src.clean_inventory import capacity_status


SHEET = "Pivot Table Data"
DETAIL = ["Space Type", "Space Subtype", "Time Limit [minutes]"]


def present(value):
    """Return whether a source cell contains a nonblank value, including zero."""
    return not pd.isna(value) and str(value).strip() != ""


def extract_modern_inventory(raw, source_file, academic_year, quarter,
                             title_values=()):
    """Extract candidate groups from a sheet read with header=None.

    Retain missing identifiers and raw capacities. Repeated row counts in the
    2024 layout are ambiguous and are never summed or silently deduplicated.
    Return a cleaned DataFrame and an audit dictionary. Positive counts remain
    unverified until historical timing and QPASS scope have been checked.
    """
    years = re.fullmatch(r"(\d{4})-(\d{4})", academic_year)
    if not years or int(years[2]) != int(years[1]) + 1:
        raise ValueError("Academic year must contain consecutive years")
    if quarter not in {"Summer", "Fall", "Winter", "Spring"}:
        raise ValueError("Unknown quarter")
    if academic_year not in source_file or quarter.lower() not in source_file.lower():
        raise ValueError("Requested period does not match Inventory filename")

    header_rows = [i for i in range(min(10, len(raw)))
                   if set(DETAIL).issubset(set(raw.iloc[i].tolist()))]
    if len(header_rows) != 1:
        raise ValueError("Cannot identify one unambiguous Inventory header")
    header_row = header_rows[0]
    headers = raw.iloc[header_row].tolist()
    for field in DETAIL:
        if headers.count(field) != 1:
            raise ValueError(f"Duplicate required header: {field}")

    if "Inventory By Location" in headers and "Lot  / Structure" in headers:
        facility_col, capacity_col = "Lot  / Structure", "Inventory By Location"
        schema = "facility_totals"
    elif "Inventory" in headers and "Lot / Garage" in headers:
        facility_col, schema = "Lot / Garage", "quarter_row_counts"
        calendar_year = int(years[1]) + (quarter in {"Winter", "Spring"})
        options = [quarter, f"{quarter} {calendar_year}"]
        available = [name for name in options if name in headers]
        if len(available) != 1:
            raise ValueError("Cannot identify requested quarter capacity column")
        capacity_col = available[0]
    else:
        raise ValueError("Unsupported newer Inventory capacity layout")

    used = [facility_col, capacity_col, *DETAIL]
    if schema == "quarter_row_counts":
        used.append("Inventory")
    if any(headers.count(name) != 1 for name in used):
        raise ValueError("Duplicate required capacity or facility header")

    # Position-based temporary column names preserve unnamed source columns.
    data = raw.iloc[header_row + 1:].copy()
    data.columns = [f"column_{i}" for i in range(len(headers))]
    data["source_row"] = data.index + 1
    data = data.rename(columns={f"column_{headers.index(name)}": name for name in used})
    value_columns = [c for c in data.columns if c != "source_row"]
    populated = data[value_columns].map(present).any(axis=1)
    blank_rows = int((~populated).sum())
    data = data.loc[populated].copy()
    if data.empty:
        raise ValueError("No populated Inventory records")

    title_raw = [str(v) for v in title_values if present(v)]
    selector_raw = [str(v) for v in raw.iloc[:header_row].to_numpy().ravel()
                    if present(v) and isinstance(v, str)]
    metadata_issues = []
    for value in title_raw + selector_raw:
        for found in re.finditer(r"\b(Summer|Fall|Winter|Spring)\b(?:\s+(\d{4}))?", value):
            name, year = found.groups()
            expected_year = int(years[1]) + (quarter in {"Winter", "Spring"})
            if name != quarter or (year and int(year) != expected_year):
                metadata_issues.append(value)
    metadata_issues = list(dict.fromkeys(metadata_issues))

    rows = []
    keys = [facility_col, *DETAIL]
    for values, group in data.groupby(keys, dropna=False, sort=False):
        facility, category, subtype, limit = values
        raw_values = group[capacity_col].tolist()
        checked = pd.Series([v if present(v) else None for v in raw_values], dtype=object)
        capacity, status = capacity_status(checked)
        if schema == "quarter_row_counts" and len(group) > 1:
            capacity, status = pd.NA, "multiple_totals_review"
        conflict = False
        if schema == "quarter_row_counts":
            for selected, reported in zip(raw_values, group["Inventory"]):
                if present(selected) != present(reported):
                    conflict = True
                elif present(selected):
                    left, right = pd.to_numeric(pd.Series([selected, reported]), errors="coerce")
                    if pd.isna(left) or pd.isna(right) or left != right:
                        conflict = True
        if conflict:
            capacity, status = pd.NA, "capacity_column_conflict"
        invalid_identifier = any(
            not present(v) or str(v).strip() in {"0", "0.0"}
            for v in (facility, category)
        )
        if invalid_identifier:
            capacity, status = pd.NA, "invalid_identifier_review"
        if metadata_issues:
            capacity, status = pd.NA, "period_metadata_review"
        rows.append({
            "academic_year": academic_year, "quarter": quarter,
            "facility_raw": facility,
            "facility": str(facility).strip() if present(facility) else "",
            "category_raw": category,
            "category": str(category).strip() if present(category) else "",
            "subtype_raw": subtype, "time_limit_raw": limit,
            "capacity": capacity, "capacity_status": status,
            "capacity_raw_values": repr(raw_values),
            "inventory_column_raw_values": repr(group["Inventory"].tolist())
                if schema == "quarter_row_counts" else "",
            "source_file": source_file, "source_sheet": SHEET,
            "source_rows": ";".join(group["source_row"].astype(str)),
            "capacity_source_column": capacity_col,
            "schema_version": schema,
            "source_record_count": len(group),
            "invalid_identifier": invalid_identifier,
            "capacity_column_conflict": conflict,
            "period_metadata_status": "conflict" if metadata_issues else "no_conflict_detected",
        })
    cleaned = pd.DataFrame(rows)
    cleaned["capacity"] = cleaned["capacity"].astype("Int64")
    audit = {
        "source_file": source_file, "academic_year": academic_year,
        "quarter": quarter, "source_sheet": SHEET,
        "header_excel_row": header_row + 1, "headers_raw": headers,
        "title_values_raw": title_raw, "selector_values_raw": selector_raw,
        "period_metadata_issues": metadata_issues,
        "source_records": len(data), "blank_rows_excluded": blank_rows,
        "capacity_groups": len(cleaned), "schema_version": schema,
        "capacity_source_column": capacity_col,
        "capacity_status_counts": cleaned["capacity_status"].value_counts().to_dict(),
        "assumptions": [
            "No positive capacity is historically verified by extraction alone.",
            "Repeated 2024 count rows are flagged, not summed or deduplicated.",
            "Inventory By Location already contains grouped totals; do not sum repeated totals.",
            "Combined Inventory by Lot totals all categories and is not selected.",
            "Blank, zero, invalid identifiers and conflicting metadata require review.",
            "Workbook formula caches are read without recalculation.",
            "All populated source rows are retained in groups; only wholly blank rows are excluded.",
        ],
    }
    return cleaned, audit


def clean_modern_inventory(path, academic_year, quarter,
                           output_dir=Path("data/interim/inventory")):
    """Read a newer workbook without modifying it and write CSV plus audit JSON.

    Args:
        path: Read-only modern workbook path. academic_year: Consecutive YYYY-YYYY
        label. quarter: Summer/Fall/Winter/Spring. output_dir: Generated CSV/audit
        directory.

    Returns:
        Generated CSV Path. Writes CSV and JSON audit; raises ValueError for
        unsupported or inconsistent schema/periods.
    """
    path, output_dir = Path(path), Path(output_dir)
    sheets = pd.read_excel(path, sheet_name=[SHEET, "Title"], header=None,
                           keep_default_na=False, engine="openpyxl")
    cleaned, audit = extract_modern_inventory(
        sheets[SHEET], path.name, academic_year, quarter,
        sheets["Title"].to_numpy().ravel(),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{path.stem}_capacity_groups.csv"
    cleaned.to_csv(destination, index=False)
    (output_dir / f"{path.stem}_modern_audit.json").write_text(
        json.dumps(audit, indent=2, default=str), encoding="utf-8",
    )
    print(f"Source records: {audit['source_records']}")
    print(cleaned["capacity_status"].value_counts().to_string())
    print(f"Saved: {destination}")
    return destination


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--quarter", required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("data/interim/inventory"))
    args = parser.parse_args()
    clean_modern_inventory(args.workbook, args.academic_year, args.quarter, args.output_dir)
