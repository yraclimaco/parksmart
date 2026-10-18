"""Verify batch coverage, weighted rates, and lossless Inventory grouping."""

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

from src.compare_capacities import compare_capacities
from src.run_capacity_matching import build_inventory_dataset, combine_rates, run_capacity_matching


class TestCapacityBatch(unittest.TestCase):
    def test_weighted_rate_and_zero_denominator(self):
        quarters = pd.DataFrame({"observation_slots": [10, 90],
                                 "exact_key_candidates": [10, 0],
                                 "verified_capacity_matches": [2, 0]})
        total = combine_rates(quarters)
        self.assertEqual(total["exact_key_candidate_rate"], 0.1)
        self.assertEqual(total["verified_capacity_match_rate"], 0.02)
        self.assertIsNone(combine_rates(quarters.iloc[:0])["verified_capacity_match_rate"])

    def test_ambiguous_inventory_groups_not_summed_or_lost(self):
        rows = [dict(academic_year="2018-2019", quarter="Fall", facility_raw=" P011 ",
                     category_raw="B", capacity="20", capacity_status="positive_unverified",
                     source_file="original.xlsx", subtype_raw="regular"),
                dict(academic_year="2018-2019", quarter="Fall", facility_raw=" P011 ",
                     category_raw="B", capacity="8", capacity_status="positive_unverified",
                     source_file="original.xlsx", subtype_raw="special")]
        cleaned = build_inventory_dataset(pd.DataFrame(rows))
        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned.iloc[0].facility, "P011")
        self.assertTrue(pd.isna(cleaned.iloc[0].capacity))
        self.assertEqual(json.loads(cleaned.iloc[0].source_groups_json), rows)

    def test_single_inventory_zero_keeps_review_status(self):
        row = dict(academic_year="2018-2019", quarter="Fall", facility_raw="P011",
                   category_raw="B", capacity="0", capacity_status="zero_review",
                   source_file="original.xlsx")
        cleaned = build_inventory_dataset(pd.DataFrame([row]))
        self.assertEqual(cleaned.iloc[0].capacity, "0")
        self.assertEqual(cleaned.iloc[0].capacity_status, "zero_review")

    def test_missing_inventory_quarter_stays_in_results(self):
        qpass = pd.DataFrame([dict(
            academic_year="2026-2027", quarter="Fall", location="P011", type="B",
            sub_type="", level="", date="2026-10-01", total_stall_count=28,
            open_8am=12, open_10am=10, open_12pm=9, open_2pm=8,
            source_file="QPASS 2026-2027-2 Fall.xlsm", sheet_name="Data Entry", source_row=5,
        )])
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "qpass").mkdir()
            (root / "qpass/QPASS 2026-2027-2 Fall.xlsm").touch()
            manifest = root / "manifest.csv"
            pd.DataFrame([dict(academic_year="2026-2027", quarter="Fall",
                               qpass_file="QPASS 2026-2027-2 Fall.xlsm",
                               inventory_path="", download_status="not_listed_in_archive",
                               reason="No quarterly link found")]).to_csv(manifest, index=False)
            with patch("src.compare_capacities.load_qpass", return_value=qpass):
                quarters, total = run_capacity_matching(
                    manifest, root / "qpass", root / "inventory", root / "output"
                )
            self.assertEqual(len(quarters), 1)
            self.assertEqual(total["eligible_observation_slots"], 4)
            self.assertEqual(total["verified_capacity_matches"], 0)
            unresolved = pd.read_csv(root / "output/combined/unresolved_cases.csv")
            self.assertEqual(len(unresolved), 4)
            self.assertTrue(unresolved.comparison_status.eq("inventory_workbook_unavailable").all())
            self.assertTrue(unresolved.matched_capacity.isna().all())

    def test_duplicate_manifest_quarter_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            row = dict(academic_year="2018-2019", quarter="Fall")
            manifest = root / "manifest.csv"
            pd.DataFrame([row, row]).to_csv(manifest, index=False)
            with self.assertRaisesRegex(ValueError, "repeated quarters"):
                run_capacity_matching(manifest, output_dir=root / "output")
