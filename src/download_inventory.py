"""Download same-quarter Inventory sources for local QPASS workbooks."""

import argparse
import csv
import io
import re
import zipfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urljoin, urlsplit
from urllib.request import urlopen


ARCHIVE_URL = (
    "https://rmp-wapps.ucsd.edu/TS/Survey/Parking%20Space%20Inventory/"
    "Quarterly%20Tables/Contents.html"
)
QUARTERS = {1: "Summer", 2: "Fall", 3: "Winter", 4: "Spring"}
EXCEL_SUFFIXES = {".xls", ".xlsx", ".xlsm"}
TIMEOUT_SECONDS = 30
LOCAL_ALIASES = {
    ("2025-2026", "Fall"): "Inventory_2025-2026_Fall.xlsm",
}


class _ArchiveParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows = []
        self.row = None
        self.cell = None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.row = []
        elif tag in {"td", "th"} and self.row is not None:
            self.cell = {"text": "", "links": []}
        elif tag == "a" and self.cell is not None:
            href = dict(attrs).get("href")
            if href:
                self.cell["links"].append(href)

    def handle_data(self, data):
        if self.cell is not None:
            self.cell["text"] += data

    def handle_endtag(self, tag):
        if tag in {"td", "th"} and self.cell is not None:
            self.row.append(self.cell)
            self.cell = None
        elif tag == "tr" and self.row is not None:
            self.rows.append(self.row)
            self.row = None


def parse_inventory_archive(html, base_url=ARCHIVE_URL):
    """Extract year/quarter Excel URLs from the official archive table.

    Args:
        html: Downloaded archive page text.
        base_url: URL used to resolve relative workbook links.

    Returns:
        Mapping from (academic_year, quarter) to a list of Excel URLs.
        Multiple links remain ambiguous rather than being silently selected.
    """
    parser = _ArchiveParser()
    parser.feed(html)
    sources = {}
    for row in parser.rows:
        if not row:
            continue
        label = re.sub(r"\s+", "", row[0]["text"])
        year = re.fullmatch(r"(\d{4})/(\d{4})", label)
        if not year:
            continue
        if len(row) != 5:
            raise ValueError(f"Unrecognized archive row for {label}: {len(row)} cells")
        academic_year = f"{year[1]}-{year[2]}"
        for number, quarter in QUARTERS.items():
            links = []
            for href in row[number]["links"]:
                url = urljoin(base_url, href)
                if Path(unquote(urlsplit(url).path)).suffix.lower() in EXCEL_SUFFIXES:
                    if urlsplit(url).hostname != urlsplit(base_url).hostname:
                        raise ValueError(f"Unexpected workbook host: {url}")
                    links.append(url)
            sources[(academic_year, quarter)] = sorted(set(links))
    if not sources:
        raise ValueError("No academic-year rows found; inspect archive structure")
    return sources


def qpass_period(filename):
    """Parse a QPASS filename's academic year and quarter number.

    Args:
        filename: Original local QPASS workbook filename.

    Returns:
        (academic_year, quarter), or raises ValueError for an unknown pattern.
    """
    match = re.fullmatch(
        r"QPASS\s+(\d{4}-\d{4})-([1-4])\s+(Summer|Fall|Winter|Spring)\.(xlsx|xlsm|xls)",
        filename, flags=re.IGNORECASE,
    )
    if not match:
        raise ValueError(f"Unrecognized QPASS filename: {filename}")
    quarter = QUARTERS[int(match[2])]
    if quarter.casefold() != match[3].casefold():
        raise ValueError(f"Quarter number/name disagree: {filename}")
    start, end = map(int, match[1].split("-"))
    if end != start + 1:
        raise ValueError(f"Nonconsecutive academic year: {filename}")
    return match[1], quarter


def download_inventory(qpass_dir=Path("data/raw/QPASS"),
                       output_dir=Path("data/raw/inventory"),
                       manifest_path=Path("results/capacity_matching/inventory_sources.csv")):
    """Download available same-quarter sources without overwriting workbooks.

    Args:
        qpass_dir: Directory of local QPASS workbooks.
        output_dir: Directory for original Inventory downloads.
        manifest_path: CSV recording source URLs, local paths, and download status.

    Returns:
        Manifest records. Download success does not mean a workbook was audited
        or its historical capacities verified. Failed downloads remain flagged.
    """
    qpass_dir, output_dir = Path(qpass_dir), Path(output_dir)
    manifest_path = Path(manifest_path)
    files = sorted(p for p in qpass_dir.iterdir()
                   if p.suffix.lower() in EXCEL_SUFFIXES and p.is_file()
                   and not p.name.startswith("~$"))
    if not files:
        raise ValueError(f"No QPASS workbooks found in {qpass_dir}")
    with urlopen(ARCHIVE_URL, timeout=TIMEOUT_SECONDS) as response:
        sources = parse_inventory_archive(response.read().decode("utf-8", errors="replace"))
    output_dir.mkdir(parents=True, exist_ok=True)
    records = []
    for qpass in files:
        record = {"qpass_file": qpass.name, "academic_year": "", "quarter": "",
                  "inventory_url": "", "archive_filename": "", "inventory_path": "",
                  "download_status": "", "review_status": "not_audited_by_downloader",
                  "reason": ""}
        try:
            year, quarter = qpass_period(qpass.name)
            record.update(academic_year=year, quarter=quarter)
            urls = sources.get((year, quarter), [])
            if not urls:
                record.update(download_status="not_listed_in_archive",
                              reason="No Excel link for this exact academic year and quarter")
            elif len(urls) != 1:
                record.update(download_status="ambiguous_archive_links",
                              reason="Multiple Excel links; select only after source review")
            else:
                url = urls[0]
                filename = Path(unquote(urlsplit(url).path)).name
                local = output_dir / filename
                alias = LOCAL_ALIASES.get((year, quarter))
                if alias and (output_dir / alias).is_file():
                    local = output_dir / alias
                record.update(inventory_url=url, archive_filename=filename,
                              inventory_path=str(local))
                if local.exists():
                    record["download_status"] = "already_present"
                else:
                    with urlopen(url, timeout=TIMEOUT_SECONDS) as response:
                        payload = response.read()
                    suffix = Path(filename).suffix.lower()
                    valid = (payload.startswith(bytes.fromhex("d0cf11e0a1b11ae1"))
                             if suffix == ".xls" else zipfile.is_zipfile(io.BytesIO(payload)))
                    if not valid:
                        raise ValueError("Response is not an expected Excel file")
                    with local.open("xb") as handle:
                        handle.write(payload)
                    record["download_status"] = "downloaded"
        except Exception as exc:
            record.update(download_status="needs_review", reason=f"{type(exc).__name__}: {exc}")
        records.append(record)
        print(f"{qpass.name}: {record['download_status']}", flush=True)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with manifest_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    print(f"\nSource manifest: {manifest_path}")
    print("Downloads are original sources, not reviewed or verified capacities.")
    return records


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qpass-dir", type=Path, default=Path("data/raw/QPASS"))
    parser.add_argument("--output-dir", type=Path, default=Path("data/raw/inventory"))
    parser.add_argument("--manifest", type=Path,
                        default=Path("results/capacity_matching/inventory_sources.csv"))
    args = parser.parse_args()
    download_inventory(args.qpass_dir, args.output_dir, args.manifest)
