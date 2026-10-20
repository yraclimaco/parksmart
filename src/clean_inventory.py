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
    """Deprecated compatibility entry point; delegate to the supported modern cleaner.

    Legacy summary workbooks must use src.clean_inventory_legacy explicitly.
    Returns the generated capacity-group CSV path.
    """
    import warnings
    from src.clean_inventory_modern import clean_modern_inventory

    warnings.warn("Use src.clean_inventory_modern for newer layouts or "
                  "src.clean_inventory_legacy for legacy summary tables.",
                  FutureWarning, stacklevel=2)
    return clean_modern_inventory(path, academic_year, quarter)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Deprecated: use src.clean_inventory_modern")
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--quarter", required=True)
    args = parser.parse_args()
    clean_inventory(args.workbook, args.academic_year, args.quarter)
