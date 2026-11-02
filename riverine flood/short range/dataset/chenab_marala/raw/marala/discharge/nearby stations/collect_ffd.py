"""Collect observed Chenab discharge from official FFD bulletins; no gap filling.

Run with Python containing beautifulsoup4 and pymupdf. Known bulletin URLs come
from existing Marala source catalogs. Exact documents are saved once under _sources.
"""
import csv
import hashlib
import json
import re
import time
import urllib.request
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pymupdf
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent
MODEL = ROOT.parents[3]
CATALOG = MODEL / 'processed/marala/discharge'
STATIONS = ('Khanki', 'Qadirabad', 'Trimmu')
FACTOR = Decimal('28.316846592')  # 1,000 cusecs to m3/s


def write_csv(path, rows):
    if not rows:
        return
    with path.open('w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fetch(item):
    year, r = item
    destination = ROOT / '_sources' / str(year) / r['raw_file']
    destination.parent.mkdir(parents=True, exist_ok=True)
    receipt = dict(year=year, url=r['source_url'], local_file=str(destination.relative_to(ROOT)),
                   retrieved_utc='', retrieval_mode='', network_error='')
    if destination.exists():
        body = destination.read_bytes()
        receipt['retrieval_mode'] = 'reused_download_in_this_folder'
        old = destination.with_suffix(destination.suffix + '.receipt.json')
        if old.exists():
            receipt = json.loads(old.read_text())
    else:
        body = None
        for attempt in range(2):
            try:
                request = urllib.request.Request(r['source_url'], headers={'User-Agent': 'Mozilla/5.0 (Chenab observed discharge collection)'})
                with urllib.request.urlopen(request, timeout=25) as response:
                    data = response.read()
                    if year < 2026 and not data.startswith(b'%PDF-'):
                        raise ValueError('Expected an official PDF response')
                    if year == 2026 and b'meta-dated' not in data:
                        raise ValueError('Expected an official HTML bulletin')
                    receipt['final_url'] = response.url
                    body = data
                receipt['retrieved_utc'] = datetime.now(timezone.utc).isoformat()
                receipt['retrieval_mode'] = 'downloaded_from_official_ffd'
                break
            except Exception as exc:
                receipt['network_error'] = str(exc)
                if attempt == 0:
                    time.sleep(0.5)
        if body is None:
            cached = MODEL / 'raw/marala/discharge/ffd' / f'bulletins_{year}' / r['raw_file']
            body = cached.read_bytes()
            receipt['retrieval_mode'] = 'existing_official_snapshot_network_failed'
            receipt['existing_snapshot_path'] = str(cached.relative_to(MODEL))
        destination.write_bytes(body)
    receipt['sha256'] = hashlib.sha256(body).hexdigest()
    receipt['bytes'] = len(body)
    receipt['matches_existing_marala_snapshot'] = receipt['sha256'] == r['source_sha256']
    destination.with_suffix(destination.suffix + '.receipt.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return year, r, body, receipt


def parse(year, catalog_row, body, receipt):
    if year < 2026:
        with pymupdf.open(stream=body, filetype='pdf') as doc:
            text = '\n'.join(page.get_text() for page in doc)
            header = doc[0].get_text()[:2500]
        dated = re.search(r'Dated:\s*[-–]?\s*(\d{1,2})(?:st|nd|rd|th)?\s*([A-Za-z]+)[,\s-]+(20\d\d)', header, re.I)
        page = None
    else:
        page = BeautifulSoup(body, 'html.parser')
        node = page.select_one('.meta-dated')
        dated = re.search(r'(\d{1,2})(?:st|nd|rd|th)?\s+([A-Za-z]+)-(20\d\d)', node.get_text(' ', strip=True) if node else '')
        text = page.get_text(' ', strip=True)
    if not dated:
        raise ValueError('Printed date could not be parsed')
    printed = datetime.strptime(' '.join(dated.groups()), '%d %B %Y').date().isoformat()
    listed = catalog_row.get('archive_listed_date', catalog_row['date'])
    time_confirmed = bool(re.search(r'Actual\s+Observations\s+at\s+0600\s+PST', text, re.I))
    if not re.search(r'thousands?\s+(?:of\s+)?cusecs|1000\s*[- ]?\s*cusecs|1000.*cusecs', text, re.I):
        raise ValueError('Cannot confirm thousands-of-cusecs units')
    rows = []
    for station in STATIONS:
        if page is None:
            label = r'Qadirabad?' if station == 'Qadirabad' else station
            match = re.search(r'\b' + label + r'\s*\n\s*\d{3,4}\s*\n\s*([\d,.]+)\s*\n\s*([\d,.]+)', text, re.I)
            if not match:
                raise ValueError(f'Could not parse {station} PDF observation row')
            inflow, outflow = match.groups()
        else:
            cell = next((c for c in page.find_all(['td', 'th']) if c.get_text(' ', strip=True).casefold() == station.casefold()), None)
            if cell is None:
                raise ValueError(f'Missing {station} HTML observation row')
            row = cell.find_parent('tr')
            a, b = row.find('td', attrs={'data-ffd': 'inflow'}), row.find('td', attrs={'data-ffd': 'outflow'})
            if a is None or b is None:
                table = cell.find_parent('table')
                headers = ' '.join(tr.get_text(' ', strip=True) for tr in table.find_all('tr')[:2])
                if not re.search(r'Actual\s+Observations\s+at\s+0600\s+PST', headers, re.I):
                    raise ValueError('Unrecognized HTML observation table')
                cells = row.find_all(['td', 'th'], recursive=False)
                offset = next(i for i, c in enumerate(cells) if c is cell) + (2 if 'Design Capacity' in headers else 1)
                a, b = cells[offset:offset + 2]
            inflow, outflow = a.get_text(' ', strip=True), b.get_text(' ', strip=True)
        inflow, outflow = Decimal(inflow.replace(',', '')), Decimal(outflow.replace(',', ''))
        if not inflow.is_finite() or not outflow.is_finite() or inflow < 0 or outflow < 0:
            raise ValueError(f'Invalid discharge for {station}')
        flags = []
        if printed != listed:
            flags.append('printed_date_differs_from_archive')
        if not time_confirmed:
            flags.append('observation_time_unconfirmed')
        if inflow == 0:
            flags.append('zero_inflow_needs_review')
        rows.append(dict(date=printed, station=station, river='Chenab',
                         inflow_cumecs=str(inflow * FACTOR), outflow_cumecs=str(outflow * FACTOR),
                         inflow_1000_cusecs=str(inflow), outflow_1000_cusecs=str(outflow),
                         observation_time_pkt='06:00' if time_confirmed else '',
                         measurement_basis='instantaneous_reading_not_daily_mean',
                         archive_listed_date=listed, quality_flag=';'.join(flags),
                         eligible_daily=int(not flags), provider='PMD Flood Forecasting Division',
                         source_url=receipt['url'], source_file=receipt['local_file'],
                         source_sha256=receipt['sha256'], retrieval_mode=receipt['retrieval_mode']))
    return rows


def main():
    items = []
    for year in (2024, 2025, 2026):
        with (CATALOG / f'marala_ffd_{year}_bulletin_discharge.csv').open(newline='', encoding='utf-8') as f:
            items.extend((year, row) for row in csv.DictReader(f))
    records, receipts, failures = [], [], []
    with ThreadPoolExecutor(max_workers=4) as pool:
        futures = {pool.submit(fetch, item): item for item in items}
        for n, future in enumerate(as_completed(futures), 1):
            item = futures[future]
            try:
                year, row, body, receipt = future.result()
                receipts.append(receipt)
                records.extend(parse(year, row, body, receipt))
            except Exception as exc:
                failures.append(dict(url=item[1]['source_url'], error=str(exc)))
            if n % 25 == 0 or n == len(items):
                print(f'Processed {n}/{len(items)} bulletins; failures={len(failures)}', flush=True)
    summary = []
    for station in STATIONS:
        folder = ROOT / station
        folder.mkdir(exist_ok=True)
        rows = sorted((r for r in records if r['station'] == station), key=lambda r: (r['date'], r['source_url']))
        write_csv(folder / 'observations_with_provenance.csv', rows)
        grouped = defaultdict(list)
        for row in rows:
            if row['eligible_daily']:
                grouped[row['date']].append(row)
        daily, provenance = [], []
        current, last = date.fromisoformat(min(r['date'] for r in rows)), date.fromisoformat(max(r['date'] for r in rows))
        while current <= last:
            candidates = grouped.get(current.isoformat(), [])
            unambiguous = len({r['inflow_cumecs'] for r in candidates}) == 1
            selected = candidates[0] if unambiguous else None
            daily.append(dict(date=current.isoformat(), q_cumecs=selected['inflow_cumecs'] if selected else 'NaN'))
            if selected:
                provenance.append(selected)
            current += timedelta(days=1)
        write_csv(folder / 'nearby.csv', daily)
        write_csv(folder / 'selected_daily_provenance.csv', provenance)
        report = dict(station=station, river='Chenab', variable='inflow', units='m3/s',
                      first_date=daily[0]['date'], last_date=daily[-1]['date'],
                      extracted_bulletin_rows=len(rows), eligible_unique_observed_days=len(provenance),
                      calendar_days=len(daily), missing_days=len(daily) - len(provenance),
                      by_year={str(year): sum(r['date'].startswith(str(year)) for r in provenance) for year in (2024, 2025, 2026)},
                      excluded_flag_counts=dict(Counter(r['quality_flag'] for r in rows if not r['eligible_daily'])),
                      policy='06:00 PKT observed inflow only; exclude archive/printed date conflicts, uncertain times, zero inflow, or conflicting same-day inflows. No interpolation, regression, GloFAS or analysis performed.')
        (folder / 'collection_report.json').write_text(json.dumps(report, indent=2) + '\n')
        (folder / 'README.md').write_text(f"# {station}: observed Chenab discharge\n\n`nearby.csv` contains date,q_cumecs with observed inflow in m3/s at 06:00 PKT. Missing days remain NaN. It covers flood seasons, not complete years.\n\n`observations_with_provenance.csv` preserves all extracted inflows/outflows and quality flags; `selected_daily_provenance.csv` identifies each accepted daily value. Inflows and outflows are never substituted for one another. Exact source documents and receipts are in `../_sources/`.\n\n{len(provenance)} eligible observed days; {len(daily) - len(provenance)} missing dates within {daily[0]['date']} to {daily[-1]['date']}. No regression analysis has been run.\n")
        summary.append(report)
    report = dict(checked_utc=datetime.now(timezone.utc).isoformat(), requested_bulletins=len(items),
                  saved_sources=len(receipts), retrieval_modes=dict(Counter(r['retrieval_mode'] for r in receipts)),
                  failures=failures, stations=summary)
    (ROOT / 'collection_report.json').write_text(json.dumps(report, indent=2) + '\n')
    write_csv(ROOT / 'source_manifest.csv', [{k: r.get(k, '') for k in ('year', 'url', 'local_file', 'retrieval_mode', 'retrieved_utc', 'sha256', 'bytes', 'matches_existing_marala_snapshot', 'network_error')} for r in receipts])
    print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
