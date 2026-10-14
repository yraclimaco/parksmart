"""Extract Inventory capacity groups without forcing uncertain values."""

import argparse
from pathlib import Path

import pandas as pd


def capacity_status(values):
    """Check the populated facility-total cells within a group."""
    populated = values.dropna()

    if populated.empty:
        return pd.NA, "missing"

    if len(populated) > 1:
        return pd.NA, "multiple_totals_review"

    numeric = pd.to_numeric(populated, errors="coerce")
    value = numeric.iloc[0]

    if pd.isna(value):
        return pd.NA, "invalid_numeric"

    if value < 0 or value == float("inf") or value % 1 != 0:
        return pd.NA, "invalid_capacity"

    if value == 0:
        return 0, "zero_review"

    return int(value), "positive_unverified"


def clean_inventory(path, academic_year, quarter):
    data = pd.read_excel(
        path,
        sheet_name="Pivot Table Data",
        header=3,
        engine="openpyxl",
    )

    data["source_row"] = data.index + 5

    data = data.loc[
        data["Lot #"].notna() & data["Space Type"].notna()
    ].copy()

    group_columns = [
        "Lot  / Structure",
        "Space Type",
        "Space Subtype",
        "Time Limit [minutes]",
    ]

    output_rows = []

    for keys, group in data.groupby(
        group_columns,
        dropna=False,
        sort=False,
    ):
        facility, category, subtype, time_limit = keys

        capacity, status = capacity_status(
            group["Inventory By Location"]
        )

        output_rows.append({
            "academic_year": academic_year,
            "quarter": quarter,
            "facility_raw": facility,
            "category_raw": category,
            "subtype_raw": subtype,
            "time_limit_raw": time_limit,
            "capacity": capacity,
            "capacity_status": status,
            "capacity_raw_values": repr(
                group["Inventory By Location"].tolist()
            ),
            "source_file": path.name,
            "source_sheet": "Pivot Table Data",
            "source_rows": ";".join(
                group["source_row"].astype(str)
            ),
        })

    cleaned = pd.DataFrame(output_rows)
    cleaned["capacity"] = cleaned["capacity"].astype("Int64")

    output_dir = Path("data/interim/inventory")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / f"{path.stem}_capacity_groups.csv"
    cleaned.to_csv(output_path, index=False)

    print(f"Source records: {len(data)}")
    print(f"Capacity groups: {len(cleaned)}")
    print("\nCapacity statuses:")
    print(cleaned["capacity_status"].value_counts().to_string())
    print(f"\nSaved to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument(
        "--quarter",
        required=True,
        choices=["Fall", "Winter", "Spring", "Summer"],
    )
    args = parser.parse_args()

    clean_inventory(
        args.workbook,
        args.academic_year,
        args.quarter,
    )