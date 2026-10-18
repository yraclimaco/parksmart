"""Evidence and rejection tests for historical snapshot capacity matching."""

import unittest

import pandas as pd

from src.capacity_acceptance import apply_capacity_acceptance


class TestCapacityAcceptance(unittest.TestCase):
    def row(self, **changes):
        row = {
            "academic_year": "2018-2019", "quarter": "Fall", "facility": "P011",
            "category": "B", "inventory_source_file": "Inventory 2018-2019-2 October 1.xlsx",
            "inventory_source_sheet": "5A By Lot", "inventory_facility_granularity": "lot",
            "inventory_report_title_raw": "Parking Space Inventory, Fall, 2018",
            "inventory_subtype_raw": "", "inventory_time_limit_raw": "",
            "inventory_single_capacity_status": "positive_unverified",
            "candidate_capacity": 28, "inventory_group_count": 1,
            "qpass_capacity_raw": 28, "qpass_level_raw": "", "qpass_subtype_raw": "",
            "observation_date": "2018-10-01", "open_spaces_raw": 12,
            "exclusion_reason": "", "_merge": "both",
        }
        row.update(changes)
        return row

    def test_supported_snapshot_is_accepted_with_basis(self):
        source = pd.DataFrame([self.row()])
        result = apply_capacity_acceptance(source)
        self.assertEqual(result.iloc[0].matched_capacity, 28)
        self.assertEqual(result.iloc[0].capacity_acceptance_status, "accepted")
        self.assertEqual(result.iloc[0].capacity_acceptance_basis,
                         "same_day_legacy_inventory_and_qpass_agreement")
        self.assertEqual(result.iloc[0].inventory_snapshot_date, pd.Timestamp("2018-10-01"))
        self.assertNotIn("matched_capacity", source)

    def test_no_backward_or_forward_capacity_fill(self):
        for date in ("2018-09-30", "2018-10-02", "", "not a date"):
            with self.subTest(date=date):
                result = apply_capacity_acceptance(pd.DataFrame([self.row(observation_date=date)]))
                self.assertTrue(pd.isna(result.iloc[0].matched_capacity))
                self.assertEqual(result.iloc[0].capacity_acceptance_reason, "outside_inventory_snapshot_date")

    def test_wrong_period_or_title_is_not_accepted(self):
        for changes in ({"academic_year": "2019-2020"}, {"quarter": "Spring"},
                        {"inventory_report_title_raw": "Inventory Spring 2019"},
                        {"inventory_report_title_raw": ""}):
            with self.subTest(changes=changes):
                result = apply_capacity_acceptance(pd.DataFrame([self.row(**changes)]))
                self.assertTrue(pd.isna(result.iloc[0].matched_capacity))

    def test_unknown_and_modern_sources_need_dated_evidence(self):
        for changes in ({"inventory_source_file": "other.xlsx"},
                        {"inventory_source_file": "Inventory 2025-2026-2 Fall.xlsm"},
                        {"inventory_source_sheet": "Pivot Table Data"},
                        {"inventory_facility_granularity": "structure"}):
            with self.subTest(changes=changes):
                result = apply_capacity_acceptance(pd.DataFrame([self.row(**changes)]))
                self.assertTrue(pd.isna(result.iloc[0].matched_capacity))

    def test_qualified_scopes_are_not_accepted(self):
        for changes in ({"qpass_level_raw": "Level 1"}, {"qpass_subtype_raw": "SIO"},
                        {"inventory_subtype_raw": "Reserved"},
                        {"inventory_time_limit_raw": "120"}, {"facility": "Hopkins"}):
            with self.subTest(changes=changes):
                result = apply_capacity_acceptance(pd.DataFrame([self.row(**changes)]))
                self.assertTrue(pd.isna(result.iloc[0].matched_capacity))

    def test_bad_totals_and_observations_are_not_accepted(self):
        for changes in ({"candidate_capacity": 0}, {"candidate_capacity": -1},
                        {"candidate_capacity": float("inf")}, {"candidate_capacity": 2.5},
                        {"qpass_capacity_raw": ""}, {"qpass_capacity_raw": 27},
                        {"open_spaces_raw": 29}, {"open_spaces_raw": -1},
                        {"open_spaces_raw": 1.5}, {"open_spaces_raw": "bad"}):
            with self.subTest(changes=changes):
                result = apply_capacity_acceptance(pd.DataFrame([self.row(**changes)]))
                self.assertTrue(pd.isna(result.iloc[0].matched_capacity))

    def test_conflict_in_another_slot_blocks_key_date(self):
        for changes in ({"qpass_capacity_raw": 30}, {"open_spaces_raw": 40},
                        {"qpass_subtype_raw": "Special"}):
            with self.subTest(changes=changes):
                result = apply_capacity_acceptance(pd.DataFrame([self.row(), self.row(**changes)]))
                self.assertTrue(result.matched_capacity.isna().all())

    def test_duplicate_sources_and_review_flags_block_acceptance(self):
        for changes in ({"inventory_group_count": 2}, {"_merge": "left_only"},
                        {"inventory_single_capacity_status": "closure_review"},
                        {"inventory_single_capacity_status": "period_metadata_review"},
                        {"exclusion_reason": "invalid_open_spaces"}):
            with self.subTest(changes=changes):
                result = apply_capacity_acceptance(pd.DataFrame([self.row(**changes)]))
                self.assertTrue(pd.isna(result.iloc[0].matched_capacity))

    def test_unrelated_key_or_date_conflict_does_not_block(self):
        result = apply_capacity_acceptance(pd.DataFrame([
            self.row(), self.row(facility="P012", qpass_capacity_raw=30),
            self.row(observation_date="2018-10-02", qpass_capacity_raw=30),
        ]))
        self.assertEqual(result.iloc[0].matched_capacity, 28)
        self.assertTrue(result.iloc[1:].matched_capacity.isna().all())

    def test_missing_evidence_and_empty_input_do_not_force_matches(self):
        source = pd.DataFrame([self.row()]).drop(columns="inventory_report_title_raw")
        result = apply_capacity_acceptance(source)
        self.assertTrue(result.matched_capacity.isna().all())
        self.assertTrue(apply_capacity_acceptance(pd.DataFrame()).empty)
