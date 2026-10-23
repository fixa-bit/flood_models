"""Preserve PMD's published historical Marala flood peaks separately from daily data.

Requires pymupdf: python -m pip install pymupdf
Run from any directory: python collect_pmd_marala_peaks.py
"""

import csv
import hashlib
import json
import re
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

import pymupdf


MODEL_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = MODEL_DIR / "raw" / "marala" / "discharge" / "pmd"
PROCESSED_DIR = MODEL_DIR / "processed" / "marala" / "discharge"
URL = (
    "https://www.pmd.gov.pk/rnd/rndweb/rnd_new/journal/vol13_issue26_files/"
    "5_Flood_Forecasting_of_an_Ungauged_Trans-boundary_Chenab_River_Basin_Using_"
    "Distributed_Hydrological_Model_Integrated_Flood_Analysis_System_%28IFAS%29.pdf"
)
RAW_FILE = RAW_DIR / "marala_historical_flood_peaks_pmd_journal.pdf"


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    if RAW_FILE.exists():
        pdf = RAW_FILE.read_bytes()
    else:
        request = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            pdf = response.read()
        if not pdf.startswith(b"%PDF-"):
            raise ValueError("PMD response was not a PDF")
        RAW_FILE.write_bytes(pdf)
    digest = hashlib.sha256(pdf).hexdigest()
    document = pymupdf.open(stream=pdf, filetype="pdf")
    page = next((page for page in document if "Table 1: Historical Floods Recorded at Marala" in page.get_text()), None)
    if page is None:
        raise ValueError("Could not find Marala flood-peak table")
    text = page.get_text()
    start = text.index("Table 1: Historical Floods Recorded at Marala")
    end = text.index("The Classification of Flood Limits", start)
    table = text[start:end]
    pattern = re.compile(r"(\d{1,2})\s*/\s*(\d{1,2})\s*/\s*(\d{4})\s+([\d.]+)\s+(Ex\. High|Very High|High)", re.I)
    records = []
    for day, month, year, discharge, level in pattern.findall(table):
        date = datetime(int(year), int(month), int(day)).date().isoformat()
        records.append({
            "peak_date": date,
            "peak_discharge_1000_cusecs": str(Decimal(discharge)),
            "flood_level_as_published": level,
            "source_url": URL,
            "source_pdf_page": page.number + 1,
        })
    records.sort(key=lambda record: record["peak_date"])
    if len(records) != 30 or len({record["peak_date"] for record in records}) != 30:
        raise ValueError(f"Expected 30 distinct published peak rows, found {len(records)}")
    output = PROCESSED_DIR / "marala_pmd_historical_flood_peaks.csv"
    with output.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    receipt = {
        "provider": "Pakistan Meteorological Department, Pakistan Journal of Meteorology",
        "source_url": URL,
        "downloaded_or_checked_utc": datetime.now(timezone.utc).isoformat(),
        "raw_file": str(RAW_FILE.relative_to(MODEL_DIR)).replace("\\", "/"),
        "source_sha256": digest,
        "pdf_page": page.number + 1,
        "peak_count": len(records),
        "first_peak_date": records[0]["peak_date"],
        "last_peak_date": records[-1]["peak_date"],
        "warning": "Selected historical flood peaks only. These are event maxima, not daily 06:00 observations; do not merge as daily training rows.",
    }
    (RAW_DIR / "source_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(records)} selected historical Marala flood peaks: {records[0]['peak_date']} to {records[-1]['peak_date']}")


if __name__ == "__main__":
    main()
