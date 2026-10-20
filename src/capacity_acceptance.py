"""Select valid QPASS capacities first, then unambiguous same-quarter Inventory."""

import pandas as pd

from src.capacity_labels import invalid_identifier


KEYS = ["academic_year", "quarter", "facility", "category"]


def _column(frame, name, default=""):
    return frame.get(name, pd.Series(default, index=frame.index))


def _positive_integer(values):
    values = pd.to_numeric(values, errors="coerce")
    return values.gt(0) & values.lt(float("inf")) & values.mod(1).eq(0)


def _truth(values):
    return values.astype("string").str.casefold().isin(["true", "1", "yes"])


def apply_capacity_acceptance(results):
    """Select capacity per eligible observation and retain evidence and assumptions.

    QPASS capacities are trusted for their source row's exact group unless known
    errors, ambiguous group totals, comparable contradictory Inventory, or counts
    above capacity make them unsafe. Missing/invalid readings never contribute
    to group conflicts. Different levels and subtypes are separate groups.

    Only missing or demonstrably broken QPASS capacities can fall back to a
    positive, unique, scope-compatible, consistent-period Inventory candidate.
    A zero alone is unverified, not proof of a formula error. Fallback explicitly
    assumes capacity is applicable within that same academic year and quarter.
    No same-day requirement or cross-quarter fill is used.
    """
    result = results.copy()
    for name in ("selected_capacity", "matched_capacity"):
        result[name] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["capacity_source"] = "unknown"
    result["capacity_acceptance_status"] = "unresolved"
    result["capacity_acceptance_reason"] = "capacity_evidence_required"
    result["capacity_acceptance_basis"] = ""
    result["capacity_assumption"] = ""
    result["group_capacity_conflict"] = False
    if result.empty:
        return result
    required = [*KEYS, "qpass_capacity_raw", "open_spaces_raw",
                "observation_date", "exclusion_reason"]
    if not all(name in result for name in required):
        return result

    eligible = result.exclusion_reason.eq("")
    reported = pd.to_numeric(result.qpass_capacity_raw, errors="coerce")
    capacity = pd.to_numeric(_column(result, "candidate_capacity"), errors="coerce")
    opened = pd.to_numeric(result.open_spaces_raw, errors="coerce")
    positive = _positive_integer(reported)
    inventory_positive = _positive_integer(capacity)
    formula_error = _truth(_column(result, "qpass_formula_error", False))
    scope_issue = _truth(_column(result, "qpass_scope_issue", False))
    label_issue = _truth(_column(result, "label_unresolved", False))
    invalid_id = invalid_identifier(result.facility) | invalid_identifier(result.category)
    eligible &= ~invalid_id
    inventory_usable = (
        _column(result, "inventory_group_count", 0).eq(1)
        & _column(result, "inventory_scope_compatible", False).eq(True)
        & _column(result, "inventory_single_capacity_status").eq("positive_unverified")
        & inventory_positive & _column(result, "_merge").eq("both")
        & ~_truth(_column(result, "inventory_period_metadata_conflict", False))
        & ~_truth(_column(result, "inventory_label_unresolved", False))
    )
    # A broad facility total is never compared with a single level/subtype.
    disagreement = inventory_usable & positive & reported.ne(capacity) & ~formula_error
    own_count_conflict = positive & opened.gt(reported) & ~formula_error
    inventory_count_conflict = inventory_usable & opened.gt(capacity)

    group = result[KEYS].copy()
    for name in ("qpass_level_raw", "qpass_subtype"):
        group[name] = _column(result, name).fillna("").astype("string").str.strip()
    group["date"] = pd.to_datetime(result.observation_date, errors="coerce").dt.normalize()
    group_keys = list(group.columns)
    group["capacity"] = reported.where(eligible & positive & ~formula_error)
    group["conflict"] = eligible & (
        disagreement | own_count_conflict | inventory_count_conflict
    )
    grouped = group.groupby(group_keys, dropna=False)
    blocked = grouped["conflict"].transform("any") | (
        grouped["capacity"].transform("nunique").gt(1)
    )
    result["group_capacity_conflict"] = blocked & eligible
    valid = eligible & ~scope_issue & ~label_issue & ~blocked
    qpass_ok = valid & positive & ~formula_error
    raw = result.qpass_capacity_raw.astype("string").str.strip()
    missing = raw.isna() | raw.str.casefold().isin(["", "nan", "none", "na", "n/a"])
    demonstrably_broken = formula_error | reported.lt(0) | (
        reported.notna() & (~reported.lt(float("inf")) | reported.mod(1).ne(0))
    ) | (reported.isna() & ~missing)
    inventory_ok = valid & (missing | demonstrably_broken) & inventory_usable
    accepted = qpass_ok | inventory_ok
    result.loc[qpass_ok, "selected_capacity"] = reported[qpass_ok].astype("Int64")
    result.loc[inventory_ok, "selected_capacity"] = capacity[inventory_ok].astype("Int64")
    result["matched_capacity"] = result.selected_capacity.copy()
    result.loc[qpass_ok, "capacity_source"] = "qpass"
    result.loc[inventory_ok, "capacity_source"] = "inventory_same_quarter"
    result.loc[accepted, "capacity_acceptance_status"] = "accepted"
    result.loc[qpass_ok, "capacity_acceptance_reason"] = "valid_qpass_exact_group"
    result.loc[inventory_ok, "capacity_acceptance_reason"] = "assumed_same_quarter_capacity"
    result.loc[accepted, "capacity_acceptance_basis"] = result.loc[
        accepted, "capacity_acceptance_reason"
    ]
    result.loc[inventory_ok, "capacity_assumption"] = (
        "Assumed same-quarter capacity for the exact parking group; "
        "Inventory does not establish capacity on every survey date."
    )
    # Reasons remain diagnostic for unaccepted rows; source errors are also kept
    # independently, including when an Inventory fallback is selected.
    unresolved = ~accepted
    result.loc[unresolved & reported.eq(0), "capacity_acceptance_reason"] = "qpass_zero_requires_review"
    result.loc[unresolved & (missing | demonstrably_broken), "capacity_acceptance_reason"] = "inventory_fallback_not_verified"
    result.loc[unresolved & label_issue, "capacity_acceptance_reason"] = "label_mapping_unresolved"
    result.loc[unresolved & scope_issue, "capacity_acceptance_reason"] = "qpass_scope_conflict"
    result.loc[unresolved & blocked, "capacity_acceptance_reason"] = "source_capacity_conflict"
    result.loc[~eligible, "capacity_acceptance_reason"] = "excluded_observation"
    return result
