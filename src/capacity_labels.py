"""Adapt both capacity sources to Issue #3 labels without losing raw evidence."""

import pandas as pd

from src.label_decisions import standardize_labels
from src.labels import prepare_label_records


FIELDS = ("facility", "category", "subtype")


def label_qpass(qpass):
    """Return loader rows with Issue #3 labels, restrictions, and raw values."""
    return standardize_labels(prepare_label_records(qpass))


def label_inventory(groups):
    """Return Inventory groups with shared labels while retaining all input columns.

    Legacy category headers can span two rows (UC + Vehicle). Their extractor's
    reconstructed category is used for decisions; the original header and all
    source cells remain unchanged. No restricted category or subtype is collapsed.
    """
    result = groups.copy()
    adapter = groups.copy()
    adapter["category_raw"] = groups.get("category", groups["category_raw"])
    adapter["subtype_raw"] = groups.get(
        "subtype_raw", pd.Series("", index=groups.index, dtype=object)
    )
    # These guard columns describe Inventory, not the QPASS-specific audited row.
    for name in ("sheet_name", "raw_structure", "raw_lot", "source_row"):
        if name not in adapter:
            adapter[name] = ""
    adapter["total_stall_count"] = groups["capacity"]
    labels = standardize_labels(adapter)
    for name in (*FIELDS, *(f"{f}_status" for f in FIELDS),
                 "label_status", "label_notes"):
        result[name] = labels[name]
    return result


def invalid_identifier(values):
    """Identify missing/placeholder/zero IDs without converting missing to 'nan'."""
    text = values.astype("string").str.strip()
    return (text.isna() | text.str.casefold().isin(
        ["", "nan", "none", "null", "n/a", "na", "<na>"]
    ) | pd.to_numeric(text, errors="coerce").eq(0).fillna(False)).fillna(True)
