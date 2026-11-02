"""Download daily Marala dewpoint and solar radiation, 1980–2024.

Yearly files go into dewpoint_temperature/ and
surface_solar_radiation_downwards_sum/ beside this script.
Requires earthengine-api; see dewpoint_ssrd_README.md for the run command.
"""
import argparse
import csv
from datetime import date, timedelta
import hashlib
import io
import json
import math
import os
from pathlib import Path
import time
from urllib.request import urlopen

START, END = date(1980, 1, 1), date(2025, 1, 1)  # Exclusive end.
COLLECTION = 'ECMWF/ERA5_LAND/DAILY_AGGR'
BANDS = ['dewpoint_temperature_2m', 'surface_solar_radiation_downwards_sum']
FOLDERS = {'dewpoint_c': 'dewpoint_temperature', 'ssrd_wm2': 'surface_solar_radiation_downwards_sum'}
HERE = Path(__file__).resolve().parent
# raw/marala -> model root is two parents above.
DEFAULT_CATCHMENT = HERE.parent.parent / 'processed/marala/catchment/marala_upstream_catchment.geojson'
ee = None


def dates(start, end):
    while start < end:
        yield str(start)
        start += timedelta(days=1)


def yearly_table(start, end, polygon):
    images = ee.ImageCollection(COLLECTION).filterDate(str(start), str(end)).select(BANDS)
    empty = ee.Image.constant([0, 0]).rename(BANDS).updateMask(ee.Image.constant(0))
    projection = ee.Image(images.first()).select(BANDS[0]).projection()

    def daily(stamp):
        day = ee.Date(stamp)
        subset = images.filterDate(day, day.advance(1, 'day'))
        image = ee.Image(ee.Algorithms.If(subset.size().eq(1), subset.first(), empty))
        dewpoint = image.select(BANDS[0]).subtract(273.15).rename('dewpoint_c')  # K -> degrees C.
        radiation = image.select(BANDS[1]).divide(86400).rename('ssrd_wm2')  # Daily J/m2 -> mean W/m2.
        # Weighted mean applies fractional boundary-pixel coverage and excludes
        # masked pixels. This uses the requested mean at 11132 m, without an
        # extra pixelArea weight; geographic cells are not exactly equal-area.
        means = dewpoint.addBands(radiation).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=polygon, scale=11132,
            crs=projection, maxPixels=10_000_000, tileScale=4)
        return ee.Feature(None, means).set('date', day.format('YYYY-MM-dd', 'UTC'))

    return ee.FeatureCollection(ee.List(list(dates(start, end))).map(daily))


def download(start, end, polygon):
    """Try a year; split requests if Earth Engine's online limits are reached."""
    for attempt in range(2):
        try:
            table = yearly_table(start, end, polygon)
            url = table.getDownloadURL(filetype='CSV', selectors=['date', *FOLDERS])
            with urlopen(url, timeout=300) as response:
                rows = list(csv.DictReader(io.StringIO(response.read().decode('utf-8-sig'))))
            if sorted(row['date'] for row in rows) != list(dates(start, end)):
                raise ValueError('Export dates differ from requested dates')
            return sorted(rows, key=lambda row: row['date'])
        except Exception as error:
            print(f'Request {start} to {end} failed: {error}', flush=True)
            if attempt == 0:
                time.sleep(2)
    if (end - start).days <= 1:
        raise RuntimeError(f'Could not download {start}')
    midpoint = start + timedelta(days=(end - start).days // 2)
    print(f'Splitting request {start} to {end}', flush=True)
    return download(start, midpoint, polygon) + download(midpoint, end, polygon)


def write_csv(path, columns, rows):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def merge(output, start=START, end=END):
    calendar = {stamp: {'date': stamp} for stamp in dates(start, end)}
    report = {}
    for column, folder in FOLDERS.items():
        seen = set()
        for path in sorted((output / folder).glob('[0-9][0-9][0-9][0-9].csv')):
            with path.open(newline='', encoding='utf-8-sig') as stream:
                for row in csv.DictReader(stream):
                    stamp = row['date']
                    if stamp not in calendar or stamp in seen:
                        raise ValueError(f'Unexpected/duplicate date in {path}: {stamp}')
                    seen.add(stamp)
                    text = row[column].strip()
                    value = float(text) if text and text.lower() != 'nan' else math.nan
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
        report[column] = {'units': 'degrees C' if column == 'dewpoint_c' else 'W/m2',
                          'missing_days': missing, 'valid_days': len(values),
                          'min': min(values) if values else None, 'max': max(values) if values else None}
        print(f"{column}: missing days ({len(missing)}): {missing}", flush=True)
        print(f"{column}: min={report[column]['min']}, max={report[column]['max']}", flush=True)
    path = output / 'marala_daily_dewpoint_ssrd_1980_2024.csv'
    write_csv(path, ['date', *FOLDERS], calendar.values())
    report['merged_csv_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / 'dewpoint_ssrd_quality_report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'Merged CSV: {path}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default=os.environ.get('EE_PROJECT', 'n8n-gmail-send-503521'))
    parser.add_argument('--catchment', type=Path, default=DEFAULT_CATCHMENT,
                        help='Path to marala_catchment.geojson or another existing catchment GeoJSON')
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--merge-only', action='store_true')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for folder in FOLDERS.values():
        (args.output / folder).mkdir(exist_ok=True)
    if args.merge_only:
        merge(args.output)
        return
    global ee
    import ee
    ee.Initialize(project=args.project)
    body = args.catchment.read_bytes()
    geojson = json.loads(body)
    if geojson['type'] == 'FeatureCollection':
        polygon = ee.FeatureCollection(geojson).geometry()
    elif geojson['type'] == 'Feature':
        polygon = ee.Feature(geojson).geometry()
    else:
        polygon = ee.Geometry(geojson)
    print(f'Catchment: {args.catchment}', flush=True)
    settings = {'collection': COLLECTION, 'bands': BANDS, 'scale_m': 11132,
                'reducer': 'ee.Reducer.mean()', 'start': str(START), 'end_exclusive': str(END),
                'catchment_sha256': hashlib.sha256(body).hexdigest(),
                'conversions': {'dewpoint_c': 'K - 273.15', 'ssrd_wm2': '(J/m2)/86400'},
                'day_definition': '00:00–24:00 UTC; 05:00–05:00 next day Pakistan time'}
    manifest = args.output / 'dewpoint_ssrd_manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != settings:
        raise ValueError('Extraction settings changed; use a fresh --output directory')
    if not manifest.exists() and any(list((args.output / folder).glob('*.csv')) for folder in FOLDERS.values()):
        raise ValueError('Yearly files exist without a manifest')
    manifest.write_text(json.dumps(settings, indent=2) + '\n', encoding='utf-8')
    for year in range(1980, 2025):
        paths = {column: args.output / folder / f'{year}.csv' for column, folder in FOLDERS.items()}
        if all(path.exists() for path in paths.values()):
            continue
        rows = download(date(year, 1, 1), date(year + 1, 1, 1), polygon)
        for column, path in paths.items():
            write_csv(path, ['date', column], rows)
        print(f'Saved {year}: {len(rows)} daily rows in each variable folder', flush=True)
    merge(args.output)


if __name__ == '__main__':
    main()
