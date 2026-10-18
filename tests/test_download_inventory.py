"""Archive parsing and preservation checks; no network needed for tests."""

import io
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from src import download_inventory as downloader


HTML = '''<table><tr><th>Year</th><th>Summer</th><th>Fall</th>
<th>Winter</th><th>Spring</th></tr>
<tr><td>2025/2026</td><td><a href="Inventory%20Summer.xlsm">Excel</a></td>
<td><a href="Inventory%20Fall.xlsm">Excel</a></td><td></td>
<td><a href="Inventory%20Spring.xlsm">Excel</a></td></tr></table>'''


class TestDownloadInventory(unittest.TestCase):
    def test_year_and_quarter_columns(self):
        result = downloader.parse_inventory_archive(HTML)
        self.assertTrue(result[("2025-2026", "Fall")][0].endswith("Inventory%20Fall.xlsm"))
        self.assertEqual(result[("2025-2026", "Winter")], [])

    def test_pdf_links_are_not_excel_sources(self):
        result = downloader.parse_inventory_archive(HTML.replace(
            'Inventory%20Summer.xlsm', 'summary.pdf',
        ))
        self.assertEqual(result[("2025-2026", "Summer")], [])

    def test_changed_archive_shape_is_rejected(self):
        for text in ("<html>No archive</html>",
                     "<tr><td>2025/2026</td><td>Changed layout</td></tr>"):
            with self.subTest(text=text):
                with self.assertRaises(ValueError):
                    downloader.parse_inventory_archive(text)

    def test_multiple_links_are_retained_for_review(self):
        text = HTML.replace('>Excel</a>', '>Excel</a><a href="other.xlsx">Excel</a>', 1)
        self.assertEqual(len(downloader.parse_inventory_archive(text)[
            ("2025-2026", "Summer")]), 2)

    def test_qpass_period_accepts_extra_filename_spaces(self):
        self.assertEqual(downloader.qpass_period("QPASS 2026-2027-2  Fall.xlsm"),
                         ("2026-2027", "Fall"))

    def test_unknown_or_inconsistent_qpass_names_are_rejected(self):
        for name in ("random.xlsx", "QPASS 2025-2026-1 Fall.xlsx",
                     "QPASS 2025-2028-2 Fall.xlsx"):
            with self.subTest(name=name):
                with self.assertRaises(ValueError):
                    downloader.qpass_period(name)

    def test_existing_sources_and_archive_gaps_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            qpass, output = root / "qpass", root / "inventory"
            qpass.mkdir()
            output.mkdir()
            for name in ("QPASS 2025-2026-1 Summer.xlsm",
                         "QPASS 2025-2026-3 Winter.xlsm"):
                (qpass / name).write_bytes(b"fixture")
            source = output / "Inventory Summer.xlsm"
            source.write_bytes(b"original bytes must stay unchanged")
            with patch.object(downloader, "urlopen", return_value=io.BytesIO(HTML.encode())) as fetch:
                records = downloader.download_inventory(qpass, output, root / "manifest.csv")
            self.assertEqual(fetch.call_count, 1)
            self.assertEqual(source.read_bytes(), b"original bytes must stay unchanged")
            self.assertEqual([r["download_status"] for r in records],
                             ["already_present", "not_listed_in_archive"])
            self.assertTrue((root / "manifest.csv").is_file())

    def test_download_checks_payload_and_records_failures(self):
        for valid in (True, False):
            with self.subTest(valid=valid), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                qpass = root / "qpass"
                qpass.mkdir()
                (qpass / "QPASS 2025-2026-1 Summer.xlsm").write_bytes(b"fixture")
                content = io.BytesIO()
                with zipfile.ZipFile(content, "w") as package:
                    package.writestr("xl/workbook.xml", "test fixture")
                payload = content.getvalue() if valid else b"<html>error</html>"
                with patch.object(downloader, "urlopen", side_effect=[
                    io.BytesIO(HTML.encode()), io.BytesIO(payload),
                ]):
                    records = downloader.download_inventory(
                        qpass, root / "inventory", root / "manifest.csv",
                    )
                self.assertEqual(records[0]["download_status"],
                                 "downloaded" if valid else "needs_review")
                self.assertEqual((root / "inventory" / "Inventory Summer.xlsm").exists(), valid)
