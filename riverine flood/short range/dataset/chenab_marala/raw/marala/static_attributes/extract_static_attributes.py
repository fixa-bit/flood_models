"""Compute one row of static Marala catchment attributes with Earth Engine."""
import argparse
import csv
import hashlib
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_CATCHMENT = HERE.parents[2] / 'processed/marala/catchment/marala_upstream_catchment.geojson'
LAND_CLASSES = {10: 'tree_cover', 20: 'shrubland', 30: 'grassland', 40: 'cropland',
                50: 'built_up', 60: 'bare_sparse', 70: 'snow_ice', 80: 'permanent_water',
                90: 'herbaceous_wetland', 95: 'mangroves', 100: 'moss_lichen'}
SAND = 'OpenLandMap/SOL/SOL_SAND-WFRACTION_USDA-3A1A1A_M/v02'
CLAY = 'OpenLandMap/SOL/SOL_CLAY-WFRACTION_USDA-3A1A1A_M/v02'
ee = None


def reduce(image, reducer, polygon, scale, crs):
    return image.reduceRegion(reducer=reducer, geometry=polygon, scale=scale,
                              crs=crs, maxPixels=1e13, tileScale=4)


def area_means(image, polygon, scale, crs):
    # Physical pixel-area weights plus Earth Engine's boundary overlap weights.
    weights = ee.Image.pixelArea().updateMask(image.mask().reduce(ee.Reducer.min())).rename('weight_area')
    totals = reduce(image.multiply(weights).addBands(weights), ee.Reducer.sum(), polygon, scale, crs)
    names = image.bandNames()
    return ee.Dictionary.fromLists(names, names.map(
        lambda name: ee.Number(totals.get(ee.String(name))).divide(totals.get('weight_area'))))


def soil_0_30(image):
    # Trapezoidal depth integration over 0–10 and 10–30 cm: weights 1/6, 1/2, 1/3.
    return image.select('b0').add(image.select('b10').multiply(3)).add(image.select('b30').multiply(2)).divide(6)


def elevation_masks(dem):
    return (dem.lt(1500).rename('frac_band1')
            .addBands(dem.gte(1500).And(dem.lt(3000)).rename('frac_band2'))
            .addBands(dem.gte(3000).And(dem.lte(4500)).rename('frac_band3'))
            .addBands(dem.gt(4500).rename('frac_band4')))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', default='n8n-gmail-send-503521')
    parser.add_argument('--catchment', type=Path, default=DEFAULT_CATCHMENT)
    parser.add_argument('--output', type=Path, default=HERE)
    args = parser.parse_args()
    global ee
    import ee
    ee.Initialize(project=args.project)
    args.output.mkdir(parents=True, exist_ok=True)
    body = args.catchment.read_bytes()
    document = json.loads(body)
    if document['type'] == 'FeatureCollection':
        polygon = ee.FeatureCollection(document).geometry()
    elif document['type'] == 'Feature':
        polygon = ee.Feature(document).geometry()
    else:
        polygon = ee.Geometry(document)
    manifest = {'catchment_sha256': hashlib.sha256(body).hexdigest(), 'method_version': 1,
                'dem': 'MERIT/DEM/v1_0_3', 'glaciers': 'GLIMS/current',
                'glacier_selection': 'latest anlys_time per glac_id; dissolved union',
                'landcover': 'ESA/WorldCover/v200 (2021)', 'sand': SAND, 'clay': CLAY,
                'soil_depth_method': '(b0 + 3*b10 + 2*b30)/6; silt=100-sand-clay',
                'climate': 'ECMWF/ERA5_LAND/DAILY_AGGR; 1980-01-01 through 2024-12-31',
                'scales_m': {'dem': 90, 'landcover': 90, 'soil': 250, 'climate': 'native ERA5-Land'}}
    manifest_path = args.output / 'run_manifest.json'
    if manifest_path.exists() and json.loads(manifest_path.read_text()) != manifest:
        raise ValueError('Settings changed; use a fresh output folder')
    manifest_path.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')

    # Cache completed sections so a network interruption can be resumed.
    def section(name, value):
        path = args.output / f'{name}.json'
        if not path.exists():
            result = value.getInfo()
            path.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
        result = json.loads(path.read_text())
        print(f'{name}: {result}', flush=True)
        return result

    row = section('area', ee.Dictionary({'area_km2': polygon.area(1).divide(1e6)}))
    dem = ee.Image('MERIT/DEM/v1_0_3').select('dem').rename('elev')
    grid = dem.projection()
    reducer = ee.Reducer.minMax().combine(ee.Reducer.percentile([10, 50, 90]), sharedInputs=True)
    stats = section('elevation_statistics', reduce(dem, reducer, polygon, 90, grid))
    row.update({f'elev_{name}_m': stats[f'elev_{name}'] for name in ['min', 'max', 'p10', 'p50', 'p90']})
    topo = dem.rename('elev_mean_m').addBands(ee.Terrain.slope(dem).rename('slope_mean_deg'))
    row.update(section('topography_means', area_means(topo, polygon, 90, grid)))
    # Full-catchment denominator; DEM gaps, if any, are not renormalized away.
    row.update(section('elevation_bands', area_means(elevation_masks(dem).unmask(0), polygon, 90, grid)))

    glaciers = ee.FeatureCollection('GLIMS/current').filterBounds(polygon).filter(ee.Filter.eq('line_type', 'glac_bound'))
    newest = glaciers.sort('anlys_time', False).distinct('glac_id').aggregate_array('anlys_id')
    latest = glaciers.filter(ee.Filter.inList('anlys_id', newest))
    glacier_area = ee.Algorithms.If(latest.size().gt(0),
        latest.union(maxError=10).geometry().intersection(polygon, maxError=10).area(10), 0)
    row.update(section('glaciers', ee.Dictionary({'glacier_frac': ee.Number(glacier_area).divide(polygon.area(1))})))

    cover = ee.Image(ee.ImageCollection('ESA/WorldCover/v200').first()).select('Map')
    # Requested 90 m class sampling is coarser than WorldCover's native 10 m.
    indicators = ee.Image.cat([cover.eq(code).rename(f'landcover_{name}') for code, name in LAND_CLASSES.items()])
    row.update(section('landcover', area_means(indicators.unmask(0), polygon, 90, grid)))

    sand = soil_0_30(ee.Image(SAND)).rename('sand_pct')
    clay = soil_0_30(ee.Image(CLAY)).rename('clay_pct')
    silt = ee.Image.constant(100).subtract(sand).subtract(clay).rename('silt_pct')
    soil = sand.addBands(silt).addBands(clay)
    # Exclude inconsistent predictions from all three means, rather than clip silt.
    soil = soil.updateMask(silt.gte(0))
    row.update(section('soil', area_means(soil, polygon, 250, ee.Image(SAND).select('b0').projection())))

    climate = ee.ImageCollection('ECMWF/ERA5_LAND/DAILY_AGGR').filterDate('1980-01-01', '2025-01-01')
    if climate.size().getInfo() != 16437:
        raise ValueError('ERA5-Land climate period does not contain all 16,437 daily images')
    # Daily m -> mm, summed over 45 years, then /45 gives mean annual amounts.
    precip = climate.select('total_precipitation_sum').sum().multiply(1000 / 45).rename('precip_mean_mm')
    pet = climate.select('potential_evaporation_sum').sum().multiply(-1000 / 45).rename('pet_mean_mm')
    native = ee.Image(climate.first()).select('total_precipitation_sum').projection()
    amounts = section('climate', area_means(precip.addBands(pet), polygon, native.nominalScale(), native))
    row['precip_mean_mm'] = amounts['precip_mean_mm']
    row['aridity'] = amounts['pet_mean_mm'] / amounts['precip_mean_mm']

    if any(value is None or not math.isfinite(value) for value in row.values()):
        raise ValueError('Missing/nonfinite static attributes; inspect section files')
    for name, value in row.items():
        if (name.startswith(('landcover_', 'frac_band')) or name == 'glacier_frac') and not 0 <= value <= 1.000001:
            raise ValueError(f'Invalid fraction: {name}={value}')
    columns = ['area_km2', 'elev_mean_m', 'elev_min_m', 'elev_max_m', 'elev_p10_m', 'elev_p50_m', 'elev_p90_m',
               'slope_mean_deg', 'glacier_frac', *[f'landcover_{name}' for name in LAND_CLASSES.values()],
               'sand_pct', 'silt_pct', 'clay_pct', 'precip_mean_mm', 'aridity', 'frac_band1', 'frac_band2', 'frac_band3', 'frac_band4']
    path = args.output / 'marala_static_attributes.csv'
    with path.open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        writer.writerow(row)
    checks = {'landcover_fraction_sum': sum(row[k] for k in row if k.startswith('landcover_')),
              'elevation_band_fraction_sum': sum(row[f'frac_band{i}'] for i in range(1, 5)),
              'soil_percent_sum': sum(row[k] for k in ['sand_pct', 'silt_pct', 'clay_pct']),
              'csv_sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
    (args.output / 'quality_report.json').write_text(json.dumps(checks, indent=2) + '\n', encoding='utf-8')
    print(f'Saved one-row CSV: {path}', flush=True)
    print(json.dumps(checks, indent=2), flush=True)


if __name__ == '__main__':
    main()
