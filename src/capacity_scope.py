"""Flag QPASS levels whose Inventory capacity scope is unverified."""

import pandas as pd


def apply_scope_review(results):
    """Flag level-specific comparisons while preserving original differences.

    Args:
        results: Joined observations with capacity comparison columns.

    Returns:
        A copy with scope-review flags for level-specific QPASS records.
    """
    results = results.copy()

    level = (
        results["qpass_level_raw"]
        .fillna("")
        .astype("string")
        .str.strip()
    )
    review = level.ne("") & results["_merge"].eq("both")

    results["capacity_scope_status"] = "scope_unverified"
    results.loc[review, "capacity_scope_status"] = "level_scope_review"

    results["reported_capacity_difference_raw"] = (
        results["capacity_difference"]
    )
    results.loc[review, "capacity_difference"] = float("nan")
    results.loc[
        review, "reported_capacity_comparison"
    ] = "scope_review_required"

    promote = review & results["comparison_status"].isin([
        "historical_verification_required",
        "open_spaces_exceed_candidate",
    ])
    results.loc[promote, "comparison_status"] = "level_scope_review"

    return results