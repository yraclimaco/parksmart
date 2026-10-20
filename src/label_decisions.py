"""Apply explicit label decisions without changing raw labels or provenance."""

import json
import logging
from pathlib import Path

import pandas as pd
from .labels import format_label, format_labels, format_category, TIMED_CATEGORY_SUFFIX

DEFAULT_CATEGORY_ALIASES = (
    Path(__file__).resolve().parents[1] / "config" / "category_aliases.json"
)
DEFAULT_CATEGORY_REVIEW = DEFAULT_CATEGORY_ALIASES.with_name(
    "category_review_decisions.json"
)
FIELDS = ("facility", "category", "subtype")
LOGGER = logging.getLogger(__name__)


def standardize_labels(records, mappings=None):
    """Format labels, apply field-specific decisions, and flag the audited row.

    Args:
        records: Loader-adapted table containing the three raw label columns.
        mappings: Optional dictionary of field names to decision dictionaries
            with raw_value, standard_value, status, and notes. If omitted, use
            the repository's verified category aliases and unresolved review decisions.

    Returns:
        Copy with cleaned labels, per-field statuses, label_status, and reasons.
        Missing facility/category and numeric zero are unresolved. Missing
        subtype alone is allowed. Known unresolved facility is cleared only in
        the cleaned column; loader location and all original cells are retained.
        Precedence: unresolved, keep_separate, standardized, unchanged.
        Unlisted nonmissing labels are preserved; unchanged is not verification.
        keep_separate preserves restricted categories/subtypes for downstream
        eligibility checks; it does not grant permission to use those spaces.
        More-specific scopes win over general decisions, regardless of list
        order. Equal-specificity decisions retain their configured order.
        attrs["summer_2019_check"] reports whether the guarded check ran;
        missing guard columns also produce a warning in the module logger.
    """
    if mappings is None:
        mappings = {
            "facility": json.loads(
                DEFAULT_CATEGORY_ALIASES.with_name("facility_aliases.json").read_text()
            ),
            "category": (
                json.loads(DEFAULT_CATEGORY_ALIASES.read_text())
                + json.loads(DEFAULT_CATEGORY_REVIEW.read_text())
            ),
        }
    result = format_labels(records)
    result["label_notes"] = ""
    for field in FIELDS:
        raw = result[f"{field}_raw"].astype("string")
        clean = result[field].astype("string")
        same = raw.eq(clean).fillna(False) | (raw.isna() & clean.isna())
        result[f"{field}_status"] = same.map({True: "unchanged", False: "standardized"})
        # A modifier is not an alias: retain the complete visitor label.
        # This conservative distinction does not interpret eligibility rules.
        if field == "category":
            visitor = clean.str.contains(
                r"\bvisitor\b", case=False, regex=True, na=False
            )
            qualified = visitor & clean.str.casefold().ne("visitor").fillna(False)
            timed = clean.map(
                lambda value: (
                    bool(TIMED_CATEGORY_SUFFIX.fullmatch(value))
                    if pd.notna(value)
                    else False
                )
            )
            restricted_wording = clean.str.contains(
                r"\b(?:physician|reserved|accessible|carpool|electric[ -]vehicle)\b",
                case=False,
                regex=True,
                na=False,
            )
            enforced_a = clean.str.fullmatch(
                r"(?:24/7 A|A \(24/7\)|A 24/7 Enforced)", case=False, na=False
            )
            two_person_carpool = clean.eq("2 Person Carpool").fillna(False)
            qualified = (
                qualified | timed | restricted_wording | enforced_a | two_person_carpool
            )
            result.loc[qualified, "category_status"] = "keep_separate"
            result.loc[
                qualified, "label_notes"
            ] += "category: explicit restriction retained separately; "
        if field == "subtype":
            qualified = clean.notna()
            result.loc[qualified, "subtype_status"] = "keep_separate"
            result.loc[
                qualified, "label_notes"
            ] += "subtype: populated subtype retained separately; "
        seen = set()
        applied = pd.Series(False, index=result.index)
        # Match the original formatted value, then let the most-specific
        # matching scope win. JSON list order cannot override a scoped fix.
        decisions = sorted(
            mappings.get(field, []),
            key=lambda decision: len(decision.get("scope", {})),
            reverse=True,
        )
        for decision in decisions:
            formatter = format_category if field == "category" else format_label
            key = formatter(decision["raw_value"])
            decision_key = (key, tuple(sorted(decision.get("scope", {}).items())))
            if pd.isna(key) or decision_key in seen:
                raise ValueError(f"Invalid or duplicate {field} decision: {key!r}")
            seen.add(decision_key)
            status = decision["status"]
            if status not in {"verified", "keep_separate", "unresolved"}:
                raise ValueError(f"Invalid decision status: {status}")
            mask = clean.eq(key).fillna(False) & ~applied
            for column, expected in decision.get("scope", {}).items():
                if column not in result:
                    raise ValueError(f"Decision scope column missing: {column}")
                mask &= (
                    result[column]
                    .map(format_label)
                    .eq(format_label(expected))
                    .fillna(False)
                )
            target = formatter(decision["standard_value"])
            if status != "unresolved" and pd.isna(target):
                raise ValueError("Resolved decisions require a standard value")
            if status == "keep_separate" and target != key:
                raise ValueError("keep_separate must preserve the formatted label")
            applied |= mask
            result.loc[mask, field] = target
            mapped_status = {
                "verified": "standardized",
                "keep_separate": "keep_separate",
                "unresolved": "unresolved",
            }[status]
            # Alias resolution must not erase a preserved restriction status.
            if status == "verified":
                target_is_timed = (
                    field == "category"
                    and pd.notna(target)
                    and bool(TIMED_CATEGORY_SUFFIX.fullmatch(target))
                )
                preserve_restriction = mask & (
                    result[f"{field}_status"].eq("keep_separate") | target_is_timed
                )
                result.loc[mask, f"{field}_status"] = mapped_status
                result.loc[preserve_restriction, f"{field}_status"] = "keep_separate"
            else:
                result.loc[mask, f"{field}_status"] = mapped_status
            result.loc[mask, "label_notes"] += field + ": " + decision["notes"] + "; "
        if field in {"facility", "category"}:
            # Excel/pandas can represent the same zero identifier as 0 or 0.0.
            # Check its numeric value without changing the raw or cleaned text.
            zero_identifier = pd.to_numeric(result[field], errors="coerce").eq(0)
            unknown = result[field].isna() | zero_identifier.fillna(False)
            result.loc[unknown, f"{field}_status"] = "unresolved"
            result.loc[unknown, "label_notes"] += (
                field + ": missing or zero identifier; "
            )

    # Closure applies only to the dated source record, not the facility forever.
    # Retain the original wording in category_raw and override any alias.
    closure = (
        result["category_raw"]
        .astype("string")
        .str.contains(r"\bclosed\b", case=False, regex=True, na=False)
    )
    result.loc[closure, "category"] = "Closure"
    result.loc[closure, "category_status"] = "unresolved"
    result.loc[
        closure, "label_notes"
    ] += "category: closure label for this source record and survey time only; do not treat as usable parking or infer permanent facility closure; "

    # The shared loader reconstructs this row as Pangea. Ownership is not
    # established: use workbook + week + source row and original-cell guards.
    required = {
        "source_file",
        "sheet_name",
        "source_row",
        "raw_structure",
        "raw_lot",
        "total_stall_count",
    }
    missing = sorted(required.difference(result.columns))
    result.attrs["summer_2019_check"] = {
        "status": "skipped_missing_columns" if missing else "checked",
        "missing_columns": missing,
        "matched_records": None,
    }
    if missing:
        LOGGER.warning(
            "Summer 2019 ownership check skipped; missing required columns: %s",
            ", ".join(missing),
        )
    else:

        def blank(col):
            return col.isna() | col.astype("string").str.strip().eq("").fillna(False)

        uncertain = (
            result["source_file"].eq("QPASS 2019-2020-1 Summer.xlsx")
            & result["sheet_name"]
            .astype("string")
            .str.contains(r"\b(?:W|Week\s*)2\b", case=False, regex=True, na=False)
            & result["source_row"].eq(101)
            & blank(result["raw_structure"])
            & blank(result["raw_lot"])
            & result["category_raw"].map(format_label).eq("V").fillna(False)
            & pd.to_numeric(result["total_stall_count"], errors="coerce").eq(9)
        )
        result.attrs["summer_2019_check"]["matched_records"] = int(uncertain.sum())
        result.loc[uncertain, "facility"] = pd.NA
        result.loc[uncertain, "facility_status"] = "unresolved"
        result.loc[uncertain, "label_notes"] += (
            "facility: unnamed 9-space V row after Pangea; ownership unresolved. "
            "Evidence: docs/qpass_schema_audit.md, Known data issues; "
        )
    statuses = result[[f"{field}_status" for field in FIELDS]]
    result["label_status"] = "unchanged"
    for status in ("standardized", "keep_separate", "unresolved"):
        result.loc[statuses.eq(status).any(axis=1), "label_status"] = status
    return result
