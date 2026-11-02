"""Daily MOD10A1 Marala snow-cover index and valid fraction, 2000–2024.

snow_cover_pct is the requested column name; MODIS V6.1 NDSI_Snow_Cover is
an index scaled 0–100, not fractional snow-covered area percent.
"""
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
COLLECTION, BAND = 'MODIS/061/MOD10A1', 'NDSI_Snow_Cover'
START, END = date(2000, 3, 1), date(2025, 1, 1)  # Exclusive end.
COLUMNS = ['date', 'snow_cover_pct', 'valid_frac']
ee = None


def dates(start, end):
    while start < end:
        yield str(start)
        start += timedelta(days=1)


def daily_table(start, end, polygon, projection):
    images = ee.ImageCollection(COLLECTION).filterBounds(polygon).filterDate(str(start), str(end)).select(BAND)
    empty = ee.Image.constant(0).rename(BAND).updateMask(ee.Image.constant(0))

    def daily(stamp):
        day = ee.Date(stamp)
        subset = images.filterDate(day, day.advance(1, 'day'))
        image = ee.Image(ee.Algorithms.If(subset.size().gt(0), subset.mosaic(), empty))
        # Keep 0–100 only; Earth Engine also masks provider flags in this band.
        valid = image.gte(0).And(image.lte(100)).unmask(0, sameFootprint=False).rename('valid_frac')
        snow = image.updateMask(valid).rename('snow_cover_pct')
        # Invalid pixels are zero in valid_frac, not masked out of its denominator.
        # Both means use the same native MODIS CRS at 500 m and boundary weights.
        means = snow.addBands(valid).reduceRegion(
            reducer=ee.Reducer.mean(), geometry=polygon, crs=projection,
            scale=500, maxPixels=1e13, tileScale=4)
        return ee.Feature(None, means).set('date', day.format('YYYY-MM-dd', 'UTC'))

    return ee.FeatureCollection(ee.List(list(dates(start, end))).map(daily))


def download(start, end, polygon, projection):
    for attempt in range(3):
        try:
            url = daily_table(start, end, polygon, projection).getDownloadURL(filetype='CSV', selectors=COLUMNS)
            with urlopen(url, timeout=300) as response:
                rows = list(csv.DictReader(io.StringIO(response.read().decode('utf-8-sig'))))
            if sorted(row['date'] for row in rows) != list(dates(start, end)):
                raise ValueError('Download calendar mismatch')
            return sorted(rows, key=lambda row: row['date'])
        except Exception as error:
            print(f'MODIS {start} to {end}: {error}', flush=True)
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
    if (end - start).days <= 1:
        raise RuntimeError(f'MODIS download failed for {start}')
    # Split heavy requests while preserving yearly output files.
    midpoint = start + timedelta(days=(end - start).days // 2)
    return download(start, midpoint, polygon, projection) + download(midpoint, end, polygon, projection)


def write_csv(path, rows):
    temporary = path.with_suffix('.tmp')
    with temporary.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def download_year(year, polygon, projection, output, chunk_days=7):
    """Cache small requests, then assemble the requested yearly daily CSV."""
    path = output / f'{year}.csv'
    if path.exists():
        return
    folder = output / 'chunks'
    folder.mkdir(exist_ok=True)
    start, end = max(START, date(year, 1, 1)), date(year + 1, 1, 1)
    rows = []
    while start < end:
        stop = min(end, start + timedelta(days=chunk_days))
        part = folder / f'{start}_{stop}.csv'
        if not part.exists():
            write_csv(part, download(start, stop, polygon, projection))
            print(f'Saved MODIS chunk: {start} to {stop} (exclusive)', flush=True)
        with part.open(newline='', encoding='utf-8-sig') as stream:
            saved = list(csv.DictReader(stream))
        if [row['date'] for row in saved] != list(dates(start, stop)):
            raise ValueError(f'Cached MODIS chunk has incorrect dates: {part}')
        rows.extend(saved)
        start = stop
    write_csv(path, rows)
    print(f'Saved MODIS {year}: {len(rows)} daily rows', flush=True)


def merge(output, start=START, end=END):
    calendar = {stamp: {'date': stamp} for stamp in dates(start, end)}
    seen = set()
    for path in sorted(output.glob('[0-9][0-9][0-9][0-9].csv')):
        with path.open(newline='', encoding='utf-8-sig') as stream:
            for row in csv.DictReader(stream):
                stamp = row['date']
                if stamp in seen or stamp not in calendar:
                    raise ValueError(f'Unexpected/duplicate date in {path}: {stamp}')
                seen.add(stamp)
                for column, upper in [('snow_cover_pct', 100), ('valid_frac', 1)]:
                    value = float(row[column]) if row[column].strip() else math.nan
                    if math.isinf(value) or (math.isfinite(value) and not 0 <= value <= upper):
                        raise ValueError(f'Out-of-range {column} on {stamp}: {value}')
                    calendar[stamp][column] = value if math.isfinite(value) else 'NaN'
    report = {'snow_cover_pct_definition': 'Mean valid NDSI_Snow_Cover (0–100 index); not snow-covered area percent',
              'days_absent_from_exports': sorted(set(calendar) - seen)}
    for column in COLUMNS[1:]:
        missing, values = [], []
        for stamp, row in calendar.items():
            value = row.setdefault(column, 'NaN')
            if value == 'NaN':
                missing.append(stamp)
            else:
                values.append(value)
        report[column] = {'missing_days': missing, 'valid_days': len(values),
                          'min': min(values) if values else None, 'max': max(values) if values else None}
        print(f'{column}: missing days ({len(missing)}): {missing}', flush=True)
        print(f"{column}: min={report[column]['min']}, max={report[column]['max']}", flush=True)
    path = output / 'marala_daily_modis_snow_cover_2000_2024.csv'
    write_csv(path, calendar.values())
    report['merged_csv_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
    (output / 'quality_report.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Merged CSV: {path}', flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='n8n-gmail-send-503521')
    parser.add_argument('--catchment', type=Path, default=DEFAULT_CATCHMENT)
    parser.add_argument('--output', type=Path, default=HERE)
    parser.add_argument('--merge-only', action='store_true')
    parser.add_argument('--chunk-days', type=int, default=7, help='Days per request, combined into yearly exports (default 7)')
    args = parser.parse_args()
    if not 1 <= args.chunk_days <= 31:
        parser.error('--chunk-days must be between 1 and 31')
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
    reference = ee.Image(ee.ImageCollection(COLLECTION).filterBounds(polygon).filterDate('2000-03-01', '2000-03-08').first()).select(BAND)
    projection = reference.projection()
    settings = {'collection': COLLECTION, 'band': BAND, 'scale_m': 500, 'maxPixels': 1e13, 'tileScale': 4,
                'catchment_sha256': hashlib.sha256(body).hexdigest(), 'period': [str(START), str(END)],
                'projection': projection.getInfo(), 'valid_values': '0 through 100, inclusive',
                'valid_fraction': 'mean of unmasked 0/1 validity over whole catchment'}
    manifest = args.output / 'run_manifest.json'
    if manifest.exists() and json.loads(manifest.read_text()) != settings:
        raise ValueError('Settings changed; use a fresh --output directory')
    if not manifest.exists() and list(args.output.glob('[0-9][0-9][0-9][0-9].csv')):
        raise ValueError('Yearly files exist without a run manifest')
    manifest.write_text(json.dumps(settings, indent=2) + '\n', encoding='utf-8')
    print(f'MODIS catchment: {args.catchment}', flush=True)
    for year in range(2000, 2025):
        download_year(year, polygon, projection, args.output, args.chunk_days)
    merge(args.output)


if __name__ == '__main__':
    main()
