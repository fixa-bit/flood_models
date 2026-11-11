"""Extend Marala ERA5-Land daily catchment means past 2024-12-31.

The short-range dataset stops at 2024-12-31. This script re-extracts 2024 (an
overlap year used only to verify that the method reproduces the stored values)
and then every available day from 2025-01-01 onward, from
ECMWF/ERA5_LAND/DAILY_AGGR on Google Earth Engine.

Two methods are copied exactly from the short-range extractors, each with the
catchment file that extractor used:

* precipitation and 2 m temperature (``rainfall|temperature/google_earth_engine``):
  native-grid ``crsTransform``, ``Reducer.mean().splitWeights()`` weighted by
  ``pixelArea``; ERA5 precipitation negatives clipped to 0 (packing artefacts).
* dewpoint, PET, snowmelt, snow depth, SWE and solar radiation (``extract_snow.py``,
  ``extract_pet.py``, ``extract_dewpoint_ssrd.py``): ``Reducer.mean()`` at 11 132 m.

Nothing is filled. A day without exactly one source image is not written.

Run (from this folder):
    ../../.venv/Scripts/python.exe extract_era5land_extension.py --project <ee-project>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
SHORT = HERE.parents[2] / "short range" / "dataset" / "chenab_marala"
CATCHMENT_AREA_WEIGHTED = SHORT / "raw/marala/rainfall/google_earth_engine/marala_upstream_catchment.geojson"
CATCHMENT_PLAIN_MEAN = SHORT / "processed/marala/catchment/marala_upstream_catchment.geojson"
COLLECTION = "ECMWF/ERA5_LAND/DAILY_AGGR"
START = date(2024, 1, 1)  # 2024 is the verification overlap.

# column -> (band, multiply, add)
AREA_WEIGHTED = {
    "precip_era5land_mm": ("total_precipitation_sum", 1000.0, 0.0),
    "temperature_c": ("temperature_2m", 1.0, -273.15),
}
PLAIN_MEAN = {
    "dewpoint_c": ("dewpoint_temperature_2m", 1.0, -273.15),
    "pet_mm": ("potential_evaporation_sum", -1000.0, 0.0),
    "snowmelt_mm": ("snowmelt_sum", 1000.0, 0.0),
    "snow_depth_m": ("snow_depth", 1.0, 0.0),
    "swe_mm": ("snow_depth_water_equivalent", 1000.0, 0.0),
    "ssrd_wm2": ("surface_solar_radiation_downwards_sum", 1.0 / 86400.0, 0.0),
}
COLUMNS = ["date", *AREA_WEIGHTED, *PLAIN_MEAN]
ee = None


def load_geometry(path: Path):
    document = json.loads(path.read_text(encoding="utf-8"))
    if document["type"] == "FeatureCollection":
        return ee.FeatureCollection(document).geometry()
    if document["type"] == "Feature":
        return ee.Feature(document).geometry()
    return ee.Geometry(document)


def table(start: date, end: date, poly_weighted, poly_plain, grid):
    images = ee.ImageCollection(COLLECTION).filterDate(str(start), str(end))
    pixel_area = ee.Image.pixelArea().rename("area")
    weighted_opts = dict(geometry=poly_weighted, maxPixels=10_000_000, tileScale=4, **grid)

    def daily(item):
        image = ee.Image(item)
        props = {"date": image.date().format("YYYY-MM-dd", "UTC")}
        for column, (band, mul, add) in AREA_WEIGHTED.items():
            value = image.select(band).multiply(mul).add(add)
            if column == "precip_era5land_mm":
                value = value.max(0)
            result = value.rename("v").addBands(pixel_area).reduceRegion(
                ee.Reducer.mean().splitWeights(), **weighted_opts)
            props[column] = result.values().get(0)
        plain = ee.Image.cat([image.select(band).multiply(mul).add(add).rename(column)
                              for column, (band, mul, add) in PLAIN_MEAN.items()])
        means = plain.reduceRegion(reducer=ee.Reducer.mean(), geometry=poly_plain, scale=11132,
                                   crs=image.select("temperature_2m").projection(),
                                   maxPixels=10_000_000, tileScale=4)
        for column in PLAIN_MEAN:
            props[column] = means.get(column)
        return ee.Feature(None, props)

    return ee.FeatureCollection(images.toList(images.size()).map(daily))


def download(start, end, poly_weighted, poly_plain, grid):
    for attempt in range(3):
        try:
            url = table(start, end, poly_weighted, poly_plain, grid).getDownloadURL(filetype="CSV", selectors=COLUMNS)
            with urlopen(url, timeout=300) as response:
                rows = list(csv.DictReader(io.StringIO(response.read().decode("utf-8-sig"))))
            stamps = [r["date"] for r in rows]
            if len(stamps) != len(set(stamps)) or any(not str(start) <= s < str(end) for s in stamps):
                raise ValueError("duplicate or out-of-range dates")
            return sorted(rows, key=lambda r: r["date"])
        except Exception as error:  # Earth Engine size/time limits: retry, then split.
            print(f"{start}..{end} attempt {attempt + 1}: {type(error).__name__}: {str(error)[:200]}", flush=True)
            time.sleep(2 ** (attempt + 1))
    if (end - start).days <= 1:
        raise RuntimeError(f"could not extract {start}")
    mid = start + timedelta(days=(end - start).days // 2)
    return download(start, mid, poly_weighted, poly_plain, grid) + download(mid, end, poly_weighted, poly_plain, grid)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--project", required=True)
    parser.add_argument("--chunk-days", type=int, default=61)
    args = parser.parse_args()
    global ee
    import ee as _ee
    ee = _ee
    ee.Initialize(project=args.project)

    collection = ee.ImageCollection(COLLECTION)
    last_millis = collection.filterDate(str(START), "2100-01-01").aggregate_max("system:time_start").getInfo()
    last_day = datetime.fromtimestamp(last_millis / 1000, tz=timezone.utc).date()
    end = last_day + timedelta(days=1)  # exclusive
    projection = ee.Image(collection.filterDate("2020-01-01", "2020-01-02").first()).select(
        "total_precipitation_sum").projection().getInfo()
    grid = {"crs": projection["crs"], "crsTransform": projection["transform"]}
    poly_weighted = load_geometry(CATCHMENT_AREA_WEIGHTED)
    poly_plain = load_geometry(CATCHMENT_PLAIN_MEAN)
    print(f"Latest {COLLECTION} image: {last_day}", flush=True)

    rows, start = [], START
    while start < end:
        stop = min(end, start + timedelta(days=args.chunk_days))
        rows += download(start, stop, poly_weighted, poly_plain, grid)
        print(f"extracted {start}..{stop - timedelta(days=1)} ({len(rows)} rows)", flush=True)
        start = stop

    out = HERE / f"marala_era5land_daily_{START}_{last_day}.csv"
    with out.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    expected = (end - START).days
    missing = sorted({str(START + timedelta(days=i)) for i in range(expected)} - {r["date"] for r in rows})
    receipt = {
        "collection": COLLECTION,
        "retrieved_at_utc": datetime.now(timezone.utc).isoformat(),
        "period": [str(START), str(last_day)],
        "verification_overlap": ["2024-01-01", "2024-12-31"],
        "methods": {
            "area_weighted": {"columns": list(AREA_WEIGHTED), "reducer": "Reducer.mean().splitWeights() with pixelArea",
                              "grid": grid, "catchment": str(CATCHMENT_AREA_WEIGHTED.relative_to(SHORT.parents[1])),
                              "catchment_sha256": hashlib.sha256(CATCHMENT_AREA_WEIGHTED.read_bytes()).hexdigest()},
            "plain_mean": {"columns": list(PLAIN_MEAN), "reducer": "Reducer.mean()", "scale_m": 11132,
                           "catchment": str(CATCHMENT_PLAIN_MEAN.relative_to(SHORT.parents[1])),
                           "catchment_sha256": hashlib.sha256(CATCHMENT_PLAIN_MEAN.read_bytes()).hexdigest()},
        },
        "conversions": {c: {"band": b, "multiply": m, "add": a} for c, (b, m, a) in {**AREA_WEIGHTED, **PLAIN_MEAN}.items()},
        "rows": len(rows), "missing_days": missing,
        "file": out.name, "sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
    }
    (HERE / "source_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"saved {out.name}: {len(rows)} rows, {len(missing)} missing days", flush=True)


if __name__ == "__main__":
    main()
