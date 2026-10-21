"""Build the integrated QPASS analysis dataset, audit table, and summary.

Run from the repository root after downloading QPASS and Inventory workbooks:

    python -m src.build_dataset

The pipeline reuses the merged team modules and does not reimplement them:

1. Shared loader, reshape, and quality checks (Issue #2) on all workbooks.
2. Label standardization and capacity selection (Issues #3/#4) through the
   existing capacity batch, which writes its own reports to an interim folder.
3. A one-to-one join of the two timed tables on source file, sheet, Excel row,
   survey date, and time slot. Records are never lost or multiplied silently.
4. Inclusion decisions, exact-repeat deduplication, fraction_available, and
   exports. Original workbooks are never modified.
"""

from __future__ import annotations

import argparse
import json
import logging
import time
import warnings
from contextlib import redirect_stdout
from pathlib import Path

import pandas as pd

from src.qpass_loader import RAW_QPASS_DIR, load_all_qpass
from src.qpass_observations import reshape_loaded_observations, validate_observations
from src.run_capacity_matching import run_capacity_matching

LOGGER = logging.getLogger(__name__)

DEFAULT_MANIFEST = Path("results/capacity_matching/inventory_sources.csv")
DEFAULT_INVENTORY_DIR = Path("data/interim/inventory")
DEFAULT_CAPACITY_DIR = Path("data/interim/pipeline/capacity")
DEFAULT_OUTPUT_DIR = Path("data/processed/pipeline")

# The capacity batch labels slots 8am..2pm; the reshape uses the wide column.
CAPACITY_TIME_TO_COLUMN = {"8am": "open_8am", "10am": "open_10am",
                           "12pm": "open_12pm", "2pm": "open_2pm"}
SOURCE_KEY = ["source_file", "sheet_name", "source_row", "date",
              "source_time_column"]
# Columns in both tables that must agree after the join.
SHARED_COLUMNS = ["academic_year", "quarter"]

# Every validate_observations() check must be listed, so a new check forces an
# explicit decision. True blocks analysis use. Checks on the QPASS capacity
# column do not block on their own: capacity selection already rejects or
# replaces unsafe QPASS capacities, and open counts are re-checked against the
# selected capacity. Exact repeats are deduplicated instead of excluded.
QUALITY_FLAG_BLOCKS = {
    "missing_observation_datetime": True,
    "missing_location": True,
    "missing_type": True,
    "missing_total_stall_count": False,
    "unexpected_text_total_stall_count": False,
    "negative_total_stall_count": False,
    "nonfinite_total_stall_count": False,
    "fractional_total_stall_count": False,
    "missing_open_spaces": True,
    "unexpected_text_open_spaces": True,
    "negative_open_spaces": True,
    "nonfinite_open_spaces": True,
    "fractional_open_spaces": True,
    "zero_capacity": False,
    "open_exceeds_capacity": False,
    "exact_repeated_record": False,
    "ambiguous_allocation_requires_review": True,
    "conflicting_observation": True,
}

ANALYSIS_COLUMNS = {
    "record_id": "record_id",
    "facility": "facility",
    "category": "category",
    "qpass_subtype": "subtype",
    "level": "level",
    "location": "facility_raw",
    "type": "category_raw",
    "sub_type": "subtype_raw",
    "qpass_label_status": "label_status",
    "date": "observation_date",
    "observation_time": "observation_time",
    "observation_datetime": "observation_datetime",
    "academic_year": "academic_year",
    "quarter": "quarter",
    "open_spaces": "open_spaces",
    "selected_capacity": "selected_capacity",
    "capacity_source": "capacity_source",
    "capacity_acceptance_reason": "capacity_acceptance_reason",
    "capacity_assumption": "capacity_assumption",
    "fraction_available": "fraction_available",
    "quality_flag": "quality_flag",
    "qpass_source_issue": "qpass_source_issue",
    "inventory_coverage_status": "inventory_coverage_status",
    "duplicate_copies": "duplicate_copies",
    "source_file": "source_file",
    "sheet_name": "sheet_name",
    "source_row": "source_row",
    "format_version": "format_version",
}


def _key_frame(frame: pd.DataFrame) -> pd.DataFrame:
    """Return SOURCE_KEY columns in comparable types (string ids, midnight dates)."""
    key = pd.DataFrame(index=frame.index)
    for column in ["source_file", "sheet_name", "source_time_column"]:
        key[column] = frame[column].astype("string")
    key["source_row"] = pd.to_numeric(
        frame["source_row"], errors="coerce"
    ).astype("Int64")
    key["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    return key


def join_capacity(audited: pd.DataFrame, capacity: pd.DataFrame) -> pd.DataFrame:
    """Attach capacity selection to every audited observation, one-to-one.

    Args:
        audited: Output of validate_observations() on all workbooks.
        capacity: Combined capacity_comparison report from the capacity batch,
            read as strings (one row per QPASS source row and time slot).

    Returns:
        audited with capacity columns added. Observations with no capacity
        row (a workbook outside the capacity manifest) are kept with
        capacity_row_found False.

    Raises:
        ValueError: A key is duplicated on either side, a capacity row has no
            matching observation, or academic year/quarter disagree.
    """
    capacity = capacity.rename(columns={
        "qpass_source_file": "source_file", "qpass_source_sheet": "sheet_name",
        "qpass_source_row": "source_row", "observation_date": "date",
    })
    capacity["source_time_column"] = capacity.pop("observation_time").map(
        CAPACITY_TIME_TO_COLUMN
    )
    left, right = _key_frame(audited), _key_frame(capacity)
    for name, key in [("observation", left), ("capacity", right)]:
        if key.isna().any(axis=None):
            raise ValueError(f"{name} rows have incomplete source keys")
        if key.duplicated().any():
            raise ValueError(f"{name} source keys are not unique")
    extra = pd.concat([capacity.drop(columns=SOURCE_KEY).add_prefix("cap__"), right],
                      axis=1)
    joined = pd.concat([audited.drop(columns=SOURCE_KEY), left], axis=1).merge(
        extra, on=SOURCE_KEY, how="outer", validate="one_to_one", indicator=True,
    )
    orphans = joined["_merge"].eq("right_only")
    if orphans.any():
        raise ValueError(f"{int(orphans.sum())} capacity rows match no observation")
    joined["capacity_row_found"] = joined.pop("_merge").eq("both")
    found = joined["capacity_row_found"]
    for column in SHARED_COLUMNS:
        mismatch = found & joined[column].astype("string").ne(
            joined.pop(f"cap__{column}").astype("string")
        ).fillna(True)
        if mismatch.any():
            raise ValueError(f"{column} disagrees for {int(mismatch.sum())} rows")
    joined.columns = [c.removeprefix("cap__") for c in joined.columns]
    if len(joined) != len(audited):
        raise ValueError("Join changed the number of observations")
    return joined


def _quality_reasons(quality_flag: pd.Series) -> pd.Series:
    """List blocking quality flags per row; raise on flags without a policy."""
    flags = quality_flag.fillna("").str.split("|")
    seen = {flag for row in flags for flag in row} - {"", "pass"}
    unknown = seen - QUALITY_FLAG_BLOCKS.keys()
    if unknown:
        raise ValueError(f"No inclusion policy for quality flags: {sorted(unknown)}")
    return flags.map(lambda row: [f"quality:{f}" for f in row
                                  if QUALITY_FLAG_BLOCKS.get(f, False)])


def decide_inclusion(joined: pd.DataFrame) -> pd.DataFrame:
    """Decide analysis use per observation and deduplicate exact repeats.

    A row is included only when capacity selection accepted a capacity, the
    capacity step did not exclude it, no blocking quality flag is set, and
    open_spaces does not exceed the selected capacity. Values are never
    clipped or filled. Among included rows sharing one identity group, the
    copy with the smallest source key is kept; the others are excluded with
    duplicate_of pointing to it. Copies with different selected capacities are
    all excluded for review.

    Args:
        joined: Output of join_capacity().

    Returns:
        Copy with record_id, included, exclusion_reasons ('|'-joined),
        duplicate_of, duplicate_copies, and fraction_available.
    """
    result = joined.copy()
    result["record_id"] = (
        result["source_file"] + "|" + result["sheet_name"] + "|"
        + result["source_row"].astype("string") + "|"
        + result["date"].dt.strftime("%Y-%m-%d") + "|" + result["source_time_column"]
    )
    result["selected_capacity"] = pd.to_numeric(
        result["selected_capacity"], errors="coerce"
    ).astype("Int64")
    reasons = _quality_reasons(result["quality_flag"])
    found = result["capacity_row_found"]
    capacity_excluded = result["exclusion_reason"].fillna("").ne("")
    for index in result.index[~found]:
        reasons[index].append("capacity:not_in_capacity_manifest")
    for index in result.index[found & capacity_excluded]:
        reason = result.at[index, "exclusion_reason"]
        reasons[index].append(f"capacity_excluded:{reason}")
    unaccepted = found & ~capacity_excluded & result["selected_capacity"].isna()
    for index in result.index[unaccepted]:
        reasons[index].append(
            f"capacity_unresolved:{result.at[index, 'capacity_acceptance_reason']}"
        )
    exceeds = result["open_spaces"].gt(result["selected_capacity"]).fillna(False)
    for index in result.index[exceeds]:
        reasons[index].append("open_exceeds_selected_capacity")

    eligible = reasons.map(len).eq(0)
    result["duplicate_of"] = pd.Series(pd.NA, index=result.index, dtype="string")
    result["duplicate_copies"] = pd.Series(1, index=result.index, dtype="Int64")
    repeats = result.loc[eligible & result["observation_group"].notna()].sort_values(
        ["source_file", "sheet_name", "source_row", "date", "source_time_column"]
    )
    for _, group in repeats.groupby("observation_group", sort=False):
        if len(group) == 1:
            continue
        if group["selected_capacity"].nunique() > 1:
            for index in group.index:
                reasons[index].append("duplicate_capacity_disagreement")
            continue
        keeper = group.index[0]
        result.at[keeper, "duplicate_copies"] = len(group)
        for index in group.index[1:]:
            reasons[index].append("exact_repeat")
            result.at[index, "duplicate_of"] = result.at[keeper, "record_id"]

    result["exclusion_reasons"] = reasons.map("|".join).astype("string")
    result["included"] = result["exclusion_reasons"].eq("")
    result["fraction_available"] = (
        result["open_spaces"] / result["selected_capacity"]
    ).astype("Float64").where(result["included"])
    return result


def build_analysis_dataset(audit: pd.DataFrame) -> pd.DataFrame:
    """Select included rows and analysis columns in a deterministic order.

    Args:
        audit: Output of decide_inclusion().

    Returns:
        One row per usable observation with the ANALYSIS_COLUMNS names.
    """
    analysis = audit.loc[audit["included"], list(ANALYSIS_COLUMNS)].rename(
        columns=ANALYSIS_COLUMNS
    )
    return analysis.sort_values(
        ["observation_datetime", "facility", "category", "record_id"]
    ).reset_index(drop=True)


# Plain-language labels for exclusion reason codes, used in reports only.
REASON_LABELS = {
    "capacity_excluded:missing_open_spaces": "open-space reading left blank",
    "quality:missing_open_spaces": "open-space reading left blank",
    "capacity_excluded:invalid_open_spaces": "reading is not a valid count",
    "quality:unexpected_text_open_spaces": "reading is text, not a number",
    "quality:negative_open_spaces": "reading is negative",
    "quality:nonfinite_open_spaces": "reading is not a valid count",
    "quality:fractional_open_spaces": "reading is a fraction",
    "capacity_excluded:known_copied_non_observation":
        "known copied cell, not a real survey reading",
    "capacity_excluded:invalid_facility_or_category":
        "facility or permit category missing",
    "quality:missing_location": "facility missing",
    "quality:missing_type": "permit category missing",
    "quality:missing_observation_datetime": "survey date missing",
    "capacity_unresolved:label_mapping_unresolved":
        "facility or category name could not be matched",
    "capacity_unresolved:qpass_scope_conflict":
        "unclear which spaces the capacity covers (level, subtype or closure)",
    "capacity_unresolved:source_capacity_conflict":
        "capacity sources disagree for the same parking group",
    "capacity_unresolved:inventory_fallback_not_verified":
        "no capacity in QPASS and no matching Inventory capacity",
    "capacity_unresolved:qpass_zero_requires_review": "capacity recorded as 0",
    "capacity_unresolved:qpass_period_metadata_conflict":
        "survey date does not match its quarter",
    "capacity:not_in_capacity_manifest": "workbook not in the capacity manifest",
    "quality:conflicting_observation":
        "two different readings for the same spot and time",
    "quality:ambiguous_allocation_requires_review":
        "same spot and time listed with different capacities",
    "duplicate_capacity_disagreement":
        "duplicate copies were given different capacities",
    "open_exceeds_selected_capacity": "more open spaces than total capacity",
    "exact_repeat": "exact duplicate copy of a kept reading",
}

# Each excluded row is counted once, under the first group its reasons match.
REASON_GROUPS = [
    ("Reading blank or invalid", (
        "capacity_excluded:missing_open_spaces",
        "capacity_excluded:invalid_open_spaces",
        "capacity_excluded:known_copied_non_observation",
        "quality:missing_open_spaces", "quality:unexpected_text_open_spaces",
        "quality:negative_open_spaces", "quality:nonfinite_open_spaces",
        "quality:fractional_open_spaces",
    )),
    ("Facility, category or date missing", (
        "capacity_excluded:invalid_facility_or_category",
        "quality:missing_location", "quality:missing_type",
        "quality:missing_observation_datetime",
        "capacity_unresolved:label_mapping_unresolved",
    )),
    ("No trustworthy capacity", ("capacity_unresolved:", "capacity:")),
    ("Conflicting readings for the same spot and time", (
        "quality:conflicting_observation",
        "quality:ambiguous_allocation_requires_review",
        "duplicate_capacity_disagreement",
    )),
    ("More open spaces than capacity", ("open_exceeds_selected_capacity",)),
    ("Exact duplicate copy", ("exact_repeat",)),
]
TOP_REASONS_SHOWN = 3


def _removal_breakdown(audit: pd.DataFrame) -> pd.DataFrame:
    """Assign each excluded row one plain-language group and main reason.

    Args:
        audit: Output of decide_inclusion().

    Returns:
        One row per (group, reason) with row counts, in REASON_GROUPS order and
        then by count. Every excluded row is counted exactly once.
    """
    excluded = audit.loc[~audit["included"], "exclusion_reasons"].str.split("|")
    records = []
    for reasons in excluded:
        for group, prefixes in REASON_GROUPS:
            match = next((r for r in reasons if r.startswith(prefixes)), None)
            if match is not None:
                records.append((group, REASON_LABELS.get(match, match)))
                break
        else:
            records.append(("Other", reasons[0]))
    order = {group: i for i, (group, _) in enumerate(REASON_GROUPS)}
    breakdown = pd.DataFrame(records, columns=["group", "reason"]).value_counts()
    breakdown = breakdown.rename("rows").reset_index()
    breakdown["order"] = breakdown["group"].map(order).fillna(len(order))
    return breakdown.sort_values(["order", "rows"], ascending=[True, False]).drop(
        columns="order"
    ).reset_index(drop=True)


def summarize(audit: pd.DataFrame, loader_attrs: dict) -> dict:
    """Count processed, included, and excluded rows plus coverage tables.

    Args:
        audit: Output of decide_inclusion().
        loader_attrs: attrs of load_all_qpass() (files, skipped sheets/rows).

    Returns:
        Dict with totals, removed (plain-language breakdown counting each
        excluded row once), exclusion_reasons (rows per reason code; a row may
        have several), coverage_by_quarter, coverage_by_facility_quarter and
        coverage_by_facility frames.
    """
    reasons = audit["exclusion_reasons"].str.split("|").explode()
    reasons = reasons[reasons.ne("")].str.split(":").str[0:2].str.join(":")
    included = audit.loc[audit["included"]]
    by_quarter = audit.groupby(["academic_year", "quarter"], sort=False).agg(
        observations=("record_id", "size"), included=("included", "sum"),
    ).reset_index()
    by_facility = included.groupby(
        ["facility", "academic_year", "quarter"], dropna=False
    ).size().rename("included").reset_index()
    years = sorted(included["academic_year"].dropna().unique())
    return {
        "total_observations": len(audit),
        "included": int(audit["included"].sum()),
        "excluded": int((~audit["included"]).sum()),
        "exact_repeats_removed": int(audit["duplicate_of"].notna().sum()),
        "capacity_source_counts": included["capacity_source"].value_counts().to_dict(),
        "facilities": int(included["facility"].nunique()),
        "quarters": int(included[["academic_year", "quarter"]].drop_duplicates()
                        .shape[0]),
        "years": " to ".join(dict.fromkeys([years[0], years[-1]])) if years
        else "none",
        "files": loader_attrs.get("files", []),
        "skipped_sheets": loader_attrs.get("skipped_sheets", {}),
        "dropped_rows": loader_attrs.get("dropped_rows", {}),
        "removed": _removal_breakdown(audit),
        "exclusion_reasons": reasons.value_counts().rename_axis("reason")
        .rename("rows").reset_index(),
        "coverage_by_quarter": by_quarter,
        "coverage_by_facility_quarter": by_facility,
        "coverage_by_facility": by_facility.assign(
            period=by_facility["academic_year"] + " " + by_facility["quarter"]
        ).groupby("facility", dropna=False).agg(
            quarters=("period", "nunique"), included=("included", "sum"),
        ).reset_index(),
    }


def _result_lines(summary: dict) -> list[str]:
    """Return the plain-language result shared by the console and summary.md."""
    total, kept = summary["total_observations"], summary["included"]
    removed = summary["removed"]
    width = len(f"{total:,}")
    lines = [
        f"RESULT: {kept:,} usable parking readings ({kept / total:.1%} of "
        f"{total:,}).",
        "",
        "  Each row = how many spaces were open in one parking group (facility +",
        "  permit category, plus subtype/level when listed) at one survey time",
        "  (8am, 10am, 12pm or 2pm), with that group's capacity and",
        "  fraction_available = open_spaces / capacity (0 = full, 1 = empty).",
        f"  Covers {summary['facilities']} facilities over {summary['quarters']} "
        f"quarter(s), academic years {summary['years']}.",
        "",
        f"  How we got there, starting from {total:,} readings in the workbooks:",
    ]
    for group, _ in [*REASON_GROUPS, ("Other", ())]:
        rows = removed.loc[removed["group"].eq(group)]
        if group == "Other" and rows.empty:
            continue
        lines.append(f"    -{int(rows['rows'].sum()):>{width},}  {group}")
        for reason, count in rows[["reason", "rows"]].head(
            TOP_REASONS_SHOWN
        ).itertuples(index=False):
            lines.append(f"     {'':>{width}}    {count:,} {reason}")
        hidden = int(rows["rows"].iloc[TOP_REASONS_SHOWN:].sum())
        if hidden:
            lines.append(f"     {'':>{width}}    {hidden:,} other reasons "
                         "(codes in summary.md)")
    lines += [
        f"    ={kept:>{width},}  usable readings in the analysis dataset",
        "",
        "  Nothing was deleted: every reading, kept or not, is in audit.csv.gz",
        "  with the reason it was left out.",
    ]
    return lines


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a small DataFrame as a Markdown table without extra dependencies."""
    rows = [list(frame.columns), ["---"] * len(frame.columns),
            *frame.astype(str).to_numpy().tolist()]
    return "\n".join("| " + " | ".join(map(str, row)) + " |" for row in rows)


def _summary_markdown(summary: dict) -> str:
    """Render the summary dict as a short Markdown report."""
    counts = summary["capacity_source_counts"]
    sources = ", ".join(f"{k}: {v:,}" for k, v in counts.items())
    skipped = sum(len(v) for v in summary["skipped_sheets"].values())
    lines = [
        "# ParkSmart analysis dataset summary",
        "",
        "```text",
        *_result_lines(summary),
        "```",
        "",
        "## Load it",
        "",
        "```python",
        "import pandas as pd",
        'df = pd.read_csv("data/processed/pipeline/analysis_dataset.csv",',
        '                 parse_dates=["observation_date", "observation_datetime"])',
        "```",
        "",
        "Column definitions and the inclusion rules: `docs/pipeline.md`.",
        "",
        "## Files",
        "",
        "| File | Use it for |",
        "| --- | --- |",
        "| `analysis_dataset.csv` | EDA and modeling |",
        "| `audit.csv.gz` | Every reading, with `included` and "
        "`exclusion_reasons` |",
        "| `exclusion_reasons.csv` | Rows per exclusion reason code |",
        "| `coverage_by_facility_quarter.csv` | Usable rows per facility "
        "and quarter |",
        "| `loader_audit.json` | Sheets and rows the loader skipped |",
        "| `pipeline.log` | Full run log |",
        "",
        f"Capacity sources in the dataset: {sources or 'none'}. Workbooks "
        f"loaded: {len(summary['files'])}; non-data sheets skipped by the "
        f"loader: {skipped} (`loader_audit.json`).",
        "",
        "## Exclusion reason codes",
        "",
        "Rows per code as stored in `audit.csv.gz`; one row can have several. "
        "`quality:` comes from the observation checks, `capacity_excluded:` / "
        "`capacity_unresolved:` from capacity selection.",
        "",
        _markdown_table(summary["exclusion_reasons"]),
        "",
        "## Coverage by quarter",
        "",
        _markdown_table(summary["coverage_by_quarter"]),
        "",
        "## Coverage by facility",
        "",
        "Quarters with usable rows; per-quarter counts are in "
        "`coverage_by_facility_quarter.csv`.",
        "",
        _markdown_table(summary["coverage_by_facility"]),
        "",
        "## Limitations",
        "",
        "- QPASS covers mainly the first weeks of each quarter; several years "
        "and quarters are missing from the public archive.",
        "- capacity_source inventory_same_quarter assumes the Inventory "
        "capacity applies on every survey date of that quarter.",
        "- Quarters without an Inventory workbook rely on QPASS capacity only "
        "(see inventory_coverage_status).",
        "- fraction_available describes historical survey readings, not "
        "guaranteed live availability.",
        "",
    ]
    return "\n".join(lines)


def _console_summary(summary: dict, output_dir: Path, seconds: float) -> str:
    """Return the end-of-run report printed by the command line."""
    lines = ["", f"Done in {seconds:.0f}s.", "", *_result_lines(summary), ""]
    lines += [
        f"  Files in {output_dir}/",
        "    analysis_dataset.csv  use this for EDA and modeling",
        "    summary.md            read this first: counts, coverage, limitations",
        "    audit.csv.gz          every reading + why it was left out",
        "    pipeline.log          technical details from loading and matching",
    ]
    return "\n".join(lines)


def run_pipeline(qpass_dir: Path = RAW_QPASS_DIR,
                 manifest: Path = DEFAULT_MANIFEST,
                 inventory_dir: Path = DEFAULT_INVENTORY_DIR,
                 capacity_dir: Path = DEFAULT_CAPACITY_DIR,
                 output_dir: Path = DEFAULT_OUTPUT_DIR,
                 rebuild_inventory: bool = True) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Run the full workflow and write the analysis dataset, audit, and summary.

    Progress goes to this module's logger. The capacity batch's printed
    reports are written to capacity_dir/capacity_batch.log instead of stdout.

    Args:
        qpass_dir: Folder with the original QPASS workbooks.
        manifest: Inventory source manifest from src.download_inventory.
        inventory_dir: Folder for extracted Inventory capacity groups.
        capacity_dir: Interim folder for the capacity batch reports.
        output_dir: Folder for analysis_dataset.csv, audit.csv.gz,
            summary.md, exclusion_reasons.csv, coverage_by_facility_quarter.csv
            and loader_audit.json.
        rebuild_inventory: Re-extract Inventory groups from the workbooks.

    Returns:
        Tuple of (analysis dataset, audit table). Source workbooks are not
        modified.
    """
    started = time.perf_counter()
    qpass_dir, manifest, capacity_dir, output_dir = map(
        Path, (qpass_dir, manifest, capacity_dir, output_dir)
    )
    LOGGER.info("[1/4] Loading QPASS workbooks and checking observations...")
    loaded = load_all_qpass(qpass_dir)
    audited, _ = validate_observations(reshape_loaded_observations(loaded))
    LOGGER.info("[2/4] Standardizing labels and selecting capacities...")
    capacity_dir.mkdir(parents=True, exist_ok=True)
    batch_log = capacity_dir / "capacity_batch.log"
    with batch_log.open("w", encoding="utf-8") as handle, redirect_stdout(handle):
        run_capacity_matching(manifest, qpass_dir, inventory_dir, capacity_dir,
                              rebuild_inventory)
    capacity = pd.read_csv(capacity_dir / "combined" / "capacity_comparison.csv",
                           dtype=str, keep_default_na=False)
    LOGGER.info("[3/4] Joining and deciding which records are usable...")
    audit = decide_inclusion(join_capacity(audited, capacity))
    analysis = build_analysis_dataset(audit)
    summary = summarize(audit, loaded.attrs)

    LOGGER.info("[4/4] Writing outputs...")
    output_dir.mkdir(parents=True, exist_ok=True)
    analysis.to_csv(output_dir / "analysis_dataset.csv", index=False)
    audit.to_csv(output_dir / "audit.csv.gz", index=False)
    summary["exclusion_reasons"].to_csv(
        output_dir / "exclusion_reasons.csv", index=False
    )
    summary["coverage_by_facility_quarter"].to_csv(
        output_dir / "coverage_by_facility_quarter.csv", index=False
    )
    (output_dir / "loader_audit.json").write_text(
        json.dumps(loaded.attrs, indent=2, default=str), encoding="utf-8"
    )
    (output_dir / "summary.md").write_text(_summary_markdown(summary), encoding="utf-8")
    LOGGER.info(_console_summary(summary, output_dir, time.perf_counter() - started))
    return analysis, audit


def _configure_logging(log_path: Path) -> None:
    """Show only pipeline progress on screen; keep every message in log_path."""
    log_path.parent.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(name)s %(levelname)s %(message)s"))
    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("%(message)s"))
    console.addFilter(lambda record: record.name == __name__
                      or record.levelno >= logging.ERROR)
    logging.basicConfig(level=logging.INFO, handlers=[file_handler, console])
    # openpyxl warns about Excel features it ignores; they do not affect data.
    warnings.filterwarnings("ignore", category=UserWarning, module="openpyxl")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--qpass-dir", type=Path, default=RAW_QPASS_DIR)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--inventory-dir", type=Path, default=DEFAULT_INVENTORY_DIR)
    parser.add_argument("--capacity-dir", type=Path, default=DEFAULT_CAPACITY_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--reuse-inventory", action="store_true",
                        help="Use previously extracted Inventory groups")
    args = parser.parse_args()
    _configure_logging(args.output_dir / "pipeline.log")
    run_pipeline(args.qpass_dir, args.manifest, args.inventory_dir,
                 args.capacity_dir, args.output_dir, not args.reuse_inventory)
