"""Read-only audit of Desktop workbooks; writes reports only in qa/."""
import calendar
import csv
import hashlib
import json
import math
import re
from collections import Counter
from datetime import date, timedelta
from pathlib import Path

import xlrd
from openpyxl import load_workbook

SOURCE = Path(r'C:\Users\PC\Desktop\discharge')
OUT = Path(__file__).resolve().parent
CONVERSION = 0.028316846592


def numeric(value):
    return isinstance(value, (int, float)) and math.isfinite(value)


def raw_matrix(sheet):
    year, unit = None, 'not_explicitly_labeled'
    records = {}
    for i in range(sheet.nrows):
        a = sheet.cell_value(i, 0)
        if numeric(a) and 1900 <= a <= 2100:
            year, unit = int(a), 'not_explicitly_labeled'
        elif isinstance(a, str):
            match = re.search(r'\(Year\s*(\d{4})\)', a, re.I)
            if match:
                year, unit = int(match.group(1)), 'not_explicitly_labeled'
        for v in sheet.row_values(i):
            if isinstance(v, str):
                if re.search('cusec', v, re.I):
                    unit = 'cusecs'
                elif re.search(r'm3\s*/\s*s', v, re.I):
                    unit = 'm3/s'
        if not year or not numeric(a) or int(a) != a or not 1 <= a <= 31:
            continue
        for month in range(1, min(sheet.ncols, 13)):
            if a > calendar.monthrange(year, month)[1]:
                continue
            value = sheet.cell_value(i, month)
            if numeric(value):
                records[date(year, month, int(a)).isoformat()] = dict(value=value, unit=unit, row=i + 1, column=month + 1)
    return records


def audit(path):
    book = xlrd.open_workbook(path, on_demand=True)
    sheet = next((s for s in book.sheets() if 'rearrang' in s.name.casefold()), book.sheet_by_index(0))
    rows, bad_dates = [], []
    for i in range(1, sheet.nrows):
        cell = sheet.cell(i, 0)
        if cell.ctype not in (xlrd.XL_CELL_DATE, xlrd.XL_CELL_NUMBER):
            bad_dates.append(i + 1)
            continue
        try:
            dt = xlrd.xldate_as_datetime(cell.value, book.datemode)
            if dt.time().isoformat() != '00:00:00':
                raise ValueError('Non-midnight timestamp')
            day = dt.date().isoformat()
        except Exception:
            bad_dates.append(i + 1)
            continue
        rows.append((day, sheet.cell_value(i, 1)))
    dates = [d for d, _ in rows]
    values = {d: q for d, q in rows if numeric(q)}
    by_year = []
    for year in range(int(min(dates)[:4]), int(max(dates)[:4]) + 1):
        by_year.append(dict(file=path.name, year=year, calendar_days=366 if calendar.isleap(year) else 365,
                            dated_rows=sum(d.startswith(str(year)) for d in dates),
                            numeric_days=sum(d.startswith(str(year)) for d in values)))
    raw_checks = []
    for raw in book.sheets():
        if raw.name == sheet.name or not raw.nrows:
            continue
        matrix = raw_matrix(raw)
        if not matrix:
            continue
        compared, differences = 0, []
        for day, record in matrix.items():
            if day not in values:
                continue
            expected = record['value'] * (CONVERSION if record['unit'] == 'cusecs' else 1)
            compared += 1
            if not math.isclose(values[day], expected, rel_tol=0.001, abs_tol=0.1):
                differences.append(dict(date=day, raw_value=record['value'], raw_units=record['unit'],
                                        expected_with_standard_conversion=expected, rearranged_value=values[day],
                                        source_row=record['row'], source_column=record['column']))
        raw_checks.append(dict(sheet=raw.name, raw_numeric_dates=len(matrix),
                               raw_years=sorted({d[:4] for d in matrix}),
                               unit_counts=dict(Counter(r['unit'] for r in matrix.values())),
                               paired_dates_compared=compared,
                               mismatches_over_0_1percent_or_0_1_absolute=len(differences),
                               sample_differences=differences[:10],
                               numeric_years_present_only_in_rearranged=sorted({d[:4] for d in values} - {d[:4] for d in matrix})))
    header = [sheet.cell_value(0, i) for i in range(min(2, sheet.ncols))]
    strings = [c.value for s in book.sheets() for i in range(s.nrows) for c in s.row(i) if c.ctype == xlrd.XL_CELL_TEXT]
    source_labels = sorted({v for v in strings if re.search(r'WAPDA|SWHP|source', v, re.I)})
    report = dict(file=path.name, path=str(path), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                  sheet_layout=[dict(name=s.name, rows=s.nrows, columns=s.ncols) for s in book.sheets()],
                  audited_daily_sheet=sheet.name, header=header,
                  first_date=min(dates), last_date=max(dates), dated_rows=len(rows),
                  numeric_days=len(values), missing_discharge_rows=sum(not numeric(q) for _, q in rows),
                  duplicate_dates=sum(v - 1 for v in Counter(dates).values() if v > 1),
                  nonmonotonic_steps=sum(dates[i] < dates[i - 1] for i in range(1, len(dates))),
                  invalid_date_rows=bad_dates, zero_values=sum(q == 0 for q in values.values()),
                  negative_values=sum(q < 0 for q in values.values()),
                  min_saved_numeric=min(values.values()), max_saved_numeric=max(values.values()),
                  missing_years=[r['year'] for r in by_year if not r['numeric_days']],
                  partial_years=[r['year'] for r in by_year if 0 < r['numeric_days'] < r['calendar_days']],
                  missing_calendar_dates=(date.fromisoformat(max(dates)) - date.fromisoformat(min(dates))).days + 1 - len(set(dates)),
                  overlaps_marala_2016_2026=any('2016-03-01' <= d <= '2026-10-23' for d in values),
                  source_labels=source_labels, raw_to_rearranged_checks=raw_checks)
    book.release_resources()
    return report, by_year


def main():
    reports, years = [], []
    for path in sorted(SOURCE.glob('*.xls')):
        report, per_year = audit(path)
        reports.append(report)
        years.extend(per_year)
    documents = []
    for path in SOURCE.glob('*.xlsx'):
        book = load_workbook(path, read_only=True, data_only=True)
        documents.append(dict(file=path.name, sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                              sheets=[dict(name=s.title, rows=s.max_row, columns=s.max_column) for s in book],
                              classification='Climate/disaster UAV monitoring questionnaire; not station discharge observations'))
        book.close()
    result = dict(source_folder=str(SOURCE), inspected_local_date='2026-10-30',
                  source_files_modified=False, workbooks=reports, other_documents=documents)
    (OUT / 'desktop_discharge_audit.json').write_text(json.dumps(result, indent=2) + '\n')
    with (OUT / 'desktop_discharge_coverage_by_year.csv').open('w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(years[0]))
        writer.writeheader()
        writer.writerows(years)
    for r in reports:
        print(r['file'], r['first_date'], r['last_date'], 'numeric', r['numeric_days'],
              'missing', r['missing_discharge_rows'], 'missing years', r['missing_years'], 'partial years', r['partial_years'])
        print(json.dumps(r['raw_to_rearranged_checks'], indent=2))


if __name__ == '__main__':
    main()
