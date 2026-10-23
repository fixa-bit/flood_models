"""Extract the dated Marala inflow column from WAPDA's original XLS workbook.

Requires xlrd: python -m pip install xlrd
Run from any working directory: python extract_wapda_marala.py
"""

import csv
import hashlib
import json
from collections import Counter
from decimal import Decimal
from pathlib import Path

import xlrd


MODEL_DIR = Path(__file__).resolve().parents[1]
SOURCE_DIR = MODEL_DIR / "raw" / "marala" / "discharge" / "wapda"
SOURCE = SOURCE_DIR / "GRAPH-DG-16-for-MAIL-2.xls"
RECEIPT = SOURCE_DIR / "source_receipt.json"
OUTPUT_DIR = MODEL_DIR / "processed" / "marala" / "discharge"
OUTPUT_CSV = OUTPUT_DIR / "marala_wapda_daily_inflow.csv"
OUTPUT_REPORT = OUTPUT_DIR / "marala_wapda_extraction_report.json"


def main() -> None:
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    actual_sha256 = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if actual_sha256 != receipt["sha256"]:
        raise ValueError("WAPDA workbook differs from its recorded source checksum")

    workbook = xlrd.open_workbook(str(SOURCE))
    sheet = workbook.sheet_by_name("GHRAPH")
    if "CHENAB INFLOW AT MARALA" not in str(sheet.cell_value(2, 8)):
        raise ValueError("Marala column label changed; inspect the workbook")
    rows = []
    ignored_blank_rows = 0
    for row_index in range(6, sheet.nrows):
        date_serial = sheet.cell_value(row_index, 0)
        if not isinstance(date_serial, (float, int)):
            raise ValueError(f"Unexpected date at Excel row {row_index + 1}")
        date = xlrd.xldate_as_datetime(date_serial, workbook.datemode).date()
        value = sheet.cell_value(row_index, 8)
        if value == "":
            ignored_blank_rows += 1
            continue
        if not isinstance(value, (float, int)) or value < 0:
            raise ValueError(f"Invalid Marala inflow at Excel row {row_index + 1}: {value!r}")
        thousands = Decimal(str(value))
        cusecs = thousands * 1000
        flag = "zero_needs_review" if value == 0 else ""
        rows.append((date, thousands, cusecs, row_index + 1, flag))

    dates = [item[0] for item in rows]
    if not dates or dates != sorted(dates) or len(dates) != len(set(dates)):
        raise ValueError("Dates are empty, unsorted, or duplicated")
    gap_days = (dates[-1] - dates[0]).days + 1 - len(dates)
    if gap_days:
        raise ValueError(f"Found {gap_days} missing dates within observed coverage")

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    with OUTPUT_CSV.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["date", "marala_inflow_1000_cusecs", "marala_inflow_cusecs", "source_excel_row", "quality_flag", "source_url"])
        for date, thousands, cusecs, excel_row, flag in rows:
            writer.writerow([date.isoformat(), str(thousands), str(cusecs), excel_row, flag, receipt["source_url"]])

    report = {
        "source_url": receipt["source_url"],
        "source_file": str(SOURCE.relative_to(MODEL_DIR)).replace("\\", "/"),
        "source_sha256": actual_sha256,
        "sheet": sheet.name,
        "date_column": "A",
        "marala_inflow_column": "I",
        "first_date": dates[0].isoformat(),
        "last_date": dates[-1].isoformat(),
        "observation_count": len(rows),
        "internal_missing_dates": gap_days,
        "blank_trailing_marala_rows_ignored": ignored_blank_rows,
        "zero_values_for_review": [date.isoformat() for date, value, _, _, _ in rows if value == 0],
        "year_counts": dict(sorted(Counter(str(date.year) for date in dates).items())),
        "units": "1000 cusecs in workbook; cusecs derived by multiplying by 1000",
        "time_basis": "WAPDA's companion 19 Dec 2024 Press sheet labels Marala as 'At 0600 hrs' and matches the historical value (5.8 thousand cusecs = 5800 cusecs). Likely 06:00 Pakistan time reporting convention; historical sheet itself lists dates only, so the convention is not individually proven for every row.",
        "quality_note": "Values copied without imputation or correction. Blank quality_flag means no specific anomaly was identified; it does not certify the measurement. Zero flagged for review.",
    }
    OUTPUT_REPORT.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Extracted {len(rows)} Marala readings: {dates[0]} to {dates[-1]}")
    print(f"Zero dates requiring review: {report['zero_values_for_review']}")
    print(f"Saved {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
