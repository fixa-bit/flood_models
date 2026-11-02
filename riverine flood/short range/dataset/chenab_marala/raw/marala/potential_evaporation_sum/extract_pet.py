"""Daily catchment-mean ERA5-Land potential evaporation, 1980–2024."""
import argparse
import csv
from datetime import date, timedelta
import hashlib
import io
import json
import math
from pathlib import Path
import time
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
DEFAULT_CATCHMENT = HERE.parents[2] / 'processed/marala/catchment/marala_upstream_catchment.geojson'
COLLECTION = 'ECMWF/ERA5_LAND/DAILY_AGGR'
BAND = 'potential_evaporation_sum'
START, END = date(1980, 1, 1), date(2025, 1, 1)  # Exclusive end.
ee = None


def daily_table(year, polygon):
    images = ee.ImageCollection(COLLECTION).filterDate(f'{year}-01-01', f'{year + 1}-01-01').select(BAND)

    def daily(item):
        image = ee.Image(item)
        pet = image.multiply(1000)  # Daily accumulated metres -> mm/day.
        pet = pet.multiply(-1).rename('pet_mm')  # ERA5 upward evaporation is negative; reverse its sign.
        # Plain mean with fractional boundary weights, at the requested scale.
        value = pet.reduceRegion(reducer=ee.Reducer.mean(), geometry=polygon,
                                 scale=11132, crs=image.projection(),
                                 maxPixels=10_000_000, tileScale=4).get('pet_mm')
        return ee.Feature(None, {'date': image.date().format('YYYY-MM-dd', 'UTC'), 'pet_mm': value})

    return ee.FeatureCollection(images.toList(images.size()).map(daily))


def write_csv(path, rows):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['date', 'pet_mm'])
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def download_year(year, polygon, output):
    path = output / f'{year}.csv'
    if path.exists():
        return
    for attempt in range(5):
        try:
            table = daily_table(year, polygon)
            url = table.getDownloadURL(filetype='CSV', selectors=['date', 'pet_mm'])
            with urlopen(url, timeout=300) as response:
                rows = list(csv.DictReader(io.StringIO(response.read().decode('utf-8-sig'))))
            stamps = [row['date'] for row in rows]
            if len(stamps) != len(set(stamps)) or any(not stamp.startswith(str(year) + '-') for stamp in stamps):
                raise ValueError('Unexpected or duplicate dates in yearly export')
            if not rows:
                raise ValueError('Empty yearly export')
            write_csv(path, sorted(rows, key=lambda row: row['date']))
            print(f'Saved {year}: {len(rows)} daily PET values', flush=True)
            return
        except Exception as error:
            print(f'PET {year}, attempt {attempt + 1}: {error}', flush=True)
            if attempt == 4:
                raise
            time.sleep(2 ** (attempt + 1))


def merge(output, start=START, end=END):
    records = {}
    for path in sorted(output.glob('[0-9][0-9][0-9][0-9].csv')):
        with path.open(newline='', encoding='utf-8-sig') as stream:
            for row in csv.DictReader(stream):
                stamp = row['date']
                if stamp in records or not str(start) <= stamp < str(end):
                    raise ValueError(f'Unexpected or duplicate date: {stamp}')
                value = float(row['pet_mm']) if row['pet_mm'].strip() else math.nan
                if math.isinf(value):
                    raise ValueError(f'Infinite PET on {stamp}')
                records[stamp] = value if math.isfinite(value) else 'NaN'
    rows, values, missing = [], [], []
    day = start
    while day < end:
        stamp = str(day)
        value = records.get(stamp, 'NaN')
        rows.append({'date': stamp, 'pet_mm': value})
        if value == 'NaN':
            missing.append(stamp)
        else:
            values.append(value)
        day += timedelta(days=1)
    write_csv(output / 'marala_daily_pet_1980_2024.csv', rows)
    report = {'units': 'mm/day', 'missing_days': missing, 'valid_days': len(values),
              'min': min(values) if values else None, 'max': max(values) if values else None,
              'negative_after_sign_reversal': sum(value < 0 for value in values)}
    (output / 'quality_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Missing days ({len(missing)}): {missing}', flush=True)
    print(f"pet_mm: min={report['min']}, max={report['max']}", flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='n8n-gmail-send-503521')
    parser.add_argument('--catchment', type=Path, default=DEFAULT_CATCHMENT)
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--merge-only', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    if args.merge_only:
        merge(args.output)
        return
    global ee
    import ee
    ee.Initialize(project=args.project)
    body = args.catchment.read_bytes()
    document = json.loads(body)
    if document['type'] == 'FeatureCollection':
        polygon = ee.FeatureCollection(document).geometry()
    elif document['type'] == 'Feature':
        polygon = ee.Feature(document).geometry()
    else:
        polygon = ee.Geometry(document)
    settings = {'collection': COLLECTION, 'band': BAND, 'scale_m': 11132,
                'catchment_sha256': hashlib.sha256(body).hexdigest(),
                'period': [str(START), str(END)], 'conversion': 'm * 1000 * -1', 'reducer': 'mean'}
    manifest = args.output / 'run_manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != settings:
        raise ValueError('Settings changed; use a fresh output folder')
    if not manifest.exists() and list(args.output.glob('[0-9][0-9][0-9][0-9].csv')):
        raise ValueError('Yearly exports exist without a run manifest')
    manifest.write_text(json.dumps(settings, indent=2) + '\n', encoding='utf-8')
    print(f'PET catchment: {args.catchment}', flush=True)
    for year in range(1980, 2025):
        download_year(year, polygon, args.output)
    merge(args.output)


if __name__ == '__main__':
    main()
