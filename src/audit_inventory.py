"""Inspect an Inventory workbook and save its source records."""

import argparse
from pathlib import Path

import pandas as pd


def audit_inventory(path):
    with pd.ExcelFile(path, engine="openpyxl") as workbook:
        print(f"Source: {path.name}")
        print(f"Sheets: {workbook.sheet_names}")

        data = pd.read_excel(
            workbook,
            sheet_name="Pivot Table Data",
            header=3,
        )

    data = data.dropna(how="all")

    columns = [
        "Lot  / Structure",
        "Lot #",
        "Garage Level",
        "Space Type",
        "Space Subtype",
        "Time Limit [minutes]",
        "For Inventory Survey?",
        "For Qpass Survey?",
        "Inventory By Locaton & Level",
        "Inventory By Location",
    ]

    missing = set(columns) - set(data.columns)
    if missing:
        raise ValueError(f"Missing expected columns: {sorted(missing)}")

    records = data.loc[
        data["Lot #"].notna() & data["Space Type"].notna(),
        columns,
    ]

    print(f"\nPopulated records: {len(records)}")
    print("\nCategories:")
    print(records["Space Type"].value_counts().to_string())

    print("\nFirst 10 records:")
    for row_number, row in records.head(10).iterrows():
        print(f"\nExcel row {row_number + 5}:")
        for column, value in row.items():
            print(f"  {column}: {value!r}")

    print("\nFacility-total cell audit:")
    raw = records["Inventory By Location"]
    numeric = pd.to_numeric(raw, errors="coerce")

    print(f"Blank cells: {raw.isna().sum()} (may be intentional)")
    print(f"Zero values: {numeric.eq(0).sum()} (require review)")
    print(f"Negative values: {numeric.lt(0).sum()}")
    print(
        "Non-numeric populated values:",
        (raw.notna() & numeric.isna()).sum(),
    )

    # Keep all source columns and record where each row came from.
    staging = data.loc[
        data["Lot #"].notna() & data["Space Type"].notna()
    ].copy()

    staging.insert(0, "source_row", staging.index + 5)
    staging.insert(0, "source_sheet", "Pivot Table Data")
    staging.insert(0, "source_file", path.name)

    # Create the output folder and save a separate CSV.
    output_dir = Path("data/interim/inventory")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{path.stem}_staging.csv"

    staging.to_csv(output_path, index=False)
    print(f"\nSaved {len(staging)} source records to: {output_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("workbook", type=Path)
    args = parser.parse_args()
    audit_inventory(args.workbook)