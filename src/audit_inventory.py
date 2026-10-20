"""Deprecated exploratory audit; use the supported layout-aware cleaner."""

import argparse
from pathlib import Path
import warnings


def audit_inventory(path, academic_year=None, quarter=None):
    """Delegate an explicitly labeled modern workbook to its supported cleaner.

    Args:
        path: Original modern Inventory workbook path; never modified.
        academic_year: Required consecutive YYYY-YYYY academic year.
        quarter: Required Summer, Fall, Winter or Spring label.

    Returns:
        Path to the supported capacity-group CSV; writes that CSV and its audit
        under data/interim/inventory. No missing-identifier rows are filtered.

    Raises:
        ValueError: If period arguments are missing. For legacy summary tables,
            use src.clean_inventory_legacy instead.
    """
    if academic_year is None or quarter is None:
        raise ValueError("Use src.clean_inventory_modern with --academic-year and "
                         "--quarter, or src.clean_inventory_legacy for old tables")
    warnings.warn("audit_inventory is deprecated; use src.clean_inventory_modern "
                  "or src.clean_inventory_legacy", FutureWarning, stacklevel=2)
    from src.clean_inventory_modern import clean_modern_inventory

    return clean_modern_inventory(Path(path), academic_year, quarter)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--academic-year", required=True)
    parser.add_argument("--quarter", required=True,
                        choices=["Summer", "Fall", "Winter", "Spring"])
    args = parser.parse_args()
    audit_inventory(args.workbook, args.academic_year, args.quarter)
