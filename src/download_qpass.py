"""Download the public QPASS workbooks into data/raw/QPASS/.

Run from the repo:

    python -m src.download_qpass

Files are fetched from UCSD's public QPASS index page. Files already in the
folder are never overwritten (delete one to download it again), and the
workbook excluded by team decision is not downloaded.
"""

from __future__ import annotations

import io
import logging
import re
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable

from src.qpass_inventory import RAW_QPASS_DIR

logger = logging.getLogger(__name__)

QPASS_INDEX_URL = "https://rmp-wapps.ucsd.edu/TS/Survey/QPASS/Contents.html"

# Workbook links on the index page, e.g. href="QPASS%202024-2025-2%20Fall.xlsm".
WORKBOOK_LINK_PATTERN = re.compile(r'href="([^"]*QPASS[^"]*\.xls[xm]?)"', re.IGNORECASE)

# Not downloaded, by team decision (see docs/qpass_schema_audit.md).
EXCLUDED_FILES = {"QPASS 2025-2026-3 Winter.xlsm"}

REQUEST_TIMEOUT_SECONDS = 60

# Download to a name that does not start with "QPASS", so a half-finished
# file is never picked up by the loader.
PARTIAL_FILE_PREFIX = ".downloading-"


def find_workbook_links(html: str, base_url: str = QPASS_INDEX_URL) -> dict[str, str]:
    """Find every QPASS workbook linked from the index page.

    Args:
        html: The index page's HTML.
        base_url: URL of the page, used to turn relative links into full URLs.

    Returns:
        {file name: full URL}. File names are decoded ("%20" becomes a space)
        and match the names used in data/raw/QPASS/.
    """
    links = {}
    for href in WORKBOOK_LINK_PATTERN.findall(html):
        url = urllib.parse.urljoin(base_url, href)
        name = urllib.parse.unquote(Path(urllib.parse.urlparse(url).path).name)
        links[name] = url
    return links


def _fetch(url: str) -> bytes:
    """Download one URL and return its contents."""
    with urllib.request.urlopen(url, timeout=REQUEST_TIMEOUT_SECONDS) as response:
        return response.read()


def download_qpass(
    folder: str | Path = RAW_QPASS_DIR, fetch: Callable[[str], bytes] = _fetch
) -> dict[str, str]:
    """Download every QPASS workbook that is not already in the folder.

    Args:
        folder: Where to save the workbooks. Defaults to data/raw/QPASS.
        fetch: Function that downloads a URL (replaced in tests).

    Returns:
        {file name: what happened}: "downloaded", "already present", or
        "excluded (team decision)".

    Raises:
        RuntimeError: If the index page links no workbooks (page changed).
        ValueError: If a download is not an Excel workbook. Nothing is saved
            for that file.
    """
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    html = fetch(QPASS_INDEX_URL).decode("utf-8", errors="replace")
    links = find_workbook_links(html)
    if not links:
        raise RuntimeError(f"No QPASS workbook links found on {QPASS_INDEX_URL}")

    results = {}
    for name, url in sorted(links.items()):
        target = folder / name
        if name in EXCLUDED_FILES:
            results[name] = "excluded (team decision)"
        elif target.exists():
            results[name] = "already present"
        else:
            content = fetch(url)
            # .xlsx and .xlsm files are zip archives; an error page is not.
            if not zipfile.is_zipfile(io.BytesIO(content)):
                raise ValueError(f"{name}: downloaded file is not an Excel workbook")
            partial = folder / (PARTIAL_FILE_PREFIX + name)
            partial.write_bytes(content)
            partial.replace(target)
            results[name] = "downloaded"
        logger.info("%s: %s", name, results[name])
    return results


def main() -> None:
    """Download the workbooks and print a one-line summary."""
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    results = download_qpass()
    statuses = list(results.values())
    counts = {status: statuses.count(status) for status in sorted(set(statuses))}
    print(f"Done. Workbooks in {RAW_QPASS_DIR}: {counts}")


if __name__ == "__main__":
    main()
