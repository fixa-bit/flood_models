"""Daily area-weighted Marala 2 m air temperature (degrees C), 1980–2024.

Uses the Earth Engine environment installed in rainfall/google_earth_engine.
Runs independently of precipitation so both jobs can execute concurrently.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import statistics
import sys
import time
from urllib.request import urlopen

WORKSPACE = next(p for p in Path(__file__).resolve().parents if (p / 'data_portal/build_dashboard.py').is_file())
RAINFALL = WORKSPACE / 'riverine flood/short range/dataset/chenab_marala/raw/marala/rainfall/google_earth_engine'
sys.path.insert(0, str(RAINFALL))
import extract_precipitation as shared

ee = None
COLLECTION = 'ECMWF/ERA5_LAND/DAILY_AGGR'
BAND = 'temperature_2m'
VALUE = 'era5land_temperature_2m_c'
FIELDS = ['date', VALUE, 'coverage_fraction', 'n_images']


def daily_table(start, end, geometry, projection, min_coverage):
    images = ee.ImageCollection(COLLECTION).select(BAND).filterDate(str(start), str(end))
    options = dict(geometry=geometry, crs=projection['crs'], crsTransform=projection['transform'],
                   maxPixels=10_000_000, tileScale=4)
    area = ee.Image.pixelArea().rename('area')
    denominator = area.reduceRegion(ee.Reducer.sum(), **options).get('area')
    empty = ee.Image.constant(0).rename(BAND).updateMask(ee.Image.constant(0))

    def feature(stamp):
        day = ee.Date(stamp)
        subset = images.filterDate(day, day.advance(1, 'day'))
        count = subset.size()
        # This source band is already the daily mean of hourly 2 m air
        # temperatures. Kelvin -> Celsius is subtraction, not multiplication.
        image = ee.Image(ee.Algorithms.If(count.eq(1), subset.first(), empty)).subtract(273.15).rename(VALUE)
        covered = area.updateMask(image.mask()).reduceRegion(ee.Reducer.sum(), **options).get('area')
        fraction = ee.Number(ee.Algorithms.If(covered, covered, 0)).divide(denominator)
        # Explicit cell area accounts for varying latitude/longitude pixel area.
        # The weighted mean also applies polygon boundary intersection fractions
        # (~1/256 precision). Native affine grid is retained; masks are not zeros.
        mean = image.addBands(area).reduceRegion(ee.Reducer.mean().splitWeights(), **options).values().get(0)
        valid = ee.Algorithms.If(count.eq(1), fraction.gte(min_coverage), False)
        return ee.Feature(None, {'date': day.format('YYYY-MM-dd', 'UTC'),
                                 VALUE: ee.Algorithms.If(valid, mean, None),
                                 'coverage_fraction': fraction, 'n_images': count})

    return ee.FeatureCollection(ee.List([str(d) for d in shared.days(start, end)]).map(feature))


def export_chunk(start, end, geometry, projection, args):
    folder = args.output / 'chunks/era5land_temperature_2m'
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f'{start}_{end}.csv'
    if path.exists():
        return
    children = [p for p in folder.glob('*.csv') if str(start) <= p.stem.split('_')[0] < str(end)]
    if not children:
        error = None
        for attempt in range(3):
            try:
                table = daily_table(start, end, geometry, projection, args.min_coverage)
                url = table.getDownloadURL(filetype='CSV', selectors=FIELDS)
                with urlopen(url, timeout=300) as response:
                    body = response.read()
                rows = list(csv.DictReader(io.StringIO(body.decode('utf-8-sig'))))
                if sorted(row['date'] for row in rows) != [str(d) for d in shared.days(start, end)]:
                    raise ValueError('Export date mismatch')
                temporary = path.with_suffix('.tmp')
                temporary.write_bytes(body)
                temporary.replace(path)
                print(f'Saved temperature: {start} to {end} (exclusive)', flush=True)
                return
            except Exception as exc:
                error = exc
                print(f'Retrying temperature {start}: {exc}', flush=True)
                if attempt < 2:
                    time.sleep(2 ** (attempt + 1))
        if (end - start).days <= 1:
            raise RuntimeError(f'Temperature export failed: {start}') from error
    midpoint = start + shared.timedelta(days=(end - start).days // 2)
    export_chunk(start, midpoint, geometry, projection, args)
    export_chunk(midpoint, end, geometry, projection, args)


def merge(args):
    records = {}
    for path in sorted((args.output / 'chunks/era5land_temperature_2m').glob('*.csv')):
        with path.open(newline='', encoding='utf-8-sig') as stream:
            for row in csv.DictReader(stream):
                stamp = row['date']
                if stamp in records:
                    raise ValueError(f'Overlapping temperature chunks: {stamp}')
                if not str(shared.START) <= stamp < str(shared.END):
                    raise ValueError(f'Unexpected temperature date: {stamp}')
                records[stamp] = row
    values, output, missing = [], [], []
    for day in shared.days():
        stamp = str(day)
        row = records.get(stamp, {})
        value = shared.number(row.get(VALUE))
        coverage = shared.number(row.get('coverage_fraction'))
        if not math.isfinite(coverage) or coverage < args.min_coverage or shared.number(row.get('n_images')) != 1:
            value = math.nan
        if math.isfinite(value):
            values.append(value)  # Negative degrees C are valid; never clip them.
        else:
            missing.append(stamp)
        output.append({'date': stamp, VALUE: value if math.isfinite(value) else 'NaN'})
    merged = args.output / 'marala_daily_temperature_1980_2024.csv'
    with merged.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=['date', VALUE])
        writer.writeheader()
        writer.writerows(output)
    annual = []
    for year in range(1980, 2025):
        rows = [r for r in output if r['date'].startswith(str(year))]
        valid = [r[VALUE] for r in rows if r[VALUE] != 'NaN']
        annual.append({'year': year, 'valid_days': len(valid), 'calendar_days': len(rows),
                       'annual_mean_c': statistics.mean(valid) if len(valid) == len(rows) else 'NaN'})
    with (args.output / 'annual_temperature_means.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(annual[0]))
        writer.writeheader()
        writer.writerows(annual)
    report = {'qa_passed': not missing, 'units': 'degrees C', 'variable': 'daily catchment-mean 2 m air temperature',
              'day_definition': '00:00–24:00 UTC; 05:00–05:00 next day Pakistan time',
              'valid_days': len(values), 'missing_days': missing, 'negative_celsius_is_valid': True,
              'min_c': min(values) if values else None, 'max_c': max(values) if values else None,
              'mean_c': statistics.mean(values) if values else None,
              'merged_csv_sha256': hashlib.sha256(merged.read_bytes()).hexdigest()}
    shared.save_json(args.output / 'quality_report.json', report)
    print(json.dumps(report, indent=2), flush=True)
    if missing:
        raise ValueError('Temperature has missing days; inspect quality_report.json')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default=os.environ.get('EE_PROJECT'))
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument('--catchment', type=Path, default=shared.DEFAULT_CATCHMENT)
    parser.add_argument('--min-coverage', type=float, default=.999)
    parser.add_argument('--merge-only', action='store_true')
    args = parser.parse_args()
    if not 0 < args.min_coverage <= 1:
        parser.error('--min-coverage must be in (0, 1]')
    args.output.mkdir(parents=True, exist_ok=True)
    if args.merge_only:
        merge(args)
        return
    if not args.project:
        parser.error('--project is required')
    global ee
    import ee
    ee.Initialize(project=args.project)
    shared.ee = ee
    geometry, catchment = shared.existing_catchment(args)
    image = ee.Image(ee.ImageCollection(COLLECTION).filterDate('1980-01-01', '1980-01-02').first()).select(BAND)
    projection = image.projection().getInfo()
    manifest = {'version': 1, 'collection': COLLECTION, 'band': BAND, 'conversion': 'K - 273.15',
                'period': [str(shared.START), str(shared.END)], 'min_coverage': args.min_coverage,
                'catchment_sha256': catchment['source_sha256'], 'projection': projection}
    path = args.output / 'run_manifest.json'
    if path.exists() and json.loads(path.read_text()) != manifest:
        raise ValueError('Temperature settings changed; use a fresh output folder')
    if not path.exists() and list((args.output / 'chunks').glob('*/*.csv')):
        raise ValueError('Temperature chunks exist without a manifest')
    shared.save_json(path, manifest)
    start = shared.START
    while start < shared.END:
        end = min(shared.END, shared.date(start.year + (start.month == 12), start.month % 12 + 1, 1))
        export_chunk(start, end, geometry, projection, args)
        start = end
    merge(args)


if __name__ == '__main__':
    main()
