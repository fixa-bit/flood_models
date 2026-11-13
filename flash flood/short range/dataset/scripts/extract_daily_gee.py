"""Extract daily gridded inputs for the flash-flood grid, one file per month and source.

imerg     NASA/GPM_L3/IMERG_V07 (Final run, half-hourly). Days are Pakistan local days
          (00:00-24:00 PKT = 19:00-19:00 UTC). For each cell: area-mean daily total (mm) and the
          largest 3-hour accumulation in any IMERG pixel of the cell (mm), from eight 3-hour blocks.
era5land  ECMWF/ERA5_LAND/DAILY_AGGR (UTC days): area-mean top-layer soil moisture (m3/m3),
          maximum 2 m temperature (deg C) and snowmelt (mm).

Output: raw/gee/<source>/<YYYY-MM>.npz with arrays (days x cells) in cells.csv order, plus a
source_receipt.json listing every month, its checksum and any incomplete days. Existing months
are skipped, so the script can resume. Missing source data stays missing (NaN).

Run from this folder: ../../../.venv/Scripts/python.exe extract_daily_gee.py --source imerg --start 2009-12 --end 2026-01
"""
from __future__ import annotations

import argparse
import calendar
import json
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timezone

import ee
import numpy as np

from gee_common import GEE_DIR, GRID_JSON, compute, initialize, sha256_file, save_npz

LOCK = threading.Lock()


def months(start, end):
    year, month = map(int, start.split("-"))
    stop = tuple(map(int, end.split("-")))
    while (year, month) <= stop:
        yield year, month
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)


def masked_like(band):
    return ee.Image.constant(0).rename(band).toFloat().updateMask(0)


def imerg_month(year, month):
    collection = ee.ImageCollection("NASA/GPM_L3/IMERG_V07").select("precipitation")
    native = collection.first().projection()
    days = calendar.monthrange(year, month)[1]
    start = ee.Date.fromYMD(year, month, 1, "Asia/Karachi")
    stamps = collection.filterDate(start, start.advance(days, "day")).aggregate_array("system:time_start").getInfo()
    month_start_ms = datetime(year, month, 1, tzinfo=timezone.utc).timestamp() * 1000 - 5 * 3600 * 1000
    counts = np.zeros(days, dtype=np.int16)
    for stamp in stamps:
        index = int((stamp - month_start_ms) // (24 * 3600 * 1000))
        if 0 <= index < days:
            counts[index] += 1
    bands = []
    for day in range(days):
        day_start = start.advance(day, "day")
        blocks = []
        for block in range(8):
            t0 = day_start.advance(3 * block, "hour")
            part = collection.filterDate(t0, t0.advance(3, "hour")).merge(ee.ImageCollection([masked_like("precipitation")]))
            blocks.append(part.sum().multiply(0.5).setDefaultProjection(native))   # mm/hr x 0.5 h per image
        stack = ee.ImageCollection(blocks)
        total = stack.sum().setDefaultProjection(native).reduceResolution(ee.Reducer.mean(), maxPixels=1024)
        peak = stack.max().setDefaultProjection(native).reduceResolution(ee.Reducer.max(), maxPixels=1024)
        bands += [total.rename(f"total_{day:02d}"), peak.rename(f"max3h_{day:02d}")]
    image = ee.Image.cat(bands).toFloat()
    array = compute(image)
    names = {"precip_total_mm": "total", "precip_max3h_mm": "max3h"}
    data = {key: np.stack([np.asarray(array[f"{prefix}_{day:02d}"], dtype=np.float32) for day in range(days)]) for key, prefix in names.items()}
    return data, {"halfhour_images": counts.tolist(), "incomplete_days": [day + 1 for day in range(days) if counts[day] != 48]}


def era5_month(year, month):
    bands_needed = ["volumetric_soil_water_layer_1", "temperature_2m_max", "snowmelt_sum"]
    raw = ee.ImageCollection("ECMWF/ERA5_LAND/DAILY_AGGR")
    native = raw.first().projection()
    collection = raw.select(bands_needed).map(lambda image: image.toFloat())
    days = calendar.monthrange(year, month)[1]
    start = ee.Date.fromYMD(year, month, 1)
    available = collection.filterDate(start, start.advance(days, "day")).aggregate_array("system:index").getInfo()
    bands = []
    for day in range(days):
        current = start.advance(day, "day")
        image = collection.filterDate(current, current.advance(1, "day")).merge(ee.ImageCollection([
            ee.Image.constant([0, 0, 0]).rename(["volumetric_soil_water_layer_1", "temperature_2m_max", "snowmelt_sum"]).toFloat().updateMask(0)])).max()
        image = image.setDefaultProjection(native)
        mean = lambda band: image.select(band).reduceResolution(ee.Reducer.mean(), maxPixels=1024)
        bands += [mean("volumetric_soil_water_layer_1").rename(f"swvl1_{day:02d}"),
                  mean("temperature_2m_max").subtract(273.15).rename(f"t2max_{day:02d}"),
                  mean("snowmelt_sum").multiply(1000).rename(f"melt_{day:02d}")]
    array = compute(ee.Image.cat(bands).toFloat())
    names = {"soil_moisture_m3m3": "swvl1", "t2m_max_c": "t2max", "snowmelt_mm": "melt"}
    data = {key: np.stack([np.asarray(array[f"{prefix}_{day:02d}"], dtype=np.float32) for day in range(days)]) for key, prefix in names.items()}
    found = {name[:8] for name in available}
    missing = [day + 1 for day in range(days) if f"{year:04d}{month:02d}{day + 1:02d}" not in found]
    return data, {"images": len(available), "incomplete_days": missing}


SOURCES = {
    "imerg": {"folder": "imerg_v07", "extract": imerg_month, "collection": "NASA/GPM_L3/IMERG_V07 (Final, half-hourly)",
              "day": "Pakistan local day, 00:00-24:00 PKT (UTC+5)",
              "variables": {"precip_total_mm": "cell area-mean daily total", "precip_max3h_mm": "largest 3-hour accumulation in any IMERG pixel touching the cell"}},
    "era5land": {"folder": "era5land_daily", "extract": era5_month, "collection": "ECMWF/ERA5_LAND/DAILY_AGGR",
                 "day": "UTC day (ends 05:00 PKT)",
                 "variables": {"soil_moisture_m3m3": "area-mean volumetric soil water 0-7 cm", "t2m_max_c": "area-mean daily maximum 2 m temperature",
                               "snowmelt_mm": "area-mean daily snowmelt"}},
}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--source", choices=sorted(SOURCES), required=True)
    parser.add_argument("--start", default="2009-12")
    parser.add_argument("--end", default="2026-01")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    initialize()
    spec = SOURCES[args.source]
    folder = GEE_DIR / spec["folder"]
    folder.mkdir(parents=True, exist_ok=True)
    grid = json.loads(GRID_JSON.read_text(encoding="utf-8"))
    static = np.load(GEE_DIR / "static" / "static_features.npz")
    rows, cols = static["rows"].astype(int), static["cols"].astype(int)
    receipt_path = folder / "source_receipt.json"
    receipt = json.loads(receipt_path.read_text(encoding="utf-8")) if receipt_path.exists() else {}
    receipt.update(collection=spec["collection"], day_definition=spec["day"], variables=spec["variables"],
                   grid="../grid/grid_definition.json", cells=int(len(rows)), cell_order="cells.csv cell_id",
                   method="Earth Engine reduceResolution to the 20 km EPSG:6933 grid via computePixels; missing data stays NaN")
    receipt.setdefault("months", {})
    todo = [(year, month) for year, month in months(args.start, args.end) if not (folder / f"{year:04d}-{month:02d}.npz").exists()]
    print(f"{args.source}: {len(todo)} months to extract into {folder}", flush=True)

    def work(year, month):
        data, info = spec["extract"](year, month)
        # computePixels returns fully masked pixels (e.g. sea cells in ERA5-Land) as -inf: keep them missing.
        cells = {key: np.where(np.isfinite(value[:, rows, cols]), value[:, rows, cols], np.nan).astype(np.float32) for key, value in data.items()}
        days = np.array([date(year, month, day + 1).isoformat() for day in range(next(iter(cells.values())).shape[0])])
        sha = save_npz(folder / f"{year:04d}-{month:02d}.npz", dates=days, **cells)
        return f"{year:04d}-{month:02d}", {**info, "sha256": sha, "extracted_utc": datetime.now(timezone.utc).isoformat(timespec="seconds")}

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(work, year, month): (year, month) for year, month in todo}
        for future in as_completed(futures):
            year, month = futures[future]
            try:
                key, info = future.result()
            except Exception as error:
                print(f"  {year:04d}-{month:02d} FAILED: {str(error)[:200]}", flush=True)
                continue
            with LOCK:
                receipt["months"][key] = info
                receipt["months"] = dict(sorted(receipt["months"].items()))
                receipt_path.write_text(json.dumps(receipt, indent=1) + "\n", encoding="utf-8")
            note = f" incomplete days {info['incomplete_days']}" if info.get("incomplete_days") else ""
            print(f"  {key} done{note}", flush=True)


if __name__ == "__main__":
    main()
