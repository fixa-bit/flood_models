"""Combine collected Marala discharge records without inventing observation times.

Run from any directory: python build_marala_discharge_catalog.py
"""

import csv
import json
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path


MODEL_DIR = Path(__file__).resolve().parents[1]
PROCESSED = MODEL_DIR / "processed" / "marala" / "discharge"
OUTPUT = PROCESSED / "marala_discharge_all_sources.csv"
FIELDS = [
    "date", "time_pakistan", "datetime_pakistan", "time_status", "river", "station",
    "record_kind", "measurement", "discharge_cusecs", "source", "source_url",
    "source_file", "quality_flag", "notes",
]


def read_csv(name: str):
    with (PROCESSED / name).open(newline="", encoding="utf-8") as handle:
        yield from csv.DictReader(handle)


def cusecs_from_thousands(value: str) -> str:
    return str(Decimal(value) * 1000)


def make_row(date, time, kind, measurement, value, source, url, source_file, quality="", notes="", time_status=None):
    if time and time != "06:00 PKT":
        raise ValueError(f"Unrecognized time label: {time}")
    return {
        "date": date,
        "time_pakistan": "06:00" if time else "",
        "datetime_pakistan": f"{date}T06:00:00+05:00" if time else "",
        "time_status": time_status or ("explicit_in_source" if time else "not_given_for_individual_record"),
        "river": "Chenab",
        "station": "Marala",
        "record_kind": kind,
        "measurement": measurement,
        "discharge_cusecs": value,
        "source": source,
        "source_url": url,
        "source_file": source_file,
        "quality_flag": quality,
        "notes": notes,
    }


def main():
    records = []
    wapda_by_date = {}
    for row in read_csv("marala_wapda_daily_inflow.csv"):
        wapda_by_date[row["date"]] = Decimal(row["marala_inflow_cusecs"])
        companion_confirmed = row["date"] == "2024-12-19"
        records.append(make_row(
            row["date"], "06:00 PKT" if companion_confirmed else "", "dated_discharge_observation", "inflow",
            row["marala_inflow_cusecs"], "WAPDA", row["source_url"],
            "raw/marala/discharge/wapda/GRAPH-DG-16-for-MAIL-2.xls",
            row["quality_flag"],
            "Historical workbook labels the date but not each row's time."
            if not companion_confirmed else
            "Companion WAPDA report confirms this day's Marala reading at 06:00: https://wapda.gov.pk/wp-content/uploads/2024/12/Daily-DataPress-Release-19-12-2024.xls",
            time_status="confirmed_by_companion_report" if companion_confirmed else None,
        ))

    for year in (2024, 2025, 2026):
        for row in read_csv(f"marala_ffd_{year}_bulletin_discharge.csv"):
            flags = []
            notes = ["Flood-season bulletin reading at 06:00 Pakistan time."]
            if row.get("date_status") == "printed_date_differs_from_archive":
                flags.append("printed_date_differs_from_archive")
                notes.append(f"Archive lists {row['archive_listed_date']}; PDF prints {row['date']}.")
            if row["date"] in wapda_by_date and Decimal(row["marala_inflow_1000_cusecs"]) * 1000 != wapda_by_date[row["date"]]:
                flags.append("bulletin_inflow_differs_from_wapda")
                notes.append(f"WAPDA inflow for this printed date: {wapda_by_date[row['date']]} cusecs.")
            for measurement in ("inflow", "outflow"):
                records.append(make_row(
                    row["date"], row["observation_time"], "dated_discharge_observation", measurement,
                    cusecs_from_thousands(row[f"marala_{measurement}_1000_cusecs"]), "FFD/PMD",
                    row["source_url"],
                    f"raw/marala/discharge/ffd/bulletins_{year}/{row['raw_file']}",
                    quality=";".join(flags),
                    notes=" ".join(notes),
                ))

    for row in read_csv("marala_pmd_historical_flood_peaks.csv"):
        records.append(make_row(
            row["peak_date"], "", "selected_historical_event_peak", "peak_discharge",
            cusecs_from_thousands(row["peak_discharge_1000_cusecs"]), "PMD journal",
            row["source_url"],
            "raw/marala/discharge/pmd/marala_historical_flood_peaks_pmd_journal.pdf",
            notes=f"Published flood level: {row['flood_level_as_published']}. Event peak; not a daily 06:00 reading.",
        ))

    if (PROCESSED / "marala_irsa_daily_mean_discharge.csv").exists():
        for row in read_csv("marala_irsa_daily_mean_discharge.csv"):
            for measurement in ("inflow", "outflow"):
                records.append(make_row(
                    row["date"], "", "daily_mean_discharge", f"mean_{measurement}",
                    row[f"mean_{measurement}_cusecs"], "IRSA", row["source_url"], row["source_file"],
                    notes="Daily mean as labeled by IRSA; averaging-period bounds not stated. Keep separate from WAPDA/FFD dated point readings.",
                    time_status=row["time_status"],
                ))

    records.sort(key=lambda item: (item["date"], item["time_pakistan"], item["source"], item["measurement"]))
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(records)
    counts = Counter((item["source"], item["record_kind"], item["measurement"]) for item in records)
    report = {
        "built_utc": datetime.now(timezone.utc).isoformat(),
        "row_count": len(records),
        "rows_with_record_time": sum(bool(item["time_pakistan"]) for item in records),
        "rows_without_individually_confirmed_time": sum(not item["time_pakistan"] for item in records),
        "counts": [
            {"source": source, "record_kind": kind, "measurement": measure, "rows": count}
            for (source, kind, measure), count in sorted(counts.items())
        ],
        "note": "Event peaks, daily means, and dated observations are distinct record kinds. Empty time is intentional; no time was invented. Gaps and overlapping sources are not filled or merged.",
    }
    (PROCESSED / "marala_discharge_all_sources_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(records)} discharge records to {OUTPUT}")
    print(f"Known time: {report['rows_with_record_time']}; unspecified time: {report['rows_without_individually_confirmed_time']}")


if __name__ == "__main__":
    main()
