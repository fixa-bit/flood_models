"""Collect Marala discharge from FFD's public 2026 daily bulletins.

Requires beautifulsoup4: python -m pip install beautifulsoup4
Run from any directory: python collect_ffd_marala_2026.py
The script saves each official HTML body before making the extraction CSV.
"""

import csv
import hashlib
import json
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from bs4 import BeautifulSoup


MODEL_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = MODEL_DIR / "raw" / "marala" / "discharge" / "ffd" / "bulletins_2026"
PROCESSED_DIR = MODEL_DIR / "processed" / "marala" / "discharge"
INDEX_URL = "https://ffd.pmd.gov.pk/bulletin/"
USER_AGENT = "Mozilla/5.0 (Marala discharge research; public FFD bulletins)"


def fetch(url: str) -> bytes:
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=25) as response:
                return response.read()
        except (urllib.error.URLError, TimeoutError):
            if attempt == 2:
                raise
            time.sleep(1.5 * (attempt + 1))
    raise RuntimeError("unreachable")


def parse_bulletin(bulletin_id: int, body: bytes) -> dict | None:
    page = BeautifulSoup(body, "html.parser")
    dated = page.select_one(".meta-dated")
    if dated is None:
        return None
    match = re.search(r"(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)-(2026)", dated.get_text(" ", strip=True))
    if not match:
        raise ValueError(f"Cannot parse date in bulletin {bulletin_id}")
    date = datetime.strptime(f"{match.group(1)} {match.group(2)} {match.group(3)}", "%d %B %Y").date()
    stations = page.find_all(["td", "th"])
    marala = next((cell for cell in stations if cell.get_text(" ", strip=True).casefold() == "marala"), None)
    if marala is None:
        return None
    row = marala.find_parent("tr")
    inflow = row.find("td", attrs={"data-ffd": "inflow"})
    outflow = row.find("td", attrs={"data-ffd": "outflow"})
    if inflow is None or outflow is None:
        # Older HTML uses plain cells and may include design capacity before inflow.
        table = marala.find_parent("table")
        headers = " ".join(tr.get_text(" ", strip=True) for tr in table.find_all("tr")[:2])
        if not re.search(r"Actual\s+Observations\s+at\s+0600\s+PST", headers, re.I):
            raise ValueError(f"Unrecognized observation-table header in bulletin {bulletin_id}")
        cells = row.find_all(["td", "th"], recursive=False)
        station_index = next(i for i, cell in enumerate(cells) if cell is marala)
        offset = 2 if "Design Capacity" in headers else 1
        inflow, outflow = cells[station_index + offset:station_index + offset + 2]
    observation_time = "06:00 PKT" if re.search(r"Actual\s+Observations\s+at\s+0600\s+PST", page.get_text(" ", strip=True), re.I) else ""
    return {
        "date": date.isoformat(),
        "observation_time": observation_time,
        "marala_inflow_1000_cusecs": str(Decimal(inflow.get_text(" ", strip=True).replace(",", ""))),
        "marala_outflow_1000_cusecs": str(Decimal(outflow.get_text(" ", strip=True).replace(",", ""))),
        "bulletin_id": bulletin_id,
        "source_url": f"https://ffd.pmd.gov.pk/bulletin/{bulletin_id}/body",
        "source_sha256": hashlib.sha256(body).hexdigest(),
    }


def main() -> None:
    index = fetch(INDEX_URL).decode("utf-8", "replace")
    ids = [int(value) for value in re.findall(r"/bulletin/(\d+)/(?:body|download)", index)]
    if not ids:
        raise ValueError("Could not find FFD bulletin IDs on the publication page")
    latest_id = max(ids)
    SOURCE_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    records = []
    skipped = []
    failures = []

    def collect(bulletin_id: int):
        url = f"https://ffd.pmd.gov.pk/bulletin/{bulletin_id}/body"
        cached = list(SOURCE_DIR.glob(f"*_bulletin_{bulletin_id}.html"))
        body = cached[0].read_bytes() if len(cached) == 1 else fetch(url)
        record = parse_bulletin(bulletin_id, body)
        return bulletin_id, body, record

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = {executor.submit(collect, bulletin_id): bulletin_id for bulletin_id in range(1, latest_id + 1)}
        for future in as_completed(futures):
            bulletin_id = futures[future]
            try:
                _, body, record = future.result()
                if record is None:
                    skipped.append(bulletin_id)
                    continue
                filename = f"{record['date']}_bulletin_{bulletin_id}.html"
                (SOURCE_DIR / filename).write_bytes(body)
                record["raw_file"] = filename
                records.append(record)
            except (Exception,) as exc:
                failures.append({"bulletin_id": bulletin_id, "error": str(exc)})

    records.sort(key=lambda row: (row["date"], row["bulletin_id"]))
    output = PROCESSED_DIR / "marala_ffd_2026_bulletin_discharge.csv"
    fields = ["date", "observation_time", "marala_inflow_1000_cusecs", "marala_outflow_1000_cusecs", "bulletin_id", "source_url", "source_sha256", "raw_file"]
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(records)
    dates = [record["date"] for record in records]
    counts = Counter(dates)
    report = {
        "provider": "Pakistan Meteorological Department, Flood Forecasting Division",
        "index_url": INDEX_URL,
        "collected_utc": datetime.now(timezone.utc).isoformat(),
        "bulletin_ids_checked": latest_id,
        "marala_records": len(records),
        "first_date": min(dates) if dates else None,
        "last_date": max(dates) if dates else None,
        "duplicate_observation_dates": {date: count for date, count in counts.items() if count > 1},
        "records_without_explicit_0600_pst_header": [record["bulletin_id"] for record in records if not record["observation_time"]],
        "bulletin_ids_without_marala_table": sorted(skipped),
        "fetch_or_parse_failures": sorted(failures, key=lambda item: item["bulletin_id"]),
        "notes": "Bulletin observations, not a complete year-round daily gauge archive. Preserve inflow and outflow separately. No missing dates were filled.",
    }
    (PROCESSED_DIR / "marala_ffd_2026_collection_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Collected {len(records)} Marala bulletin records, {report['first_date']} to {report['last_date']}")
    print(f"Skipped {len(skipped)} IDs without Marala table; failed {len(failures)} IDs")
    print(f"CSV: {output}")


if __name__ == "__main__":
    main()
