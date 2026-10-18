"""Test newer Inventory layouts without editing original workbooks."""

import unittest

import pandas as pd

from src.clean_inventory_modern import extract_modern_inventory


class TestModernInventory(unittest.TestCase):
    def table(self, grouped=False):
        facility = "Lot  / Structure" if grouped else "Lot / Garage"
        counts = ["Inventory By Location"] if grouped else ["Summer", "Inventory"]
        headers = [facility, "Space Type", "Space Subtype", "Time Limit [minutes]", *counts]
        prefix = [[""] * len(headers)] * (3 if grouped else 1)
        row = ["P001", "B", "", "", 34] + ([] if grouped else [34])
        return pd.DataFrame(prefix + [headers, row], dtype=object)

    def extract(self, table, **kwargs):
        return extract_modern_inventory(
            table, "Inventory 2025-2026-1 Summer.xlsm", "2025-2026", "Summer", **kwargs
        )

    def test_both_headers_and_provenance(self):
        for grouped in (False, True):
            with self.subTest(grouped=grouped):
                cleaned, audit = self.extract(self.table(grouped))
                row = cleaned.iloc[0]
                self.assertEqual(row.capacity, 34)
                self.assertEqual(row.source_rows, "5" if grouped else "3")
                self.assertEqual(row.facility_raw, "P001")
                self.assertEqual(row.category_raw, "B")
                self.assertEqual(row.capacity_status, "positive_unverified")
                self.assertEqual(audit["source_records"], 1)

    def test_quarter_column_disagreement_is_flagged(self):
        table = self.table()
        table.iloc[-1, -1] = 40
        cleaned, _ = self.extract(table)
        self.assertEqual(cleaned.iloc[0].capacity_status, "capacity_column_conflict")
        self.assertTrue(pd.isna(cleaned.iloc[0].capacity))
        self.assertEqual(cleaned.iloc[0].inventory_column_raw_values, "[40]")

    def test_year_specific_quarter_column(self):
        table = self.table()
        table.iloc[1, 4] = "Summer 2025"
        cleaned, _ = self.extract(table)
        self.assertEqual(cleaned.iloc[0].capacity_source_column, "Summer 2025")
        self.assertEqual(cleaned.iloc[0].capacity, 34)

    def test_repeated_2024_rows_are_not_summed(self):
        table = self.table()
        table = pd.concat([table, table.iloc[[-1]]], ignore_index=True)
        cleaned, audit = self.extract(table)
        self.assertEqual(audit["source_records"], 2)
        self.assertEqual(cleaned.iloc[0].capacity_status, "multiple_totals_review")
        self.assertTrue(pd.isna(cleaned.iloc[0].capacity))

    def test_grouped_totals_allow_intentional_blank_repeats(self):
        table = self.table(True)
        repeat = table.iloc[[-1]].copy()
        repeat.iloc[0, -1] = ""
        table = pd.concat([table, repeat], ignore_index=True)
        cleaned, _ = self.extract(table)
        self.assertEqual(cleaned.iloc[0].capacity, 34)
        self.assertEqual(cleaned.iloc[0].source_record_count, 2)

    def test_missing_identifier_is_retained(self):
        table = self.table(True)
        table.iloc[-1, 0] = ""
        cleaned, audit = self.extract(table)
        self.assertEqual(audit["source_records"], 1)
        self.assertEqual(cleaned.iloc[0].capacity_status, "invalid_identifier_review")
        self.assertTrue(pd.isna(cleaned.iloc[0].capacity))

    def test_conflicting_title_or_selector_blocks_capacity(self):
        for title in ("Spring Quarter", "Summer 2024"):
            with self.subTest(title=title):
                cleaned, audit = self.extract(self.table(True), title_values=[title])
                self.assertEqual(cleaned.iloc[0].capacity_status, "period_metadata_review")
                self.assertTrue(pd.isna(cleaned.iloc[0].capacity))
                self.assertEqual(audit["period_metadata_issues"], [title])

    def test_wrong_filename_period_or_schema_rejected(self):
        for year, quarter in (("2024-2025", "Summer"), ("2025-2026", "Fall")):
            with self.subTest(year=year, quarter=quarter):
                with self.assertRaises(ValueError):
                    extract_modern_inventory(self.table(), "Inventory 2025-2026 Summer.xlsm", year, quarter)
        table = self.table()
        table.iloc[1, 0] = "Unknown facility field"
        with self.assertRaises(ValueError):
            self.extract(table)

    def test_blank_zero_and_invalid_capacity(self):
        for value, status in (("", "missing"), (0, "zero_review"), (-1, "invalid_capacity"),
                              (2.5, "invalid_capacity"), ("text", "invalid_numeric")):
            with self.subTest(value=value):
                table = self.table(True)
                table.iloc[-1, -1] = value
                cleaned, _ = self.extract(table)
                self.assertEqual(cleaned.iloc[0].capacity_status, status)
                self.assertIn(repr(value), cleaned.iloc[0].capacity_raw_values)

    def test_all_category_total_never_used(self):
        table = self.table(True)
        table[len(table.columns)] = pd.Series("", index=table.index, dtype=object)
        table.iloc[3, -1] = "Combined  Inventory by Lot"
        table.iloc[4, -1] = 999
        cleaned, _ = self.extract(table)
        self.assertEqual(cleaned.iloc[0].capacity, 34)
        self.assertEqual(cleaned.iloc[0].capacity_source_column, "Inventory By Location")
