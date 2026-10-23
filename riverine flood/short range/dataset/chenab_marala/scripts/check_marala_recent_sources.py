"""Save public source checks and available IRSA daily-mean records.

Requires beautifulsoup4 and pymupdf. No messages or data requests are sent.
Run: python check_marala_recent_sources.py --as-of 2026-10-23
"""

import argparse
import csv
import hashlib
import json
import re
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import urljoin

import pymupdf
from bs4 import BeautifulSoup

MODEL = Path(__file__).resolve().parents[1]
OUTPUT = MODEL / "processed/marala/discharge"
RAW = MODEL / "raw/marala/discharge"


def fetch_and_save(url, path):
    checked = datetime.now(timezone.utc).isoformat()
    result = {"url": url, "checked_utc": checked}
    try:
        request = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (public hydrology research)"})
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read()
            result.update(status=response.status, final_url=response.url)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
        result.update(raw_file=path.relative_to(MODEL).as_posix(), sha256=hashlib.sha256(body).hexdigest(), bytes=len(body))
        return result, body
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        result.update(status=getattr(exc, "code", "fetch_failed"), error=str(exc))
        return result, None


def parse_irsa(pdf, expected_date):
    with pymupdf.open(stream=pdf, filetype="pdf") as document:
        text = "\n".join(page.get_text() for page in document)
    # The report also contains last year's date; require the expected current date.
    if expected_date.strftime("%d.%m.%Y") not in text:
        raise ValueError("Requested date was not found in PDF")
    section = text.split("CHENAB @ MARALA:", 1)[1]
    upstream = re.search(r"MEAN\s+U/S\s+DISCHARGE\s*=\s*([\d,]+)\s*Cs", section)
    downstream = re.search(r"MEAN\s+D/S\s+DISCHARGE\s*=\s*([\d,]+)\s*Cs", section)
    if not upstream or not downstream:
        raise ValueError("Cannot identify Marala mean upstream/downstream discharge")
    return {"date": expected_date.isoformat(), "mean_inflow_cusecs": upstream[1].replace(",", ""),
            "mean_outflow_cusecs": downstream[1].replace(",", ""), "time_pakistan": "",
            "measurement_basis": "daily_mean_as_labeled_by_irsa",
            "time_status": "averaging_period_bounds_not_stated"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    if args.as_of > datetime.now(timezone.utc).date():
        raise ValueError("Cannot collect future observations")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    checks = []
    pages = [
        ("river-flow.html", "https://wapda.gov.pk/river-flow/"),
        ("water-situation.html", "https://wapda.gov.pk/water-situation/"),
        ("river-data-index.html", "https://wapda.gov.pk/category/river-data/"),
        ("daily-media.json", "https://wapda.gov.pk/wp-json/wp/v2/media?search=Daily-Data&per_page=100"),
        ("graph-media.json", "https://wapda.gov.pk/wp-json/wp/v2/media?search=GRAPH-DG&per_page=100"),
        ("river-search.json", "https://wapda.gov.pk/wp-json/wp/v2/search?search=river%20flow&per_page=100"),
    ]
    def check_wapda(item):
        name, url = item
        result, body = fetch_and_save(url, RAW / "wapda" / f"coverage_search_{args.as_of}" / name)
        if body:
            if name.endswith(".json"):
                data = json.loads(body)
                result["entries"] = [{key: row.get(key) for key in ("date", "url", "source_url", "title")} for row in data]
            else:
                soup = BeautifulSoup(body, "html.parser")
                result["download_links"] = sorted({a["href"] for a in soup.select("a[href]") if re.search(r"\.(xls[x]?|pdf)(?:$|\?)", a["href"], re.I)})
        return result
    with ThreadPoolExecutor(max_workers=3) as pool:
        checks.extend(pool.map(check_wapda, pages))

    irsa_url = "http://pakirsa.gov.pk/DailyData.aspx"
    index_check, body = fetch_and_save(irsa_url, RAW / "irsa" / f"coverage_search_{args.as_of}" / "daily-data.html")
    checks.append(index_check)
    urls = {}
    if body:
        soup = BeautifulSoup(body, "html.parser")
        for anchor in soup.select("a[href]"):
            match = re.search(r"Data(\d\d-\d\d-20\d\d)\.pdf$", anchor["href"], re.I)
            if match:
                day = datetime.strptime(match[1], "%d-%m-%Y").date()
                if date(2025, 1, 1) <= day <= args.as_of:
                    urls[day] = (urljoin(irsa_url, anchor["href"]), "linked_from_daily_data_page")
    # A small distributed sample tests retention; this is not a full archive crawl.
    for day_text in ("2025-01-01", "2025-04-01", "2025-07-01", "2025-10-01", "2025-12-31",
                     "2026-01-01", "2026-02-14", "2026-04-01", "2026-07-01", "2026-09-01", "2026-10-01", "2026-10-15"):
        day = date.fromisoformat(day_text)
        if day <= args.as_of:
            urls.setdefault(day, (f"http://pakirsa.gov.pk/Doc/Data{day:%d-%m-%Y}.pdf", "historical_retention_probe"))

    def check_irsa(item):
        day, (url, discovery) = item
        result, pdf = fetch_and_save(url, RAW / "irsa" / "daily_reports" / f"Data{day:%d-%m-%Y}.pdf")
        result["discovery"] = discovery
        row = None
        if pdf:
            try:
                row = parse_irsa(pdf, day)
                row.update(source_url=url, source_file=result["raw_file"], source_sha256=result["sha256"])
            except (ValueError, IndexError, RuntimeError) as exc:
                result["parse_error"] = str(exc)
        return result, row
    irsa_rows = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for check, row in pool.map(check_irsa, sorted(urls.items())):
            checks.append(check)
            if row:
                irsa_rows.append(row)
    if irsa_rows:
        with (OUTPUT / "marala_irsa_daily_mean_discharge.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(irsa_rows[0]))
            writer.writeheader()
            writer.writerows(irsa_rows)
    report = {
        "checked_utc": datetime.now(timezone.utc).isoformat(), "as_of": args.as_of.isoformat(),
        "complete_year_round_2025_2026_archive_confirmed": False,
        "irsa_records_saved": len(irsa_rows), "checks": checks,
        "scope": "WAPDA public pages and search/media endpoints, IRSA linked daily PDFs, and 12 distributed historical IRSA URL probes. Search is not proof that no archive exists.",
        "measurement_warning": "IRSA labels Marala mean U/S discharge. Do not append daily means to WAPDA/FFD dated point readings. Averaging-period bounds are not stated.",
        "next_access_route": "Request machine-readable daily Marala inflow, observation definition, timestamps, QC and corrections from WAPDA H&WM/WRMD and/or IRSA. No request has been sent.",
    }
    (OUTPUT / "marala_recent_source_search_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(checks)} source checks and {len(irsa_rows)} separate IRSA daily-mean records.")


if __name__ == "__main__":
    main()
