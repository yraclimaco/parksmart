"""Summarize label decisions without dropping questionable source records."""

import pandas as pd

FIELDS = ("facility", "category", "subtype")
STATUSES = ("unchanged", "standardized", "keep_separate", "unresolved")


def build_label_reports(cleaned):
    """Return status counts, unresolved source rows, and file/quarter summaries.

    Args:
        cleaned: Output of standardize_labels, retaining loader provenance.

    Returns:
        Dictionary of DataFrames. Source-row groups collapse repeated survey
        days for inspection only; their record counts retain every observation.
        Overall unresolved counts count affected records once across fields.
    """
    unresolved = cleaned.loc[cleaned["label_status"].eq("unresolved")].copy()
    status = cleaned["label_status"].value_counts().reindex(STATUSES, fill_value=0)
    status_summary = status.rename_axis("label_status").reset_index(name="records")
    status_summary["percent"] = (
        status_summary["records"].div(len(cleaned) or 1).mul(100)
    )

    group_keys = [
        "source_file",
        "sheet_name",
        "source_row",
        "facility_raw",
        "facility",
        "category_raw",
        "category",
        "subtype_raw",
        "subtype",
        "label_notes",
    ]
    unresolved_sources = (
        unresolved.groupby(group_keys, dropna=False, sort=False)
        .size()
        .reset_index(name="affected_records")
    )
    unresolved_values = []
    for field in FIELDS:
        rows = cleaned.loc[cleaned[f"{field}_status"].eq("unresolved")]
        for value, group in rows.groupby(f"{field}_raw", dropna=False, sort=False):
            unresolved_values.append(
                {
                    "field": field,
                    "raw_value_repr": repr(value),
                    "affected_records": len(group),
                    "files": sorted(set(group["source_file"].dropna())),
                    "quarters": sorted(set(group["quarter_label"].dropna())),
                    "notes": sorted(set(group["label_notes"].dropna())),
                }
            )
    by_file_quarter = (
        cleaned.assign(is_unresolved=cleaned["label_status"].eq("unresolved"))
        .groupby(["source_file", "quarter_label"], dropna=False, sort=False)
        .agg(records=("label_status", "size"), unresolved=("is_unresolved", "sum"))
        .reset_index()
    )
    return {
        "status_summary": status_summary,
        "unresolved_sources": unresolved_sources,
        "unresolved_values": pd.DataFrame(
            unresolved_values,
            columns=[
                "field",
                "raw_value_repr",
                "affected_records",
                "files",
                "quarters",
                "notes",
            ],
        ),
        "by_file_quarter": by_file_quarter,
        "unresolved_records": unresolved,
    }


def validate_label_output(original, cleaned):
    """Raise AssertionError if labels lose records, raw values, or provenance.

    Args:
        original: Loader-adapted records before standardization.
        cleaned: Output from standardize_labels, in its original record order.

    Returns:
        None. Intended as a fast integration check across all loaded workbooks.
    """
    assert len(original) == len(cleaned), "Record count changed"
    assert original.index.equals(cleaned.index), "Record order/index changed"
    for column in [f"{field}_raw" for field in FIELDS] + [
        "source_file",
        "sheet_name",
        "source_row",
        "academic_year",
        "quarter",
        "date",
        "raw_structure",
        "raw_lot",
    ]:
        if column in original:
            pd.testing.assert_series_equal(original[column], cleaned[column])
    for column in ["label_status"] + [f"{field}_status" for field in FIELDS]:
        assert cleaned[column].isin(STATUSES).all(), f"Invalid status in {column}"
    unresolved_field = (
        cleaned[[f"{field}_status" for field in FIELDS]].eq("unresolved").any(axis=1)
    )
    assert cleaned["label_status"].eq("unresolved").equals(unresolved_field)
    assert cleaned.loc[unresolved_field, "label_notes"].str.strip().ne("").all()


def build_cleaned_inventories(cleaned):
    """Return complete cleaned-label inventories for final human review.

    Args:
        cleaned: Standardized records including raw labels and field statuses.

    Returns:
        A table per field with one row per cleaned value (including missing),
        record counts, raw representations, field statuses, and provenance.
        These groupings aid review; they do not verify new aliases.
    """
    inventories = {}
    for field in FIELDS:
        inventory = (
            cleaned.groupby(field, dropna=False, sort=False)
            .agg(
                records=("source_row", "size"),
                raw_variants=(
                    f"{field}_raw",
                    lambda values: sorted({repr(value) for value in values}),
                ),
                field_statuses=(f"{field}_status", lambda values: sorted(set(values))),
                files=("source_file", lambda values: sorted(set(values.dropna()))),
                quarters=("quarter_label", lambda values: sorted(set(values.dropna()))),
            )
            .reset_index()
        )
        inventories[field] = inventory
    return inventories


def export_label_reports(original, cleaned, raw_inventories, folder):
    """Write submission reports and a local cleaned dataset as JSON.

    Args:
        original: Loader-adapted input records.
        cleaned: Standardized records with field and record statuses.
        raw_inventories: Raw facility, category, and subtype inventory tables.
        folder: Output directory. Existing generated reports are replaced.

    Returns:
        Paths of the generated files. No source workbooks are opened or changed.
    """
    from pathlib import Path

    validate_label_output(original, cleaned)
    reports = build_label_reports(cleaned)
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    tables = dict(reports)
    for field, inventory in raw_inventories.items():
        tables[f"{field}_inventory"] = inventory
    for field, inventory in build_cleaned_inventories(cleaned).items():
        tables[f"{field}_cleaned_inventory"] = inventory
    required = [
        "facility_raw",
        "facility",
        "category_raw",
        "category",
        "subtype_raw",
        "subtype",
        "label_status",
    ]
    example_columns = required + ["source_file", "sheet_name", "source_row"]
    examples = cleaned[example_columns].drop_duplicates()
    tables["raw_cleaned_examples"] = examples.groupby(
        "label_status", sort=False, group_keys=False
    ).head(4)
    tables["standardized_records"] = cleaned
    paths = []
    for name, table in tables.items():
        path = folder / f"{name}.json"
        table.to_json(
            path, orient="records", indent=2, date_format="iso", force_ascii=False
        )
        paths.append(path)
    unresolved = len(reports["unresolved_records"])
    total = len(cleaned)
    summary = [
        "# Issue #3 results",
        "",
        f"Records: {total:,} across {cleaned['source_file'].nunique()} workbooks.",
        f"Unresolved: {unresolved:,} ({unresolved / (total or 1):.2%}).",
        "",
        "Counts refer to loader records before observation-time reshaping.",
        "Source rows and raw labels are preserved; unresolved rows are retained.",
        "",
        "| Status | Records |",
        "|---|---:|",
    ]
    for row in reports["status_summary"].itertuples(index=False):
        summary.append(f"| {row.label_status} | {row.records:,} |")
    summary += [
        "",
        "See docs/issue3_label_decisions.md for rules, evidence,",
        "remaining uncertainties, and loader coverage limitations.",
        "",
    ]
    summary_path = folder / "summary.md"
    summary_path.write_text("\n".join(summary))
    paths.append(summary_path)
    return paths
