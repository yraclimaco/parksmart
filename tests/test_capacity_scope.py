"""Scope safeguards for historical capacity comparisons."""

import unittest

import pandas as pd

from src.capacity_scope import apply_scope_review


class TestCapacityScope(unittest.TestCase):
    def record(self, **changes):
        row = {
            "qpass_level_raw": "Level 3",
            "_merge": "both",
            "capacity_difference": -179.0,
            "reported_capacity_comparison": "conflict",
            "comparison_status": "historical_verification_required",
        }
        return pd.DataFrame([{**row, **changes}])

    def test_level_comparison_requires_review(self):
        original = self.record()
        result = apply_scope_review(original)
        self.assertEqual(result.loc[0, "capacity_scope_status"], "level_scope_review")
        self.assertEqual(result.loc[0, "reported_capacity_comparison"],
                         "scope_review_required")
        self.assertEqual(result.loc[0, "comparison_status"], "level_scope_review")
        self.assertTrue(pd.isna(result.loc[0, "capacity_difference"]))
        self.assertEqual(result.loc[0, "reported_capacity_difference_raw"], -179)
        self.assertEqual(original.loc[0, "reported_capacity_comparison"], "conflict")

    def test_equal_totals_do_not_prove_equal_scope(self):
        result = apply_scope_review(self.record(
            capacity_difference=0, reported_capacity_comparison="agree_unverified",
        ))
        self.assertEqual(result.loc[0, "reported_capacity_comparison"],
                         "scope_review_required")

    def test_blank_levels_keep_existing_comparison(self):
        for level in (None, "", "  "):
            with self.subTest(level=level):
                result = apply_scope_review(self.record(qpass_level_raw=level))
                self.assertEqual(result.loc[0, "reported_capacity_comparison"], "conflict")

    def test_missing_key_is_not_a_level_match(self):
        result = apply_scope_review(self.record(
            _merge="left_only", comparison_status="no_exact_inventory_key",
            reported_capacity_comparison="not_comparable",
        ))
        self.assertEqual(result.loc[0, "comparison_status"], "no_exact_inventory_key")
        self.assertEqual(result.loc[0, "reported_capacity_comparison"], "not_comparable")

    def test_other_capacity_issues_are_preserved(self):
        for status in ("missing_or_invalid_capacity", "zero_capacity_review",
                       "subtype_mapping_required"):
            with self.subTest(status=status):
                result = apply_scope_review(self.record(comparison_status=status))
                self.assertEqual(result.loc[0, "comparison_status"], status)
                self.assertEqual(result.loc[0, "capacity_scope_status"],
                                 "level_scope_review")
