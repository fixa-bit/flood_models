"""Define the Pakistan 20 km grid and extract static cell features.

Boundaries come from Earth Engine (LSIB Pakistan, GAUL 2025 districts) and are saved as GeoJSON.
Cell fractions inside them are computed exactly from the polygons with shapely in EPSG:6933.
Terrain, land cover and population are aggregated to the cells by Earth Engine.

Writes raw/gee/grid/{grid_definition.json, cells.csv, pakistan_lsib.geojson, chenab_districts.geojson}
and raw/gee/static/{static_features.npz, source_receipt.json}.
Run from this folder: ../../../.venv/Scripts/python.exe build_grid_static.py
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone

import ee
import numpy as np
import pyproj
from shapely import STRtree, box
from shapely.geometry import shape
from shapely.ops import transform

from gee_common import CELL_M, CHENAB_DISTRICTS, CRS, GEE_DIR, GRID_JSON, chenab_districts, compute, compute_tiled, initialize, pakistan, projection, save_npz, sha256_file

PROVINCE_CODES = {1: "Balochistan", 2: "Islamabad", 3: "Khyber Pakhtunkhwa", 4: "Punjab", 5: "Sindh"}
TO_GRID = pyproj.Transformer.from_crs(4326, 6933, always_xy=True)
TO_LONLAT = pyproj.Transformer.from_crs(6933, 4326, always_xy=True)


def save_geojson(collection, path, properties):
    data = collection.map(lambda f: f.select(properties)).getInfo()
    path.write_text(json.dumps(data), encoding="utf-8")
    return [shape(feature["geometry"]) for feature in data["features"]], data


def main():
    initialize()
    grid_dir = GEE_DIR / "grid"
    grid_dir.mkdir(parents=True, exist_ok=True)
    pak_shapes, _ = save_geojson(pakistan(), grid_dir / "pakistan_lsib.geojson", ["country_na"])
    chenab_shapes, _ = save_geojson(chenab_districts(), grid_dir / "chenab_districts.geojson", ["GAUL2_NAME", "GAUL1_NAME"])
    pak = transform(TO_GRID.transform, pak_shapes[0].union_all() if hasattr(pak_shapes[0], "union_all") else pak_shapes[0])
    if len(pak_shapes) > 1:
        from shapely import union_all
        pak = transform(TO_GRID.transform, union_all(pak_shapes))
    from shapely import union_all
    chenab = transform(TO_GRID.transform, union_all(chenab_shapes))
    minx, miny, maxx, maxy = pak.bounds
    x0, y0 = np.floor(minx / CELL_M) * CELL_M, np.floor(miny / CELL_M) * CELL_M
    x1, y1 = np.ceil(maxx / CELL_M) * CELL_M, np.ceil(maxy / CELL_M) * CELL_M
    width, height = int((x1 - x0) // CELL_M), int((y1 - y0) // CELL_M)
    grid = {"crs": CRS, "cell_m": CELL_M, "x0": float(x0), "y1": float(y1), "width": width, "height": height}
    print("grid", grid, flush=True)

    cells = []
    for row in range(height):
        for col in range(width):
            cx0, cy1 = x0 + col * CELL_M, y1 - row * CELL_M
            cells.append((row, col, box(cx0, cy1 - CELL_M, cx0 + CELL_M, cy1)))
    tree = STRtree([cell for _, _, cell in cells])
    pak_fraction = np.zeros((height, width), dtype=np.float32)
    chenab_fraction = np.zeros((height, width), dtype=np.float32)
    for index in tree.query(pak):
        row, col, cell = cells[index]
        pak_fraction[row, col] = cell.intersection(pak).area / cell.area
    for index in tree.query(chenab):
        row, col, cell = cells[index]
        chenab_fraction[row, col] = cell.intersection(chenab).area / cell.area

    # Earth Engine: two-stage aggregation (native -> 1 km -> 20 km) keeps reduceResolution within limits.
    km_proj, cell_proj = projection(1000), projection(CELL_M)
    km = lambda image, reducer=ee.Reducer.mean(), max_pixels=512: image.reduceResolution(reducer, maxPixels=max_pixels).reproject(km_proj)
    cell = lambda image, reducer=ee.Reducer.mean(): image.reduceResolution(reducer, maxPixels=1024)
    dem = ee.Image("MERIT/DEM/v1_0_3").select("dem")
    slope = ee.Terrain.slope(dem)
    upa = ee.Image("MERIT/Hydro/v1_0_1").select("upa")
    built = ee.Image("JRC/GHSL/P2023A/GHS_BUILT_S/2020").select("built_surface").divide(10000)   # m2 per 100 m pixel -> fraction
    cover = ee.ImageCollection("MODIS/061/MCD12Q1").filterDate("2020-01-01", "2021-01-01").first().select("LC_Type1")   # IGBP, 500 m
    population = ee.Image("JRC/GHSL/P2023A/GHS_POP/2020").select("population_count")
    provinces = ee.FeatureCollection("FAO/GAUL/2025/level1").filter(ee.Filter.eq("GAUL0_NAME", "Pakistan"))
    province_image = ee.Image(0).byte()
    for code, name in PROVINCE_CODES.items():
        province_image = province_image.paint(provinces.filter(ee.Filter.eq("GAUL1_NAME", name)), code)
    dem_km = km(dem)
    stack = ee.Image.cat([
        cell(province_image.reproject(km_proj), ee.Reducer.mode()).rename("province_code"),
        cell(dem_km).rename("elev_mean_m"),
        cell(dem_km, ee.Reducer.max()).rename("elev_max_m"),
        cell(dem_km, ee.Reducer.min()).rename("elev_min_m"),
        cell(dem_km, ee.Reducer.stdDev()).rename("elev_std_m"),
        cell(km(slope)).rename("slope_mean_deg"),
        cell(km(slope.gt(15))).rename("steep_fraction"),
        cell(km(upa, ee.Reducer.max()), ee.Reducer.max()).rename("upstream_area_max_km2"),
        cell(km(built)).rename("built_fraction"),
        cell(km(cover.eq(12).Or(cover.eq(14)))).rename("cropland_fraction"),
        cell(km(cover.eq(16))).rename("bare_fraction"),
        cell(km(cover.eq(15))).rename("snow_ice_fraction"),
        cell(km(cover.gte(1).And(cover.lte(5)))).rename("tree_fraction"),
        cell(km(population.updateMask(population.gte(0)))).multiply(100).rename("population_per_km2"),   # people per 100 m pixel x 100 = per km2; negative no-data masked
    ]).toFloat()
    names = stack.bandNames().getInfo()
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=4) as pool:
        arrays = dict(zip(names, pool.map(lambda name: compute_tiled(stack, name, grid), names)))
    values = arrays
    print("bands computed:", ", ".join(names), flush=True)

    keep = np.argwhere(pak_fraction >= 0.1)
    rows, cols = keep[:, 0], keep[:, 1]
    print(f"cells with >=10% inside Pakistan: {len(rows)} of {width * height}; Chenab-district cells (>=25%): {int((chenab_fraction[rows, cols] >= 0.25).sum())}", flush=True)
    created = datetime.now(timezone.utc).isoformat(timespec="seconds")
    grid.update(min_pakistan_fraction=0.1, cells=int(len(rows)), created_utc=created,
                boundary="USDOS/LSIB_SIMPLE/2017 country_na=Pakistan (includes AJK and Gilgit-Baltistan)",
                chenab_area=f"FAO/GAUL/2025/level2 districts: {', '.join(CHENAB_DISTRICTS)}; a cell counts when >=25% of it lies in them")
    GRID_JSON.write_text(json.dumps(grid, indent=2) + "\n", encoding="utf-8")
    centers_x = x0 + (cols + 0.5) * CELL_M
    centers_y = y1 - (rows + 0.5) * CELL_M
    lons, lats = TO_LONLAT.transform(centers_x, centers_y)
    cells_csv = grid_dir / "cells.csv"
    with cells_csv.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["cell_id", "row", "col", "x_center_m", "y_center_m", "lon", "lat", "pakistan_fraction", "chenab_fraction", "province"])
        for index, (row, col) in enumerate(zip(rows, cols)):
            writer.writerow([index, int(row), int(col), float(centers_x[index]), float(centers_y[index]), round(float(lons[index]), 5), round(float(lats[index]), 5),
                             round(float(pak_fraction[row, col]), 4), round(float(chenab_fraction[row, col]), 4),
                             PROVINCE_CODES.get(int(round(values["province_code"][row, col])), "")])
    static = {name: values[name][rows, cols] for name in names if name != "province_code"}
    static["pakistan_fraction"] = pak_fraction[rows, cols]
    static["chenab_fraction"] = chenab_fraction[rows, cols]
    sha = save_npz(GEE_DIR / "static" / "static_features.npz", rows=rows.astype(np.int16), cols=cols.astype(np.int16), **static)
    receipt = {"created_utc": created, "grid_definition": "grid/grid_definition.json", "cells_csv_sha256": sha256_file(cells_csv),
               "static_npz_sha256": sha, "bands": sorted(static),
               "sources": {"boundary": "USDOS/LSIB_SIMPLE/2017 (saved as grid/pakistan_lsib.geojson)",
                           "chenab_districts": "FAO/GAUL/2025/level2 (saved as grid/chenab_districts.geojson)",
                           "provinces": "FAO/GAUL/2025/level1 (cell mode; AJK and Gilgit-Baltistan are not GAUL Pakistan provinces and stay blank)",
                           "elevation": "MERIT/DEM/v1_0_3, mean to 1 km, then mean/max/min/std over 20 km",
                           "slope": "ee.Terrain.slope of MERIT DEM; mean and fraction steeper than 15 degrees",
                           "upstream_area": "MERIT/Hydro/v1_0_1 upa (km2), maximum in cell",
                           "built_up": "JRC/GHSL/P2023A/GHS_BUILT_S 2020 built surface fraction", "land_cover": "MODIS/061/MCD12Q1 2020 IGBP class fractions (cropland 12+14, barren 16, snow and ice 15, forest 1-5)", "population": "JRC/GHSL/P2023A/GHS_POP 2020, mean people per km2 over the cell (negative no-data values masked)"},
               "method": "Cell fractions from exact polygon intersection (shapely, EPSG:6933). Other bands via Earth Engine reduceResolution and computePixels on the same grid. No interpolation or filling."}
    (GEE_DIR / "static").mkdir(parents=True, exist_ok=True)
    (GEE_DIR / "static" / "source_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    for name in sorted(static):
        column = static[name]
        print(f"  {name:24s} min {np.nanmin(column):10.3f}  median {np.nanmedian(column):10.3f}  max {np.nanmax(column):12.3f}  nan {int(np.isnan(column).sum())}", flush=True)


if __name__ == "__main__":
    main()
