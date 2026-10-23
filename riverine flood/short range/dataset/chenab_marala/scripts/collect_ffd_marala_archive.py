"""Collect Marala readings from FFD's public 2024 or 2025 PDF archive.

Requires beautifulsoup4 and pymupdf: python -m pip install beautifulsoup4 pymupdf
Run from any directory: python collect_ffd_marala_archive.py 2024
                        python collect_ffd_marala_archive.py 2025
"""

import csv
import hashlib
import json
import re
import sys
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup


MODEL_DIR = Path(__file__).resolve().parents[1]
PROCESSED_DIR = MODEL_DIR / "processed" / "marala" / "discharge"
ARCHIVE = "https://ffd.pmd.gov.pk/bulletins/archive"
USER_AGENT = "Mozilla/5.0 (Marala discharge research; public FFD bulletins)"


def fetch(url: str) -> bytes:
    for attempt in range(3):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout=35) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def list_bulletins(year: int) -> list[dict]:
    items = []
    for page_number in range(1, 10):
        page = BeautifulSoup(fetch(f"{ARCHIVE}?page={page_number}"), "html.parser")
        for tr in page.select("table.archive-table tbody tr"):
            cells = tr.find_all("td")
            if len(cells) < 5 or cells[1].get_text(" ", strip=True) != "Bulletin":
                continue
            date_text = cells[0].get_text(" ", strip=True)
            if not date_text.endswith(str(year)):
                continue
            link = tr.find("a", href=re.compile(r"/download$"))
            if not link:
                continue
            url = link["href"]
            bulletin_id = int(re.search(r"/archive/(\d+)/download", url).group(1))
            date = datetime.strptime(date_text, "%d %b %Y").date().isoformat()
            items.append({"date": date, "archive_id": bulletin_id, "source_url": url})
    return sorted({item["archive_id"]: item for item in items}.values(), key=lambda item: item["date"])


def parse_pdf(item: dict, pdf: bytes) -> dict:
    if not pdf.startswith(b"%PDF-"):
        raise ValueError("Response was not a PDF")
    document = pymupdf.open(stream=pdf, filetype="pdf")
    text = "\n".join(page.get_text() for page in document)
    header = document[0].get_text()[:2500]
    dated = re.search(r"Dated:\s*[-–]?\s*(\d{1,2})(?:st|nd|rd|th)?\s*([A-Za-z]+)[,\s-]+(20\d\d)", header, re.I)
    if not dated:
        raise ValueError("Could not identify the bulletin's printed issue date")
    printed_date = datetime.strptime(f"{dated.group(1)} {dated.group(2)} {dated.group(3)}", "%d %B %Y").date().isoformat()
    observation_time = "06:00 PKT" if re.search(r"Actual\s+Observations\s+at\s+0600\s+PST", text, re.I) else ""
    match = re.search(r"\bMarala\s*\n\s*(?:\d{3,4})\s*\n\s*([\d,.]+)\s*\n\s*([\d,.]+)", text)
    if not match:
        raise ValueError("Could not identify Marala inflow and outflow in PDF text")
    inflow = Decimal(match.group(1).replace(",", ""))
    outflow = Decimal(match.group(2).replace(",", ""))
    if inflow < 0 or outflow < 0:
        raise ValueError("Negative discharge value")
    return {
        "date": printed_date,
        "archive_listed_date": item["date"],
        "date_status": "matches_archive" if printed_date == item["date"] else "printed_date_differs_from_archive",
        "observation_time": observation_time,
        "marala_inflow_1000_cusecs": str(inflow),
        "marala_outflow_1000_cusecs": str(outflow),
        "archive_id": item["archive_id"],
        "source_url": item["source_url"],
        "source_sha256": hashlib.sha256(pdf).hexdigest(),
        "raw_file": f"{item['date']}_archive_{item['archive_id']}.pdf",
    }


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("2024", "2025"):
        raise SystemExit("Usage: python collect_ffd_marala_archive.py 2024|2025")
    year = int(sys.argv[1])
    raw_dir = MODEL_DIR / "raw" / "marala" / "discharge" / "ffd" / f"bulletins_{year}"
    items = list_bulletins(year)
    if not items:
        raise ValueError(f"No {year} bulletins found in FFD archive")
    raw_dir.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    failures = []

    def collect(item: dict):
        raw_file = raw_dir / f"{item['date']}_archive_{item['archive_id']}.pdf"
        pdf = raw_file.read_bytes() if raw_file.exists() else fetch(item["source_url"])
        if not pdf.startswith(b"%PDF-"):
            raise ValueError("Response was not a PDF")
        if not raw_file.exists():
            raw_file.write_bytes(pdf)
        return parse_pdf(item, pdf)

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(collect, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            try:
                records.append(future.result())
            except (Exception,) as exc:
                failures.append({"date": item["date"], "archive_id": item["archive_id"], "error": str(exc)})

    records.sort(key=lambda record: (record["date"], record["archive_id"]))
    output = PROCESSED_DIR / f"marala_ffd_{year}_bulletin_discharge.csv"
    fields = ["date", "archive_listed_date", "date_status", "observation_time", "marala_inflow_1000_cusecs", "marala_outflow_1000_cusecs", "archive_id", "source_url", "source_sha256", "raw_file"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    dates = [record["date"] for record in records]
    counts = Counter(dates)
    missing_dates = []
    if dates:
        current = datetime.fromisoformat(min(dates)).date()
        last = datetime.fromisoformat(max(dates)).date()
        while current <= last:
            if current.isoformat() not in counts:
                missing_dates.append(current.isoformat())
            current += timedelta(days=1)
    report = {
        "provider": "Pakistan Meteorological Department, Flood Forecasting Division",
        "archive_url": ARCHIVE,
        "collected_utc": datetime.now(timezone.utc).isoformat(),
        "bulletins_listed": len(items),
        "marala_records_extracted": len(records),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "duplicate_observation_dates": {date: count for date, count in counts.items() if count > 1},
        "missing_dates_within_record_span": missing_dates,
        "archive_date_mismatches": [
            {"archive_id": record["archive_id"], "printed_date": record["date"], "archive_listed_date": record["archive_listed_date"]}
            for record in records if record["date_status"] != "matches_archive"
        ],
        "records_without_explicit_0600_pst_header": [record["archive_id"] for record in records if not record["observation_time"]],
        "failures": sorted(failures, key=lambda item: item["date"]),
        "notes": "Observations extracted from flood-season PDF bulletins. Not a year-round gauge archive. No missing values filled. Verify unusually high peaks and any extraction failures against the raw PDFs.",
    }
    (PROCESSED_DIR / f"marala_ffd_{year}_collection_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(records)} of {len(items)} {year} FFD bulletins: {report['first_date']} to {report['last_date']}")
    print(f"Failures: {len(failures)}; CSV: {output}")


if __name__ == "__main__":
    main()
