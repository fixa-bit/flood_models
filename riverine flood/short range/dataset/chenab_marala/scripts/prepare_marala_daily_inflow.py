"""Prepare a reviewed, date-indexed WAPDA baseline and recent coverage calendar.

Requires xlrd and pymupdf. Run after extraction/collection and catalog building:
python prepare_marala_daily_inflow.py --as-of 2026-10-23
Source observations are never interpolated, averaged across sources, or corrected.
"""

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pymupdf
import xlrd

MODEL = Path(__file__).resolve().parents[1]
OUTPUT = MODEL / "processed/marala/discharge"
CUBIC_FOOT_M3 = Decimal("0.028316846592")


def read_csv(name):
    with (OUTPUT / name).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def write_csv(name, rows):
    with (OUTPUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def days(start, end):
    while start <= end:
        yield start.isoformat()
        start += timedelta(days=1)


def missing_spans(dates):
    spans = []
    for day in sorted(dates):
        if spans and date.fromisoformat(day) == date.fromisoformat(spans[-1]["end"]) + timedelta(days=1):
            spans[-1]["end"] = day
            spans[-1]["days"] += 1
        else:
            spans.append({"start": day, "end": day, "days": 1})
    return spans


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--as-of", type=date.fromisoformat, required=True)
    args = parser.parse_args()
    wapda = read_csv("marala_wapda_daily_inflow.csv")
    by_date = {r["date"]: r for r in wapda}
    if len(by_date) != len(wapda):
        raise ValueError("Duplicate WAPDA dates")
    expected = list(days(date.fromisoformat(min(by_date)), date.fromisoformat(max(by_date))))
    if [r["date"] for r in wapda] != expected:
        raise ValueError("WAPDA rows must be sorted and daily without gaps")
    receipt = json.loads((MODEL / "raw/marala/discharge/wapda/source_receipt.json").read_text(encoding="utf-8"))
    workbook_path = MODEL / "raw/marala/discharge/wapda" / receipt["filename"]
    if hashlib.sha256(workbook_path.read_bytes()).hexdigest() != receipt["sha256"]:
        raise ValueError("WAPDA workbook hash differs from receipt")
    workbook = xlrd.open_workbook(str(workbook_path))
    sheet = workbook.sheet_by_name("GHRAPH")
    for row in wapda:
        excel_row = int(row["source_excel_row"]) - 1
        if xlrd.xldate_as_datetime(sheet.cell_value(excel_row, 0), workbook.datemode).date().isoformat() != row["date"]:
            raise ValueError(f"Extraction date mismatch on Excel row {excel_row + 1}")
        if Decimal(str(sheet.cell_value(excel_row, 8))) * 1000 != Decimal(row["marala_inflow_cusecs"]):
            raise ValueError(f"Extraction mismatch with WAPDA workbook on {row['date']}")

    comparisons = defaultdict(list)
    issues = []
    issues_by_date = defaultdict(list)
    for year in (2024, 2025, 2026):
        for ffd in read_csv(f"marala_ffd_{year}_bulletin_discharge.csv"):
            if ffd["date"] not in by_date:
                continue
            day = ffd["date"]
            w = by_date[day]
            delta = Decimal(ffd["marala_inflow_1000_cusecs"]) * 1000 - Decimal(w["marala_inflow_cusecs"])
            comparisons[day].append({"delta": delta, "ffd": ffd})
            if not delta:
                continue
            raw = MODEL / f"raw/marala/discharge/ffd/bulletins_{year}" / ffd["raw_file"]
            if hashlib.sha256(raw.read_bytes()).hexdigest() != ffd["source_sha256"]:
                raise ValueError(f"FFD hash differs for {raw}")
            with pymupdf.open(raw) as document:
                text = "\n".join(page.get_text() for page in document)
            match = re.search(r"\bMarala\s*\n\s*\d{3,4}\s*\n\s*([\d,.]+)\s*\n\s*([\d,.]+)", text)
            if not match or Decimal(match[1].replace(",", "")) != Decimal(ffd["marala_inflow_1000_cusecs"]):
                raise ValueError("FFD raw table differs from extracted value")
            archive_day = ffd.get("archive_listed_date", day)
            note = "Both extracted values match their original files. No replacement authorized by evidence."
            if archive_day != day:
                note += f" PDF date {day} differs from archive date {archive_day}."
                if archive_day in by_date and Decimal(by_date[archive_day]["marala_inflow_cusecs"]) == Decimal(ffd["marala_inflow_1000_cusecs"]) * 1000:
                    note += " FFD value matches WAPDA on the archive-listed date; that alone does not confirm a correction."
            if ffd["archive_id"] == "61" and year == 2024:
                note += " FFD inflow also equals WAPDA's 2024-06-15 value; a source date/template error is possible but unconfirmed."
            issue = {
                "review_id": f"FFD-{year}-{ffd['archive_id']}", "date": day,
                "issue": "cross_source_disagreement", "wapda_inflow_cusecs": w["marala_inflow_cusecs"],
                "ffd_inflow_cusecs": str(Decimal(ffd["marala_inflow_1000_cusecs"]) * 1000),
                "ffd_minus_wapda_cusecs": str(delta), "ffd_archive_listed_date": archive_day,
                "ffd_printed_date": day, "status": "unresolved_withheld_from_training",
                "wapda_excel_row": w["source_excel_row"], "wapda_url": w["source_url"],
                "ffd_url": ffd["source_url"], "ffd_source_file": raw.relative_to(MODEL).as_posix(),
                "source_excerpt": " ".join(match[0].split()), "review_notes": note,
            }
            issues.append(issue)
            issues_by_date[day].append(issue["review_id"])

    for w in wapda:
        if Decimal(w["marala_inflow_cusecs"]) == 0:
            day = w["date"]
            previous = by_date.get((date.fromisoformat(day) - timedelta(days=1)).isoformat(), {}).get("marala_inflow_cusecs", "unknown")
            following = by_date.get((date.fromisoformat(day) + timedelta(days=1)).isoformat(), {}).get("marala_inflow_cusecs", "unknown")
            issue = {key: "" for key in issues[0]} if issues else {
                key: "" for key in ("review_id", "date", "issue", "wapda_inflow_cusecs", "ffd_inflow_cusecs", "ffd_minus_wapda_cusecs", "ffd_archive_listed_date", "ffd_printed_date", "status", "wapda_excel_row", "wapda_url", "ffd_url", "ffd_source_file", "source_excerpt", "review_notes")}
            issue.update(review_id=f"WAPDA-ZERO-{day}", date=day, issue="zero_needs_review", wapda_inflow_cusecs="0",
                         status="unresolved_withheld_from_training", wapda_excel_row=w["source_excel_row"], wapda_url=w["source_url"],
                         source_excerpt=f"GHRAPH row {w['source_excel_row']}, Marala column I: numeric 0.0 (not an empty cell).",
                         review_notes=f"Previous day {previous} cusecs; following day {following} cusecs. A real zero or reporting error cannot be distinguished from this workbook; retained as source value, no interpolation.")
            issues.append(issue)
            issues_by_date[day].append(issue["review_id"])
    issues.sort(key=lambda row: (row["date"], row["review_id"]))
    write_csv("marala_inflow_quality_review.csv", issues)

    catalog = {r["date"]: r for r in read_csv("marala_discharge_all_sources.csv") if r["source"] == "WAPDA"}
    clean = []
    for row in wapda:
        day = row["date"]
        flags = [row["quality_flag"]] if row["quality_flag"] else []
        disagreement_count = sum(bool(c["delta"]) for c in comparisons[day])
        if disagreement_count:
            flags.append("cross_source_disagreement")
        eligible = not flags
        value = Decimal(row["marala_inflow_cusecs"])
        clean.append({
            "date": day, "source_inflow_cusecs": row["marala_inflow_cusecs"],
            "inflow_cusecs": str(value) if eligible else "",
            "inflow_m3_s": str((value * CUBIC_FOOT_M3).quantize(Decimal("0.000001"))) if eligible else "",
            "time_pakistan": catalog[day]["time_pakistan"], "datetime_pakistan": catalog[day]["datetime_pakistan"],
            "time_status": catalog[day]["time_status"], "measurement_basis": "dated_wapda_inflow_not_confirmed_daily_mean",
            "eligible_daily_training": int(eligible), "quality_flag": ";".join(flags),
            "source": "WAPDA", "source_url": row["source_url"], "source_file": workbook_path.relative_to(MODEL).as_posix(),
            "source_excel_row": row["source_excel_row"], "ffd_comparison_count": len(comparisons[day]),
            "ffd_disagreement_count": disagreement_count, "review_ids": ";".join(issues_by_date.get(day, [])),
        })
    write_csv("marala_daily_inflow_clean.csv", clean)

    ffd_recent = defaultdict(list)
    for year in (2025, 2026):
        for row in read_csv(f"marala_ffd_{year}_bulletin_discharge.csv"):
            ffd_recent[row["date"]].append(row)
    irsa_path = OUTPUT / "marala_irsa_daily_mean_discharge.csv"
    irsa = {r["date"]: r for r in read_csv(irsa_path.name)} if irsa_path.exists() else {}
    calendar = []
    for day in days(date(2025, 1, 1), args.as_of):
        rows = ffd_recent[day]
        safe = len(rows) == 1 and rows[0].get("date_status", "matches_archive") == "matches_archive" and rows[0]["observation_time"] == "06:00 PKT"
        calendar.append({"date": day, "ffd_bulletin_count": len(rows),
                         "ffd_status": "available_unique_0600" if safe else ("date_or_duplicate_conflict" if rows else "missing"),
                         "ffd_inflow_cusecs": str(Decimal(rows[0]["marala_inflow_1000_cusecs"]) * 1000) if safe else "",
                         "ffd_source_urls": ";".join(r["source_url"] for r in rows),
                         "irsa_mean_inflow_cusecs": irsa.get(day, {}).get("mean_inflow_cusecs", ""),
                         "irsa_source_url": irsa.get(day, {}).get("source_url", ""),
                         "note": "IRSA mean does not fill a missing 06:00 observation." if day in irsa else ""})
    write_csv("marala_2025_2026_coverage.csv", calendar)
    report = {
        "built_utc": datetime.now(timezone.utc).isoformat(), "as_of": args.as_of.isoformat(),
        "baseline": {"rows": len(clean), "first_date": expected[0], "last_date": expected[-1],
                     "eligible_daily_training_rows": sum(r["eligible_daily_training"] for r in clean),
                     "withheld_dates": sorted(issues_by_date), "confirmed_time_rows": sum(bool(r["time_pakistan"]) for r in clean),
                     "unknown_time_rows": sum(not r["time_pakistan"] for r in clean),
                     "ffd_comparisons": sum(len(v) for v in comparisons.values()),
                     "exact_ffd_value_matches": sum(not c["delta"] for v in comparisons.values() for c in v)},
        "policy": "WAPDA is the baseline source. Keep all daily dates and source values. Blank modeling values and exclude all unresolved zeros or disagreements. Never average sources, impute gaps, or transfer FFD times onto WAPDA dates. Eligibility is for date-level research only, not an assertion of certified hydrological accuracy or operational availability.",
        "training_window_rule": "Require consecutive calendar dates and eligible observations throughout each input window and all 15 target days; do not drop missing dates and join across gaps. Chronological split selection remains to be implemented before training.",
        "recent_coverage": {},
    }
    for year in (2025, 2026):
        subset = [r for r in calendar if r["date"].startswith(str(year))]
        missing = [r["date"] for r in subset if r["ffd_status"] == "missing"]
        report["recent_coverage"][str(year)] = {
            "calendar_days_through_as_of": len(subset), "ffd_status_counts": dict(Counter(r["ffd_status"] for r in subset)),
            "missing_point_reading_spans": missing_spans(missing),
            "dates_with_only_separate_irsa_means": [r["date"] for r in subset if r["irsa_mean_inflow_cusecs"] and r["ffd_status"] == "missing"],
        }
    (OUTPUT / "marala_daily_inflow_quality_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Prepared {len(clean)} daily dates: {report['baseline']['eligible_daily_training_rows']} eligible, {len(issues_by_date)} withheld. Saved quality review and recent coverage calendar.")


if __name__ == "__main__":
    main()
