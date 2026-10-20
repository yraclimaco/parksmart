"""Compare representative QPASS records with Inventory candidates."""

import argparse
import math
from pathlib import Path

import pandas as pd
from src.qpass_loader import load_qpass
from src.capacity_acceptance import apply_capacity_acceptance
from src.capacity_labels import label_inventory, label_qpass, invalid_identifier
import json


KEYS = ["academic_year", "quarter", "facility", "category"]


def _numeric_status(value):
    """Classify a raw count without treating missing or zero as verified."""
    if pd.isna(value) or str(value).strip() == "":
        return "missing"
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return "invalid_numeric"
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        return "invalid_capacity"
    if number == 0:
        return "zero_review"
    return "positive_unverified"


def audit_reported_capacities(results):
    """Compare reported totals with unambiguous Inventory candidates.

    Args:
        results: Joined observations containing qpass_capacity_raw,
            candidate_capacity, inventory_group_count, and _merge columns.

    Returns:
        A copy with numeric totals, validity flags, a comparison flag, and
        QPASS-minus-Inventory differences. Agreement does not verify history
        or establish that category scopes are equivalent.
    """
    results = results.copy()
    results["qpass_capacity_status"] = results["qpass_capacity_raw"].map(
        _numeric_status
    )
    results["qpass_capacity_numeric"] = pd.to_numeric(
        results["qpass_capacity_raw"], errors="coerce"
    )
    inventory_status = results["candidate_capacity"].map(_numeric_status)
    comparable = (
        results["_merge"].eq("both")
        & results["inventory_group_count"].eq(1)
        & inventory_status.eq("positive_unverified")
        & results["qpass_capacity_status"].eq("positive_unverified")
    )
    results["reported_capacity_comparison"] = "not_comparable"
    difference = (
        results["qpass_capacity_numeric"] - results["candidate_capacity"]
    )
    results["capacity_difference"] = difference.where(comparable)
    results.loc[
        comparable & difference.eq(0), "reported_capacity_comparison"
    ] = "agree_unverified"
    results.loc[
        comparable & difference.ne(0), "reported_capacity_comparison"
    ] = "conflict"
    return results



def build_candidates(inventory):
    """Group standardized keys without summing ambiguous capacities or raw labels."""
    inventory = label_inventory(inventory)
    columns = [*KEYS, "inventory_group_count", "inventory_source_file",
               "inventory_source_rows", "inventory_facility_raw_values",
               "inventory_category_raw_values", "inventory_capacity_raw_values",
               "inventory_capacity_statuses", "inventory_source_groups_json",
               "inventory_subtype", "inventory_time_limit_raw",
               "inventory_single_capacity_status", "inventory_period_metadata_conflict",
               "inventory_label_unresolved", "candidate_capacity"]
    rows = []
    for key, group in inventory.groupby(KEYS, dropna=False, sort=False):
        row = dict(zip(KEYS, key))
        single = len(group) == 1
        row.update({
            "inventory_group_count": len(group),
            "inventory_source_file": ";".join(group.source_file.astype(str).unique()),
            "inventory_source_rows": ";".join(group.source_rows.astype(str)),
            "inventory_facility_raw_values": group.facility_raw.tolist(),
            "inventory_category_raw_values": group.category_raw.tolist(),
            "inventory_capacity_raw_values": group.get(
                "capacity_raw_values", group.capacity
            ).tolist(),
            "inventory_capacity_statuses": group.get(
                "capacity_status", pd.Series("", index=group.index)
            ).tolist(),
            "inventory_source_groups_json": json.dumps(group.to_dict("records"), default=str),
            "inventory_subtype": group.subtype.iloc[0] if single else "",
            "inventory_time_limit_raw": group.get(
                "time_limit_raw", pd.Series("", index=group.index)
            ).iloc[0] if single else "",
            "inventory_single_capacity_status": group.get(
                "capacity_status", pd.Series("", index=group.index)
            ).iloc[0] if single else "multiple_inventory_groups_review",
            "inventory_period_metadata_conflict": group.get(
                "capacity_status", pd.Series("", index=group.index)
            ).eq("period_metadata_review").any(),
            "inventory_label_unresolved": group.label_status.eq("unresolved").any(),
            "candidate_capacity": group.capacity.iloc[0] if single else pd.NA,
        })
        rows.append(row)
    return pd.DataFrame(rows, columns=columns)


def summarize_results(results):
    """Return quarter and overall summaries with identical count/rate meanings."""
    def counts(frame):
        eligible = frame.exclusion_reason.eq("")
        selected = frame.selected_capacity.notna() & eligible
        total = int(eligible.sum())
        qpass = int((selected & frame.capacity_source.eq("qpass")).sum())
        inventory = int((selected & frame.capacity_source.eq("inventory_same_quarter")).sum())
        exact = int((eligible & frame.exact_key_found).sum())
        return {
            "total_observation_slots": len(frame),
            "eligible_observation_slots": total,
            "excluded_observation_slots": len(frame) - total,
            "exact_key_candidates": exact,
            "accepted_qpass_capacities": qpass,
            "accepted_inventory_capacities": inventory,
            "accepted_capacity_matches": qpass + inventory,
            "exact_key_candidate_rate": exact / total if total else float("nan"),
            "accepted_qpass_capacity_rate": qpass / total if total else float("nan"),
            "accepted_inventory_capacity_rate": inventory / total if total else float("nan"),
            "accepted_capacity_match_rate": (qpass + inventory) / total if total else float("nan"),
        }
    rows = [dict(zip(["academic_year", "quarter"], key), **counts(group))
            for key, group in results.groupby(["academic_year", "quarter"], dropna=False)]
    columns = ["academic_year", "quarter", *counts(results)]
    return pd.DataFrame(rows, columns=columns), pd.DataFrame([counts(results)])


def _blank(values):
    return values.isna() | values.astype("string").str.strip().eq("").fillna(False)


def compare_capacities(inventory_path, qpass_path,
                       output_dir=Path("results/capacity_matching")):
    """Load, label, join, select, and audit capacity without editing source files.

    Return the complete observation DataFrame and write detailed/summary CSVs.
    Inventory joins use academic year, quarter, standardized facility/category;
    a separate scope check prevents whole-facility or broad-subtype fallback.
    """
    inventory = pd.read_csv(inventory_path, dtype={"facility_raw": "string",
                                                  "category_raw": "string"},
                            keep_default_na=False)
    candidates = build_candidates(inventory)
    qpass = load_qpass(Path(qpass_path))
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "qpass_loader_audit.json").write_text(
        json.dumps(qpass.attrs, indent=2, default=str), encoding="utf-8"
    )
    labeled = label_qpass(qpass)
    observations = []
    for _, row in labeled.iterrows():
        for time, column in {"8am": "open_8am", "10am": "open_10am",
                             "12pm": "open_12pm", "2pm": "open_2pm"}.items():
            observation = {
                name: row[name] for name in KEYS
            }
            observation.update({
                "qpass_facility_raw": row.location, "qpass_category_raw": row.type,
                "qpass_subtype_raw": row.sub_type, "qpass_subtype": row.subtype,
                "qpass_level_raw": row.level,
                "qpass_facility_status": row.facility_status,
                "qpass_category_status": row.category_status,
                "qpass_label_status": row.label_status, "qpass_label_notes": row.label_notes,
                "label_unresolved": row.label_status == "unresolved",
                "observation_date": row.date, "observation_time": time,
                "open_spaces_raw": row[column], "qpass_capacity_raw": row.total_stall_count,
                "qpass_source_file": row.source_file, "qpass_source_sheet": row.sheet_name,
                "qpass_source_row": row.source_row,
                "qpass_raw_structure": row.get("raw_structure", ""),
                "qpass_source_record_json": json.dumps(
                    {k: row[k] for k in qpass.columns}, default=str
                ),
                "qpass_formula_error": row.get("qpass_formula_error", False),
                "qpass_scope_issue": row.get("qpass_scope_issue", False),
            })
            observations.append(observation)
    # Explicit columns also support a workbook yielding no valid dated rows.
    if not observations:
        raise ValueError(f"No dated QPASS source rows in {qpass_path}; inspect loader audit")
    results = pd.DataFrame(observations).merge(
        candidates, on=KEYS, how="left", validate="many_to_one", indicator=True
    )
    results["candidate_capacity"] = pd.to_numeric(results.candidate_capacity, errors="coerce")
    results["inventory_scope_compatible"] = (
        results._merge.eq("both") & results.inventory_group_count.eq(1)
        & _blank(results.qpass_level_raw)
        & results.qpass_subtype.fillna("").eq(results.inventory_subtype.fillna(""))
        & _blank(results.inventory_time_limit_raw)
        & ~results.inventory_label_unresolved.eq(True)
    )
    results = audit_reported_capacities(results)
    results["reported_capacity_difference_raw"] = results.capacity_difference
    scope_mismatch = results._merge.eq("both") & ~results.inventory_scope_compatible
    results.loc[scope_mismatch, "reported_capacity_comparison"] = "scope_review_required"
    results.loc[scope_mismatch, "capacity_difference"] = float("nan")
    results["capacity_scope_status"] = "exact_group"
    results.loc[scope_mismatch, "capacity_scope_status"] = "inventory_scope_review"

    opened = pd.to_numeric(results.open_spaces_raw, errors="coerce")
    invalid_id = invalid_identifier(results.facility) | invalid_identifier(results.category)
    missing = _blank(results.open_spaces_raw)
    invalid = opened.isna() | opened.lt(0) | opened.ge(float("inf")) | opened.mod(1).ne(0)
    results["exclusion_reason"] = ""
    results.loc[invalid, "exclusion_reason"] = "invalid_open_spaces"
    results.loc[missing, "exclusion_reason"] = "missing_open_spaces"
    results.loc[invalid_id, "exclusion_reason"] = "invalid_facility_or_category"

    # Source errors documented in docs/qpass_schema_audit.md, not naming errors.
    fall_formula = (
        results.qpass_source_file.eq("QPASS 2025-2026-2 Fall.xlsm")
        & results.academic_year.eq("2025-2026") & results.quarter.eq("Fall")
        & pd.to_numeric(results.qpass_capacity_raw, errors="coerce").eq(0)
    )
    results["qpass_source_issue"] = ""
    results.loc[fall_formula, "qpass_formula_error"] = True
    results.loc[fall_formula, "qpass_source_issue"] = "fall_2025_zero_capacity_formula"
    copied = (fall_formula & results.facility.eq("P604") & results.category.eq("B")
              & pd.to_numeric(results.qpass_source_row, errors="coerce").eq(89)
              & results.qpass_source_sheet.str.contains(r"\b(?:Week\s*|W)1\b", case=False, regex=True)
              & pd.to_datetime(results.observation_date).eq(pd.Timestamp("2025-09-29"))
              & results.observation_time.isin(["12pm", "2pm"]))
    results.loc[copied & ~invalid_id, "exclusion_reason"] = "known_copied_non_observation"
    closure = results.qpass_raw_structure.astype("string").str.contains(
        r"\bclosed\b", case=False, regex=True, na=False
    ) | results.category.eq("Closure").fillna(False)
    # QPASS with no subtype cannot resolve multiple Inventory subtype groups.
    ambiguous = (results.inventory_group_count.gt(1) & _blank(results.qpass_level_raw)
                 & _blank(results.qpass_subtype_raw))
    results["qpass_scope_issue"] = (
        results.qpass_scope_issue.astype("string").str.lower().isin(["true", "1", "yes"])
        | closure | ambiguous
    )
    results["exact_key_found"] = results._merge.eq("both") & ~invalid_id
    results["open_spaces_exceed_candidate"] = (
        results.inventory_scope_compatible & opened.gt(results.candidate_capacity)
    )
    results = apply_capacity_acceptance(results)
    results["comparison_status"] = "no_exact_inventory_key"
    results.loc[results.exact_key_found, "comparison_status"] = "inventory_candidate_review"
    results.loc[ambiguous, "comparison_status"] = "subtype_mapping_required"
    results.loc[scope_mismatch & ~ambiguous, "comparison_status"] = "inventory_scope_review"
    accepted = results.selected_capacity.notna()
    results.loc[accepted, "comparison_status"] = "accepted_" + results.loc[accepted, "capacity_source"]
    results["unresolved_type"] = "inventory_key_unmatched"
    results.loc[results.exact_key_found, "unresolved_type"] = "inventory_capacity_review"
    results.loc[results.inventory_single_capacity_status.eq("period_metadata_review")
                | results.inventory_period_metadata_conflict.eq(True),
                "unresolved_type"] = "period_metadata_conflict"
    results.loc[scope_mismatch | results.qpass_scope_issue, "unresolved_type"] = "scope_conflict"
    results.loc[results.label_unresolved & ~closure & ~invalid_id,
                "unresolved_type"] = "mapping_review"
    results.loc[results.qpass_source_issue.ne(""), "unresolved_type"] = "source_data_problem"
    results.loc[results.group_capacity_conflict & ~results.qpass_scope_issue,
                "unresolved_type"] = "capacity_conflict"
    results.loc[results.exclusion_reason.ne(""), "unresolved_type"] = "invalid_observation"
    results.loc[invalid_id, "unresolved_type"] = "invalid_identifier"
    results.loc[accepted, "unresolved_type"] = ""
    actions = {
        "inventory_key_unmatched": "Review the same-quarter Inventory group; do not guess aliases.",
        "inventory_capacity_review": "Review original Inventory counts, duplicates and formula caches.",
        "period_metadata_conflict": "Resolve the Inventory cover/selector period disagreement.",
        "scope_conflict": "Verify exact level, subtype and restrictions; do not substitute broad totals.",
        "mapping_review": "Review remaining Issue #3 label decisions and source evidence.",
        "source_data_problem": "Inspect QPASS source formulas; preserve the original value and verify fallback scope.",
        "capacity_conflict": "Resolve contradictory counts using source evidence; do not overwrite QPASS.",
        "invalid_observation": "Review the missing/invalid reading; other valid readings remain eligible.",
        "invalid_identifier": "Recover the source facility/category identifier before matching.",
    }
    results["recommended_next_step"] = results.unresolved_type.map(actions).fillna(
        "No unresolved selection; retain documented assumptions and source warnings."
    )
    results["unresolved_reason"] = (
        results.unresolved_type + "; " + results.capacity_acceptance_reason
        + "; qpass_capacity=" + results.qpass_capacity_status
        + "; inventory=" + results.inventory_single_capacity_status.fillna("")
    )
    results.loc[accepted, "unresolved_reason"] = ""
    summary, overall = summarize_results(results)
    reports = {
        "capacity_comparison": results,
        "matched_records": results.loc[accepted],
        "unresolved_cases": results.loc[~accepted],
        "unmatched_records": results.loc[~results.exact_key_found],
        "conflicting_records": results.loc[results.group_capacity_conflict
            | results.reported_capacity_comparison.eq("conflict")
            | results.open_spaces_exceed_candidate],
    }
    for name, frame in reports.items():
        frame.to_csv(output_dir / f"{name}.csv", index=False)
    summary.to_csv(output_dir / "quarter_summary.csv", index=False)
    overall.to_csv(output_dir / "overall_summary.csv", index=False)
    print(overall.to_string(index=False))
    print(f"Reports saved in: {output_dir}")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inventory", required=True, type=Path)
    parser.add_argument("--qpass", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("results/capacity_matching"))
    args = parser.parse_args()
    compare_capacities(args.inventory, args.qpass, args.output_dir)
