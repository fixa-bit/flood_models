"""Download daily Marala ERA5-Land SWE, snow depth and snowmelt, 1980–2024."""
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
DEFAULT_CATCHMENT = HERE.parent.parent / 'processed/marala/catchment/marala_upstream_catchment.geojson'
COLLECTION = 'ECMWF/ERA5_LAND/DAILY_AGGR'
FEATURES = {
    'swe_mm': ('snow_depth_water_equivalent', 'mm'),
    'snow_depth_m': ('snow_depth', 'm'),
    'snowmelt_mm': ('snowmelt_sum', 'mm/day'),
}
START, END = date(1980, 1, 1), date(2025, 1, 1)  # Exclusive end.
ee = None


def daily_table(start, end, polygon):
    images = ee.ImageCollection(COLLECTION).filterDate(str(start), str(end)).select(
        [band for band, _ in FEATURES.values()])

    def daily(item):
        image = ee.Image(item)
        swe = image.select('snow_depth_water_equivalent').multiply(1000).rename('swe_mm')  # m water -> mm.
        depth = image.select('snow_depth').rename('snow_depth_m')  # Snow thickness stays in m.
        melt = image.select('snowmelt_sum').multiply(1000).rename('snowmelt_mm')  # Daily m water -> mm/day.
        # Include all valid catchment cells, including zero-snow cells. The plain
        # mean uses fractional boundary weights and excludes masked cells.
        means = swe.addBands(depth).addBands(melt).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=polygon, scale=11132,
            crs=image.select('snow_depth_water_equivalent').projection(),
            maxPixels=10_000_000, tileScale=4)
        return ee.Feature(None, means).set('date', image.date().format('YYYY-MM-dd', 'UTC'))

    return ee.FeatureCollection(images.toList(images.size()).map(daily))


def download(start, end, polygon):
    for attempt in range(3):
        try:
            table = daily_table(start, end, polygon)
            url = table.getDownloadURL(filetype='CSV', selectors=['date', *FEATURES])
            with urlopen(url, timeout=300) as response:
                rows = list(csv.DictReader(io.StringIO(response.read().decode('utf-8-sig'))))
            stamps = [row['date'] for row in rows]
            if not rows or len(stamps) != len(set(stamps)) or any(not str(start) <= stamp < str(end) for stamp in stamps):
                raise ValueError('Unexpected, duplicate or empty export dates')
            return sorted(rows, key=lambda row: row['date'])
        except Exception as error:
            print(f'Snow request {start} to {end}: {error}', flush=True)
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
    # Smaller requests can avoid online limits; annual output files stay annual.
    if (end - start).days <= 1:
        raise RuntimeError(f'Could not download snow data for {start}')
    midpoint = start + timedelta(days=(end - start).days // 2)
    return download(start, midpoint, polygon) + download(midpoint, end, polygon)


def write_csv(path, columns, rows):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def merge(output, start=START, end=END):
    calendar = {}
    day = start
    while day < end:
        calendar[str(day)] = {'date': str(day)}
        day += timedelta(days=1)
    report = {}
    for column, (folder, units) in FEATURES.items():
        seen = set()
        for path in sorted((output / folder).glob('[0-9][0-9][0-9][0-9].csv')):
            with path.open(newline='', encoding='utf-8-sig') as stream:
                for row in csv.DictReader(stream):
                    stamp = row['date']
                    if stamp not in calendar or stamp in seen:
                        raise ValueError(f'Unexpected/duplicate date in {path}: {stamp}')
                    seen.add(stamp)
                    value = float(row[column]) if row[column].strip() else math.nan
                    if math.isinf(value):
                        raise ValueError(f'Infinite {column} on {stamp}')
                    calendar[stamp][column] = value if math.isfinite(value) else 'NaN'
        missing, values = [], []
        for stamp, row in calendar.items():
            value = row.setdefault(column, 'NaN')
            if value == 'NaN':
                missing.append(stamp)
            else:
                values.append(value)
        report[column] = {'units': units, 'missing_days': missing, 'valid_days': len(values),
                          'min': min(values) if values else None, 'max': max(values) if values else None}
        print(f'{column}: missing days ({len(missing)}): {missing}', flush=True)
        print(f"{column}: min={report[column]['min']}, max={report[column]['max']}", flush=True)
    path = output / 'marala_daily_snow_1980_2024.csv'
    write_csv(path, ['date', *FEATURES], calendar.values())
    report['merged_csv_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / 'snow_quality_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Merged CSV: {path}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='n8n-gmail-send-503521')
    parser.add_argument('--catchment', type=Path, default=DEFAULT_CATCHMENT)
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--merge-only', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for folder, _ in FEATURES.values():
        (args.output / folder).mkdir(exist_ok=True)
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
    settings = {'collection': COLLECTION, 'features': FEATURES, 'scale_m': 11132,
                'reducer': 'ee.Reducer.mean()', 'period': [str(START), str(END)],
                'catchment_sha256': hashlib.sha256(body).hexdigest(),
                'conversions': {'swe_mm': 'm * 1000', 'snow_depth_m': 'm unchanged', 'snowmelt_mm': 'm/day * 1000'}}
    manifest = args.output / 'snow_manifest.json'
    # JSON normalizes tuples to lists so the resume comparison is stable.
    settings = json.loads(json.dumps(settings))
    if manifest.exists() and json.loads(manifest.read_text()) != settings:
        raise ValueError('Settings changed; use a fresh --output folder')
    if not manifest.exists() and any(list((args.output / folder).glob('*.csv')) for folder, _ in FEATURES.values()):
        raise ValueError('Yearly files exist without a snow manifest')
    manifest.write_text(json.dumps(settings, indent=2) + '\n', encoding='utf-8')
    print(f'Snow catchment: {args.catchment}', flush=True)
    for year in range(1980, 2025):
        paths = {column: args.output / folder / f'{year}.csv' for column, (folder, _) in FEATURES.items()}
        if all(path.exists() for path in paths.values()):
            continue
        rows = download(date(year, 1, 1), date(year + 1, 1, 1), polygon)
        for column, path in paths.items():
            write_csv(path, ['date', column], rows)
        print(f'Saved snow {year}: {len(rows)} daily rows in each feature folder', flush=True)
    merge(args.output)


if __name__ == '__main__':
    main()
