"""Tests for src/download_qpass.py.

No test touches the internet: a fake fetch function stands in for the
UCSD website.
"""

import io

import pytest
from openpyxl import Workbook

from src.download_qpass import (
    EXCLUDED_FILES,
    QPASS_INDEX_URL,
    download_qpass,
    find_workbook_links,
)

BASE = "https://rmp-wapps.ucsd.edu/TS/Survey/QPASS/"
INDEX_HTML = """
<a href="QPASS%202024-2025-1%20%20Summer.xlsm">Summer</a>
<a href="QPASS%202024-2025-2%20Fall.xlsm">Fall</a>
<a href="QPASS%202025-2026-3%20Winter.xlsm">Winter</a>
<a href="Contents.html">not a workbook</a>
"""


def _workbook_bytes():
    """A tiny valid .xlsx file, as bytes."""
    buffer = io.BytesIO()
    Workbook().save(buffer)
    return buffer.getvalue()


class FakeWebsite:
    """Serves the index page and workbooks, and records which URLs were asked for."""

    def __init__(self, workbook=None):
        self.workbook = workbook if workbook is not None else _workbook_bytes()
        self.requested = []

    def __call__(self, url):
        self.requested.append(url)
        if url == QPASS_INDEX_URL:
            return INDEX_HTML.encode()
        return self.workbook


def test_find_workbook_links_decodes_names():
    links = find_workbook_links(INDEX_HTML)
    assert links == {
        "QPASS 2024-2025-1  Summer.xlsm": BASE + "QPASS%202024-2025-1%20%20Summer.xlsm",
        "QPASS 2024-2025-2 Fall.xlsm": BASE + "QPASS%202024-2025-2%20Fall.xlsm",
        "QPASS 2025-2026-3 Winter.xlsm": BASE + "QPASS%202025-2026-3%20Winter.xlsm",
    }


def test_download_saves_workbooks_and_skips_the_excluded_file(tmp_path):
    website = FakeWebsite()
    results = download_qpass(tmp_path, fetch=website)
    assert results == {
        "QPASS 2024-2025-1  Summer.xlsm": "downloaded",
        "QPASS 2024-2025-2 Fall.xlsm": "downloaded",
        "QPASS 2025-2026-3 Winter.xlsm": "excluded (team decision)",
    }
    assert "QPASS 2025-2026-3 Winter.xlsm" in EXCLUDED_FILES
    saved = sorted(path.name for path in tmp_path.iterdir())
    assert saved == ["QPASS 2024-2025-1  Summer.xlsm", "QPASS 2024-2025-2 Fall.xlsm"]


def test_download_never_overwrites_an_existing_file(tmp_path):
    existing = tmp_path / "QPASS 2024-2025-2 Fall.xlsm"
    existing.write_bytes(b"my copy")
    website = FakeWebsite()
    results = download_qpass(tmp_path, fetch=website)
    assert results["QPASS 2024-2025-2 Fall.xlsm"] == "already present"
    assert existing.read_bytes() == b"my copy"
    assert BASE + "QPASS%202024-2025-2%20Fall.xlsm" not in website.requested


def test_download_rejects_a_file_that_is_not_a_workbook(tmp_path):
    website = FakeWebsite(workbook=b"<html>Page not found</html>")
    with pytest.raises(ValueError, match="not an Excel workbook"):
        download_qpass(tmp_path, fetch=website)
    assert list(tmp_path.iterdir()) == []  # nothing half-saved


def test_download_fails_loudly_if_the_page_has_no_links(tmp_path):
    def empty_page(url):
        return b"<html>moved</html>"

    with pytest.raises(RuntimeError, match="No QPASS workbook links"):
        download_qpass(tmp_path, fetch=empty_page)
