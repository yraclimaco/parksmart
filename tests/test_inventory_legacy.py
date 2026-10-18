"""Tests for legacy category tables without creating or editing workbooks."""

import unittest

import pandas as pd

from src.clean_inventory_legacy import CATEGORY_HEADERS, extract_legacy_table


class TestLegacyInventory(unittest.TestCase):
    def table(self, structure=False):
        data = pd.DataFrame("", index=range(8), columns=range(15), dtype=object)
        first = 1 if structure else 2
        facility_col = first - 1
        data.iloc[1, facility_col] = (
            "University of California, San Diego Survey of Parking Space Inventory, Fall, 2018"
        )
        data.iloc[5, first:first + 10] = CATEGORY_HEADERS
        data.iloc[6, first + 7] = "Vehicle"
        data.iloc[6, first + 8] = "Yard"
        data.iloc[7, facility_col] = "Hopkins" if structure else "P001"
        data.iloc[7, first] = 25
        data.iloc[7, first + 10] = 999  # Total: never unpivoted as a category.
        data.iloc[7, first + 11] = 3  # Motorcycle sections: different unit.
        return data

    def extract(self, data, structure=False, year="2018-2019", quarter="Fall"):
        sheet = "6A By Structure" if structure else "5A By Lot"
        return extract_legacy_table(data, "original.xlsx", sheet, year, quarter)

    def test_both_layouts_and_provenance(self):
        for structure in (False, True):
            with self.subTest(structure=structure):
                rows = self.extract(self.table(structure), structure)
                self.assertEqual(len(rows), 10)
                self.assertEqual(rows[0]["capacity"], 25)
                self.assertEqual(rows[0]["source_rows"], "8")
                self.assertEqual(rows[0]["source_cell"], "B8" if structure else "C8")
                self.assertEqual(rows[0]["source_file"], "original.xlsx")
                self.assertEqual(rows[7]["category_raw"], "UC")
                self.assertEqual(rows[7]["category"], "UC Vehicle")
                self.assertEqual(rows[8]["category"], "Service Yard")
                self.assertNotIn("Total", [r["category"] for r in rows])
                self.assertTrue(all(r["capacity_status"] != "verified" for r in rows))

    def test_missing_zero_closure_and_invalid_counts(self):
        cases = [("", "missing"), (None, "missing"), (0, "zero_review"),
                 ("Closed for construction", "invalid_numeric"),
                 (-1, "invalid_capacity"), (2.5, "invalid_capacity")]
        for value, expected in cases:
            with self.subTest(value=value):
                data = self.table()
                data.iloc[7, 2] = value
                row = self.extract(data)[0]
                self.assertEqual(row["capacity_status"], expected)
                self.assertIn(repr(value), row["capacity_raw_values"])
                if expected != "zero_review":
                    self.assertTrue(pd.isna(row["capacity"]))

    def test_wrong_quarter_or_year_rejected(self):
        for year, quarter in [("2018-2019", "Summer"), ("2025-2026", "Fall"),
                              ("2018-2020", "Fall")]:
            with self.subTest(year=year, quarter=quarter):
                with self.assertRaises(ValueError):
                    self.extract(self.table(), year=year, quarter=quarter)

    def test_changed_headers_rejected(self):
        data = self.table()
        data.iloc[5, 2] = "Unknown category"
        with self.assertRaises(ValueError):
            self.extract(data)

    def test_populated_row_without_facility_rejected(self):
        data = self.table()
        data.iloc[7, 1] = ""
        with self.assertRaises(ValueError):
            self.extract(data)

    def test_subtotal_not_mistaken_for_facility(self):
        data = self.table(True)
        data.iloc[7, 0] = "Grand total"
        with self.assertRaises(ValueError):
            self.extract(data, True)

    def test_summer_shifted_header_and_title_in_first_column(self):
        data = self.table()
        data.iloc[1, 1] = ""
        data.iloc[1, 0] = "Parking Space Inventory, Summer 2018"
        data = pd.concat(
            [
                data.iloc[:5],
                pd.DataFrame([[""] * data.shape[1]]),
                data.iloc[5:],
            ],
            ignore_index=True,
        )
        rows = self.extract(data, quarter="Summer")
        self.assertEqual(len(rows), 10)
        self.assertEqual(rows[0]["source_cell"], "C9")
        self.assertEqual(rows[0]["capacity"], 25)

    def test_added_d_category_does_not_shift_visitor_values(self):
        data = self.table()
        data.iloc[1, 1] = "Parking Space Inventory, Fall 2019"
        extra = pd.Series([""] * len(data), dtype=object)
        extra.iloc[5], extra.iloc[7] = "D", 17
        data = pd.concat(
            [data.iloc[:, :5], extra, data.iloc[:, 5:]],
            axis=1,
            ignore_index=True,
        )
        data.iloc[7, 6] = 22
        rows = self.extract(data, year="2019-2020")
        self.assertEqual(len(rows), 11)
        by_category = {row["category"]: row for row in rows}
        self.assertEqual(by_category["D"]["capacity"], 17)
        self.assertEqual(by_category["Visitor"]["capacity"], 22)
        self.assertEqual(by_category["UC Vehicle"]["source_cell"], "K8")

    def test_letter_suffix_lots_are_preserved(self):
        for facility in ("P406a", "P406b"):
            with self.subTest(facility=facility):
                data = self.table()
                data.iloc[7, 1] = facility
                row = self.extract(data)[0]
                self.assertEqual(row["facility_raw"], facility)
                self.assertEqual(row["facility"], facility)
    def test_closed_lot_keeps_note_and_never_accepts_capacity(self):
        for raw_capacity in ("", 123):
            with self.subTest(raw_capacity=raw_capacity):
                data = self.table()
                data.iloc[7, 1] = "P005 (closed for construction)"
                data.iloc[7, 2] = raw_capacity
                row = self.extract(data)[0]
                self.assertEqual(
                    row["facility_raw"], "P005 (closed for construction)"
                )
                self.assertEqual(row["facility"], row["facility_raw"])
                self.assertEqual(
                    row["facility_note_raw"], "(closed for construction)"
                )
                self.assertEqual(row["capacity_status"], "closure_review")
                self.assertTrue(pd.isna(row["capacity"]))
                self.assertIn(repr(raw_capacity), row["capacity_raw_values"])
