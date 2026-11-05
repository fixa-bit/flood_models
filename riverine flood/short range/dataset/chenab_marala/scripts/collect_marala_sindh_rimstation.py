"""Collect observed Marala inflow (U/S) and outflow (D/S) from Sindh Irrigation rim-station bulletins.

The Sindh Irrigation Department publishes a daily bulletin "Inflow+Outflow (Rimstations + Main
Indus River)", values in cusecs, at https://irrigation.sindh.gov.pk/Flows/Rimstation. Each PDF is a
Microsoft Print-to-PDF export of a spreadsheet holding a rolling table of recent dates, so the
numbers are read from the PDF text layer (no OCR). Column headers are images: their order was
checked visually (see the raw-folder README) and every parsed row must hold 21 aligned values.

Requires pymupdf. Run from any directory:
    python -I collect_marala_sindh_rimstation.py download
    python -I collect_marala_sindh_rimstation.py extract
"""

import argparse
import csv
import hashlib
import json
import re
import statistics
import time
import urllib.error
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = MODEL_DIR / "raw" / "marala" / "discharge" / "sindh_irrigation"
BULLETIN_DIR = RAW_DIR / "rimstation_bulletins"
RECEIPT = RAW_DIR / "source_receipt.json"
PROCESSED_DIR = MODEL_DIR / "processed" / "marala" / "discharge"
OUTPUT = PROCESSED_DIR / "marala_sindh_rimstation_discharge.csv"
REPORT = PROCESSED_DIR / "marala_sindh_rimstation_collection_report.json"
PAGE_URL = "https://irrigation.sindh.gov.pk/Flows/Rimstation"
INDEX_URL = "https://api.hicsindh.pk/public/FlowBulletins/IndusRiver_Rimstation"
SITE = "https://irrigation.sindh.gov.pk"
USER_AGENT = "Mozilla/5.0 (Marala discharge research; public Sindh Irrigation bulletins)"
CUSEC_M3_S = 0.028316846592
COLUMNS = ["tarbela_inflow", "tarbela_outflow", "kabul_nowshera", "mangla_inflow", "mangla_outflow",
           "marala_us", "marala_ds", "kalabagh_us", "kalabagh_ds", "chashma_us", "chashma_ds", "cj_link",
           "taunsa_us", "taunsa_ds", "tp_link", "guddu_us", "guddu_ds", "sukkur_us", "sukkur_ds",
           "kotri_us", "kotri_ds"]
MARALA_US, MARALA_DS = COLUMNS.index("marala_us"), COLUMNS.index("marala_ds")
DATE_TOKEN = re.compile(r"^(\d{2})/(\d{2})/(\d{2})$")
NUMBER_TOKEN = re.compile(r"^-?\d+(?:\.\d+)?$")


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def fetch(url: str) -> tuple[bytes, str]:
    for attempt in range(4):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=60) as response:
                return response.read(), response.headers.get("Content-Type", "")
        except (urllib.error.URLError, TimeoutError):
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    raise RuntimeError("unreachable")


def download(workers: int) -> None:
    body, content_type = fetch(INDEX_URL)
    index = json.loads(body)
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8")) if RECEIPT.exists() else {"files": {}}
    receipt.update({
        "content": "OBSERVED discharge bulletins as published (values in cusecs)",
        "publisher": "Irrigation Department, Government of Sindh (HIC Sindh)",
        "page": PAGE_URL,
        "index": {"url": INDEX_URL, "retrieved_utc": utc_now(), "sha256": hashlib.sha256(body).hexdigest(),
                  "content_type": content_type, "minDate": index["minDate"], "maxDate": index["maxDate"],
                  "file_url_prefix": SITE + "/" + index["url"].strip("/") + "/", "listed_bulletins": len(index["pictures"]),
                  "pictures": index["pictures"]},
    })
    BULLETIN_DIR.mkdir(parents=True, exist_ok=True)

    def get(picture: dict) -> tuple[str, dict | None]:
        name = picture["fileName"]
        target = BULLETIN_DIR / name
        if name in receipt["files"] and target.exists():
            return name, None
        url = receipt["index"]["file_url_prefix"] + name
        data, kind = fetch(url)
        if not data.startswith(b"%PDF"):
            raise ValueError(f"{name}: not a PDF ({kind})")
        target.write_bytes(data)
        return name, {"listed_date": picture["getDate"][:10], "url": url, "content_type": kind,
                      "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest(), "retrieved_utc": utc_now()}

    failures = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(get, picture) for picture in index["pictures"]]
        for future in as_completed(futures):
            try:
                name, record = future.result()
                if record:
                    receipt["files"][name] = record
            except Exception as error:
                failures.append(f"{type(error).__name__}: {error}")
    receipt["files"] = dict(sorted(receipt["files"].items(), key=lambda item: item[1]["listed_date"]))
    receipt["download_failures"] = failures
    RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(f"{len(receipt['files'])} bulletins saved; {len(failures)} failures")
    for failure in failures:
        print(failure)


def parse_bulletin(path: Path) -> dict:
    """Return the dated rows of one bulletin, with values assigned to columns by x-position."""
    import pymupdf

    rows = []
    with pymupdf.open(path) as document:
        for page in document:
            words = []
            for x0, y0, x1, y1, word, *_ in page.get_text("words"):
                box = pymupdf.Rect(x0, y0, x1, y1) * page.rotation_matrix  # some pages are stored rotated
                words.append(((box.y0 + box.y1) / 2, (box.x0 + box.x1) / 2, word))
            words.sort()
            lines, current = [], []
            for y, x, word in words:  # a new table row starts more than 4 pt below the current one
                if current and y - statistics.mean(item[0] for item in current) > 4:
                    lines.append(current)
                    current = []
                current.append((y, x, word))
            lines.append(current)
            for line in lines:
                cells = sorted((x, word) for _, x, word in line)
                position = next((i for i, (_, word) in enumerate(cells) if DATE_TOKEN.match(word)), None)
                if position is None:  # title, header and note lines
                    continue
                day, month, year = (int(group) for group in DATE_TOKEN.match(cells[position][1]).groups())
                try:
                    printed = date(2000 + year, month, day)
                except ValueError:  # impossible printed date, e.g. 31/09: reported, never guessed
                    printed = None
                # A lone "#" is the trend-arrow glyph of a cell whose formula failed; it carries no value.
                values = [(x, word) for x, word in cells[position + 1:] if word != "#"]
                rows.append({"date": printed, "printed_date": cells[position][1], "tokens": values})
    full = [row for row in rows if len(row["tokens"]) == len(COLUMNS)
            and all(NUMBER_TOKEN.match(word) for _, word in row["tokens"])]
    centres = [statistics.median(row["tokens"][i][0] for row in full) for i in range(len(COLUMNS))] if full else []
    spacing = min(b - a for a, b in zip(centres, centres[1:])) if centres else 0
    parsed = []
    for row in rows:
        cells, status = [None] * len(COLUMNS), "ok"
        if row["date"] is None:
            status = "invalid_printed_date"
        elif not centres:
            status = "no_complete_row_for_column_positions"
        else:
            for x, word in row["tokens"]:
                column = min(range(len(COLUMNS)), key=lambda i: abs(centres[i] - x))
                if abs(centres[column] - x) > spacing / 2 or cells[column] is not None:
                    status = "unaligned_token"
                elif NUMBER_TOKEN.match(word):
                    cells[column] = float(word)
                else:
                    cells[column] = word  # spreadsheet error text such as "#REF!"
            if status == "ok" and not all(isinstance(cell, float) for cell in cells):
                status = "blank_or_error_cells"
        parsed.append({"date": row["date"], "printed_date": row["printed_date"], "status": status,
                       "n_tokens": len(row["tokens"]),
                       "marala_us": cells[MARALA_US], "marala_ds": cells[MARALA_DS]})
    return {"rows": parsed, "complete_rows": len(full)}


def number(value) -> float | None:
    return value if isinstance(value, float) else None


def load_reference(path: Path, date_column: str, value_column: str, scale: float = 1.0) -> dict:
    values = {}
    with path.open(encoding="utf-8") as handle:
        for record in csv.DictReader(handle):
            text = (record.get(value_column) or "").strip()
            if text:
                values.setdefault(record[date_column], []).append(float(text) * scale)
    return values


def agrees(ours: float, theirs: float) -> bool:
    """WAPDA and FFD print to the nearest 100 cusecs and differ from each other by up to ~0.2%."""
    return abs(ours - theirs) <= max(100.0, 0.005 * abs(theirs))


def compare(selected: dict, reference: dict, field: str, list_all: bool) -> dict:
    """Agreement per date: a date agrees when any of the source's rows for it agrees."""
    days = sorted(day for day in reference if day in selected and selected[day][field] is not None)
    if not days:
        return {"dates": 0}
    outside = [{"date": day, "sindh": selected[day][field], "reference": reference[day]} for day in days
               if not any(agrees(selected[day][field], value) for value in reference[day])]
    relative = sorted(min(abs(selected[day][field] - value) / value for value in reference[day] if value) for day in days)
    return {"dates": len(days), "first": days[0], "last": days[-1], "agreeing": len(days) - len(outside),
            "agreeing_share": round(1 - len(outside) / len(days), 3),
            "median_abs_relative_difference": round(relative[len(relative) // 2], 4),
            "disagreeing": outside if list_all else outside[:5]}


def extract() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    reports = defaultdict(list)
    statuses, tokens, problems, non_table = Counter(), Counter(), [], []
    for name, record in receipt["files"].items():
        path = BULLETIN_DIR / name
        if hashlib.sha256(path.read_bytes()).hexdigest() != record["sha256"]:
            raise ValueError(f"{name}: checksum differs from receipt")
        bulletin = parse_bulletin(path)
        if bulletin["complete_rows"] == 0:  # e.g. a chart pack listed among the bulletins
            non_table.append(name)
            continue
        issue = date.fromisoformat(record["listed_date"])
        for row in bulletin["rows"]:
            statuses[row["status"]] += 1
            tokens[row["n_tokens"]] += 1
            if row["date"] and row["date"] > issue:
                problems.append({"file": name, "printed_date": row["printed_date"], "issue": "row dated after listed date"})
            if row["status"] in ("ok", "blank_or_error_cells"):
                reports[row["date"]].append({"issue": issue, "file": name, "us": number(row["marala_us"]),
                                             "ds": number(row["marala_ds"])})
                if row["marala_us"] is None or isinstance(row["marala_us"], str):
                    problems.append({"file": name, "printed_date": row["printed_date"],
                                     "issue": f"marala_us not numeric: {row['marala_us']!r}"})
            else:
                problems.append({"file": name, "printed_date": row["printed_date"], "issue": row["status"]})

    references = {
        "wapda_inflow": (load_reference(PROCESSED_DIR / "marala_wapda_daily_inflow.csv", "date", "marala_inflow_cusecs"), "inflow"),
        "irsa_daily_mean_inflow": (load_reference(PROCESSED_DIR / "marala_irsa_daily_mean_discharge.csv", "date", "mean_inflow_cusecs"), "inflow"),
        "irsa_daily_mean_outflow": (load_reference(PROCESSED_DIR / "marala_irsa_daily_mean_discharge.csv", "date", "mean_outflow_cusecs"), "outflow"),
    }
    for year in (2024, 2025, 2026):
        path = PROCESSED_DIR / f"marala_ffd_{year}_bulletin_discharge.csv"
        references[f"ffd_{year}_0600_inflow"] = (load_reference(path, "date", "marala_inflow_1000_cusecs", 1000), "inflow")
        references[f"ffd_{year}_0600_outflow"] = (load_reference(path, "date", "marala_outflow_1000_cusecs", 1000), "outflow")
    same_basis = [name for name in references if name == "wapda_inflow" or (name.startswith("ffd_") and name.endswith("_inflow"))]

    selected, output, revised, placeholders = {}, [], [], 0
    for day in sorted(reports):
        seen = sorted(reports[day], key=lambda report: (report["issue"], report["file"]))
        placeholders += sum(report["us"] == 0 for report in seen)
        # Marala inflow is never zero: a 0 is an unfilled row of the newest date, not a reading.
        valid = [report for report in seen if report["us"] not in (None, 0.0)]
        counts = Counter((report["us"], report["ds"]) for report in valid)
        if valid:  # the most frequently printed pair; ties go to the latest bulletin
            latest = [report for report in valid if counts[(report["us"], report["ds"])] == max(counts.values())][-1]
        else:
            latest = seen[-1]
        inflows = {report["us"] for report in valid}
        outflows = {report["ds"] for report in valid if report["ds"] is not None}
        file = receipt["files"][latest["file"]]
        key = day.isoformat()
        selected[key] = {"inflow": latest["us"] or None, "outflow": latest["ds"] if valid else None}
        if len(inflows) > 1 or len(outflows) > 1:
            revised.append({"date": key, "printed_pairs": [{"inflow": us, "outflow": ds, "bulletins": n}
                                                           for (us, ds), n in counts.most_common()]})
        overlapping = {name: references[name][0][key] for name in same_basis if key in references[name][0]}
        conflicts = [name for name, values in overlapping.items()
                     if not selected[key]["inflow"] or not any(agrees(selected[key]["inflow"], v) for v in values)]
        check = "no_overlap" if not overlapping else ("conflict:" + ";".join(conflicts) if conflicts else "match")
        latest = latest if valid else {**latest, "us": None, "ds": None}
        output.append({
            "date": day.isoformat(),
            "inflow_cusecs": "" if latest["us"] is None else f"{latest['us']:.0f}",
            "outflow_cusecs": "" if latest["ds"] is None else f"{latest['ds']:.0f}",
            "inflow_m3_s": "" if latest["us"] is None else f"{latest['us'] * CUSEC_M3_S:.6f}",
            "outflow_m3_s": "" if latest["ds"] is None else f"{latest['ds'] * CUSEC_M3_S:.6f}",
            "bulletins_reporting": len(valid),
            "bulletins_printing_selected": counts[(latest["us"], latest["ds"])] if valid else 0,
            "value_revised": int(len(inflows) > 1 or len(outflows) > 1),
            "inflow_check_vs_wapda_ffd": check,
            "selected_bulletin_listed_date": latest["issue"].isoformat(),
            "source_file": f"raw/marala/discharge/sindh_irrigation/rimstation_bulletins/{latest['file']}",
            "source_url": file["url"],
            "source_sha256": file["sha256"],
        })
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(output)

    days = [date.fromisoformat(row["date"]) for row in output]
    missing, cursor = [], days[0]
    present = set(days)
    while cursor <= days[-1]:
        if cursor not in present:
            start = cursor
            while cursor not in present:
                cursor = date.fromordinal(cursor.toordinal() + 1)
            missing.append({"from": start.isoformat(), "to": date.fromordinal(cursor.toordinal() - 1).isoformat(),
                            "days": cursor.toordinal() - start.toordinal()})
        cursor = date.fromordinal(cursor.toordinal() + 1)

    report = {
        "created_utc": utc_now(),
        "output": OUTPUT.name,
        "bulletins_parsed": len(receipt["files"]) - len(non_table),
        "listed_files_without_a_table": non_table,
        "index_listed_range": [receipt["index"]["minDate"][:10], receipt["index"]["maxDate"][:10]],
        "column_order": COLUMNS,
        "column_order_check": "Header images inspected for bulletins listed 2024-08-19, 2024-10-07, 2025-01-10, 2025-03-22, "
                              "2025-07-15, 2025-10-01, 2025-10-15, 2025-12-13, 2026-01-15, 2026-04-04, 2026-06-15, "
                              "2026-08-01, 2026-09-01 and 2026-11-03: identical 21-column order.",
        "row_status_counts": dict(statuses),
        "values_per_row": {str(k): v for k, v in sorted(tokens.items())},
        "rows_with_problems": problems,
        "coverage": {"first": output[0]["date"], "last": output[-1]["date"], "dates": len(output),
                     "missing_ranges": missing,
                     "dates_with_blank_inflow": sum(row["inflow_cusecs"] == "" for row in output)},
        "selection_policy": "Each date takes the Marala U/S and D/S pair printed by the most bulletins (ties: the "
                            "latest-listed bulletin). Zero U/S values are unfilled rows and are ignored. value_revised "
                            "marks dates whose printed values differ between bulletins; treat them with caution.",
        "zero_inflow_placeholder_rows_ignored": placeholders,
        "revised_dates": revised,
        "inflow_check_counts": dict(Counter(row["inflow_check_vs_wapda_ffd"].split(":")[0] for row in output)),
        "agreement_with_existing_sources": {name: compare(selected, values, field, name in same_basis)
                                            for name, (values, field) in references.items()},
        "agreement_note": "WAPDA and FFD print to the nearest 100 cusecs; differences up to 100 cusecs or 0.5% (whichever "
                          "is larger) count as agreement. IRSA values are daily means, a different measurement basis.",
    }
    REPORT.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("bulletins_parsed", "row_status_counts", "coverage",
                                                   "inflow_check_counts")}, indent=2))
    for name, result in report["agreement_with_existing_sources"].items():
        print(name, {k: v for k, v in result.items() if k != "outside_rounding"})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    get = sub.add_parser("download", help="save the bulletin index and every listed PDF (resumable)")
    get.add_argument("--workers", type=int, default=4)
    sub.add_parser("extract", help="write the Marala table and its collection report")
    args = parser.parse_args()
    download(args.workers) if args.action == "download" else extract()


if __name__ == "__main__":
    main()
