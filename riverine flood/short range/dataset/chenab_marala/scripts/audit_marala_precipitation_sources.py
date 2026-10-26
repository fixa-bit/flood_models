"""Preserve source responses and compare Marala rainfall on selected UTC days.

Requires shapely, pyproj and rasterio. No existing collection file is modified.
Run from any directory: python audit_marala_precipitation_sources.py
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import struct
import time
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

import rasterio
from pyproj import Transformer
from rasterio.io import MemoryFile
from rasterio.windows import Window, from_bounds
from shapely import segmentize, transform
from shapely.geometry import box, shape

MODEL = Path(__file__).resolve().parents[1]
RAW = MODEL / "raw/marala/rainfall"
OUT = MODEL / "processed/marala/rainfall/source_comparison_2026-10-26"
BOUNDARY = MODEL / "processed/marala/catchment/marala_upstream_catchment.geojson"
SOURCE = "https://erddap.aoml.noaa.gov/hdb/erddap/griddap"
LAEA = Transformer.from_crs(4326, "+proj=laea +lat_0=33 +lon_0=76 +datum=WGS84 +units=m +no_defs", always_xy=True)
CASES = {
    "ordinary": ["2016-03-01", "2016-07-15"],
    "2014_flood": ["2014-09-04", "2014-09-05", "2014-09-06"],
    "2016_flood": ["2016-08-05", "2016-08-06", "2016-08-07"],
    "power_disagreement": ["2024-03-02", "2024-08-08"],
}
DAYS = sorted({day for days in CASES.values() for day in days})
CASE_FOR = {day: name for name, days in CASES.items() for day in days}


def digest(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def ranged_download(url: str) -> bytes:
    """Parallel byte ranges for the large, immutable daily CHIRPS GeoTIFFs."""
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=40) as response:
        size = int(response.headers["Content-Length"])
    boundaries = [(start, min(size - 1, start + 2_999_999)) for start in range(0, size, 3_000_000)]

    def part(bounds):
        start, end = bounds
        request = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
        with urllib.request.urlopen(request, timeout=90) as response:
            body = response.read()
            if response.status != 206 or response.headers.get("Content-Range") != f"bytes {start}-{end}/{size}":
                raise ValueError("CHIRPS server did not honor the requested byte range")
        if len(body) != end - start + 1:
            raise ValueError("Short CHIRPS byte range")
        return body

    with ThreadPoolExecutor(max_workers=4) as pool:
        body = b"".join(pool.map(part, boundaries))
    if len(body) != size:
        raise ValueError("Incomplete CHIRPS GeoTIFF")
    return body


def get_saved(url: str, path: Path, ranged: bool = False) -> tuple[bytes, dict]:
    """Download once; subsequent runs verify rather than overwrite evidence."""
    receipt_path = path.with_name(path.name + ".receipt.json")
    if path.exists():
        if not receipt_path.exists():
            raise ValueError(f"Saved source lacks receipt: {path}")
        body = path.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["sha256"] != digest(body) or receipt["source_url"] != url:
            raise ValueError(f"Saved source or URL changed: {path}")
        return body, receipt
    if receipt_path.exists():
        raise ValueError(f"Receipt exists without source: {receipt_path}")
    for attempt in range(3):
        try:
            if ranged:
                body = ranged_download(url)
            else:
                with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Marala-source-audit/1.0"}), timeout=90) as response:
                    body = response.read()
            break
        except Exception:
            if attempt == 2:
                raise
            time.sleep(3 * (attempt + 1))
    if not body:
        raise ValueError(f"Empty source response: {url}")
    receipt = {"source_url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
               "sha256": digest(body), "bytes": len(body), "raw_file": path.relative_to(MODEL).as_posix()}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return body, receipt


def projected(geom):
    return transform(segmentize(geom, .005), LAEA.transform, interleaved=False)


def build_weights(basin, pixels):
    area = projected(basin).area
    weights = []
    for lat, lon, footprint in pixels:
        if not basin.intersects(footprint):
            continue
        overlap = projected(basin.intersection(footprint)).area
        if overlap > 0:
            weights.append((lat, lon, overlap / area))
    covered = math.fsum(weight for _, _, weight in weights)
    if not math.isclose(covered, 1, abs_tol=2e-5):
        raise ValueError(f"Source grid does not cover the catchment: {covered:.8f}")
    return weights


def power_url(lat, lon, start, end, temporal="daily"):
    params = {"parameters": "PRECTOTCORR", "community": "AG", "longitude": f"{lon:g}", "latitude": f"{lat:g}",
              "start": start.replace("-", ""), "end": end.replace("-", ""), "format": "JSON", "time-standard": "UTC"}
    return f"https://power.larc.nasa.gov/api/temporal/{temporal}/point?" + urllib.parse.urlencode(params)


def power_request(cell, start, end, label, temporal="daily"):
    lat, lon = cell
    name = f"lat_{lat:g}_lon_{lon:g}"
    filename = RAW / "nasa_power" / "investigation_2026-10-26" / name / f"{label}_{start}_{end}_{temporal}.json"
    data, receipt = get_saved(power_url(lat, lon, start, end, temporal), filename)
    doc = json.loads(data)
    header = doc["header"]
    expected = "mm/hour" if temporal == "hourly" else "mm/day"
    if doc["parameters"]["PRECTOTCORR"]["units"] != expected or header["time_standard"] != "UTC":
        raise ValueError("POWER unit or time standard changed")
    if header["start"] != start.replace("-", "") or header["end"] != end.replace("-", ""):
        raise ValueError("POWER returned an unexpected period")
    coordinate = doc["geometry"]["coordinates"]
    if abs(coordinate[0] - lon) > 1e-6 or abs(coordinate[1] - lat) > 1e-6:
        raise ValueError("POWER point response returned another coordinate")
    return doc["properties"]["parameter"]["PRECTOTCORR"], header, receipt


def power_audit():
    old = RAW / "nasa_power" / "cells" / "lat_32.5_lon_74.375.json"
    saved = json.loads(old.read_text(encoding="utf-8"))["properties"]["parameter"]["PRECTOTCORR"]
    target = (32.5, 74.375)
    windows = [
        ("one_day_2016_july", "2016-07-15", "2016-07-15"),
        ("one_day_2016_flood", "2016-08-06", "2016-08-06"),
        ("one_day_march", "2024-03-02", "2024-03-02"),
        ("week_march", "2024-02-28", "2024-03-04"),
        ("month_march", "2024-03-01", "2024-03-31"),
        ("one_day_august", "2024-08-08", "2024-08-08"),
        ("week_august", "2024-08-05", "2024-08-11"),
        ("year_2024", "2024-01-01", "2024-12-31"),
        ("2016_to_2024", "2016-03-01", "2024-12-31"),
        ("mixed_long_range", "2016-03-01", "2026-10-22"),
    ]
    records, heads = [], {}
    for label, start, end in windows:
        values, header, receipt = power_request(target, start, end, label)
        heads[label] = header
        for day in ["20160301", "20160715", "20160806", "20240302", "20240808"]:
            if day in values:
                records.append({"request": label, "start": start, "end": end, "date": f"{day[:4]}-{day[4:6]}-{day[6:]}",
                                "retrieved_mm": values[day], "saved_long_range_mm": saved[day],
                                "source_products": "+".join(header["sources"]), "api_version": header["api"]["version"],
                                "raw_sha256": receipt["sha256"], "source_url": receipt["source_url"]})
        print(f"POWER {label}: {len(values)} days, sources {header['sources']}", flush=True)
    hourly = {}
    for day in ["2016-07-15", "2016-08-06", "2024-03-02", "2024-08-08"]:
        values, header, receipt = power_request(target, day, day, "hourly_check", "hourly")
        day_values = {k: v for k, v in values.items() if k.startswith(day.replace("-", ""))}
        if len(day_values) != 24 or any(not isinstance(v, (int, float)) or v < 0 for v in day_values.values()):
            raise ValueError("Hourly POWER check does not have 24 valid hours")
        hourly[day] = {"hourly_sum_mm": round(math.fsum(day_values.values()), 3), "hour_count": 24,
                       "units": "mm/hour", "source_products": header["sources"], "source_url": receipt["source_url"]}
    write_csv(OUT / "nasa_power_range_comparison.csv", records)
    by = {(row["request"], row["date"]): row["retrieved_mm"] for row in records}
    result = {"hourly_cross_checks": hourly, "same_point_and_parameter": True,
              "same_units": all(row["date"] in ("2016-03-01", "2016-07-15", "2016-08-06", "2024-03-02", "2024-08-08") for row in records),
              "march_single_mm": by[("one_day_march", "2024-03-02")],
              "march_long_mm": by[("mixed_long_range", "2024-03-02")],
              "march_year_mm": by[("year_2024", "2024-03-02")],
              "aug_single_mm": by[("one_day_august", "2024-08-08")],
              "aug_long_mm": by[("mixed_long_range", "2024-08-08")],
              "request_sources": {key: value["sources"] for key, value in heads.items()}}
    return result


def power_basin_spot_checks():
    """Fresh single-day POWER values for all 21 saved catchment weights."""
    weights_path = MODEL / "processed/marala/rainfall/marala_rainfall_grid_cells.csv"
    with weights_path.open(encoding="utf-8", newline="") as handle:
        weights = list(csv.DictReader(handle))
    if len(weights) != 21 or not math.isclose(math.fsum(float(row["area_weight"]) for row in weights), 1, abs_tol=1e-9):
        raise ValueError("Saved NASA grid weights differ from expected full catchment")
    dates = ["2016-07-15", "2016-08-06", "2024-03-02", "2024-08-08"]

    def fetch(row, day):
        value, header, receipt = power_request((float(row["latitude"]), float(row["longitude"])), day, day, "basin_single")
        daily = value.get(day.replace("-", ""))
        if daily is None or not math.isfinite(daily) or daily < 0:
            raise ValueError(f"POWER has missing/invalid source cell on {day}: {row['cell_id']}")
        return {"date": day, "cell_id": row["cell_id"], "area_weight": float(row["area_weight"]),
                "source_mm_day": daily, "source_products": "+".join(header["sources"]),
                "raw_sha256": receipt["sha256"], "source_url": receipt["source_url"]}

    rows = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        jobs = {pool.submit(fetch, row, day): (row["cell_id"], day) for day in dates for row in weights}
        for future in as_completed(jobs):
            rows.append(future.result())
    rows.sort(key=lambda row: (row["date"], row["cell_id"]))
    write_csv(OUT / "nasa_power_fresh_single_day_cells.csv", rows)
    means = {day: math.fsum(row["source_mm_day"]*row["area_weight"] for row in rows if row["date"] == day) for day in dates}
    return means


def power_history_profile(spot_means):
    """Compare every archived 2016-2024 grid value with a fresh consistent request."""
    path = MODEL / "processed/marala/rainfall/marala_rainfall_grid_cells.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        weights = list(csv.DictReader(handle))
    start, end = "2016-03-01", "2024-12-31"
    def fetch(row):
        point = (float(row["latitude"]), float(row["longitude"]))
        fresh, header, receipt = power_request(point, start, end, "historical_mixed_free")
        old_file = RAW / "nasa_power/cells" / f"{row['cell_id']}.json"
        saved = json.loads(old_file.read_text(encoding="utf-8"))["properties"]["parameter"]["PRECTOTCORR"]
        if header["sources"] != ["MERRA2"]:
            raise ValueError(f"The historical request changed sources: {row['cell_id']}")
        return row, fresh, saved, receipt
    records = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        for result in pool.map(fetch, weights):
            records.append(result)
    dates = sorted(records[0][1])
    if len(dates) != 3228 or dates[0] != "20160301" or dates[-1] != "20241231":
        raise ValueError("Unexpected historical NASA POWER coverage")
    rows = []
    profile = {"equal": 0, "near_24_times": 0, "other": 0, "both_zero": 0, "missing": 0}
    by_year = {}
    sample_ratios = []
    for day in dates:
        date_text = f"{day[:4]}-{day[4:6]}-{day[6:]}"
        fresh_terms, saved_terms = [], []
        valid = 0
        for row, fresh, saved, receipt in records:
            f, s = fresh.get(day), saved.get(day)
            weight = float(row["area_weight"])
            if f is None or s is None or f == -999 or s == -999:
                category = "missing"
            elif not math.isfinite(f) or not math.isfinite(s) or f < 0 or s < 0:
                raise ValueError("Invalid POWER historical precipitation")
            else:
                valid += 1
                fresh_terms.append(f*weight)
                saved_terms.append(s*weight)
                if abs(s-f) < .00001:
                    category = "both_zero" if f == 0 else "equal"
                elif f > 0 and math.isclose(s/f, 24, abs_tol=.00001):
                    category = "near_24_times"
                else:
                    category = "other"
                if date_text in spot_means:
                    sample_ratios.append({"date": date_text, "cell_id": row["cell_id"],
                                          "saved_long_request_mm_day": s, "fresh_history_request_mm_day": f,
                                          "ratio_saved_to_fresh": "" if f == 0 else round(s/f, 5),
                                          "classification": category, "cell_weight": weight,
                                          "saved_original_file": str((RAW / "nasa_power/cells" / f"{row['cell_id']}.json").relative_to(MODEL)).replace("\\", "/"),
                                          "fresh_raw_sha256": receipt["sha256"], "fresh_source_url": receipt["source_url"]})
            profile[category] += 1
            by_year.setdefault(day[:4], {name: 0 for name in profile})[category] += 1
        mean = math.fsum(fresh_terms) if valid == 21 else None
        old_mean = math.fsum(saved_terms) if valid == 21 else None
        rows.append({"date": date_text, "fresh_basin_mean_mm_day": "" if mean is None else f"{mean:.6f}",
                     "saved_basin_mean_mm_day": "" if old_mean is None else f"{old_mean:.6f}",
                     "valid_cells": valid, "required_cells": 21, "period_start_utc": f"{date_text}T00:00:00Z",
                     "period_end_utc_exclusive": (datetime.strptime(day, "%Y%m%d")+timedelta(days=1)).strftime("%Y-%m-%dT00:00:00Z"),
                     "training_status": "HOLD; fresh source request needs independent validation"})
        if date_text in spot_means and not math.isclose(mean, spot_means[date_text], abs_tol=1e-5):
            raise ValueError(f"Fresh historical basin and single-day downloads disagree on {date_text}: {mean}, {spot_means[date_text]}")
    write_csv(OUT / "nasa_power_fresh_historical_basin_candidate.csv", rows)
    write_csv(OUT / "nasa_power_sample_cell_disagreements.csv", sample_ratios)
    profile["years"] = by_year
    profile["daily_candidate_rows"] = len(rows)
    profile["full_cell_days"] = sum(row["valid_cells"] == 21 for row in rows)
    return profile


def parse_dods(body: bytes):
    header, payload = body.split(b"\nData:\n", 1)
    header = header.decode("ascii")
    match = re.search(r"Float32\s+\w+\[time = (\d+)\]\[latitude = (\d+)\]\[longitude = (\d+)\]", header)
    if not match:
        raise ValueError("Unexpected NOAA DODS schema")
    nt, ny, nx = map(int, match.groups())
    length = nt * ny * nx
    offset = 0

    def array(item_size, count, code):
        nonlocal offset
        a, b = struct.unpack_from(">II", payload, offset)
        if (a, b) != (count, count):
            raise ValueError(f"DODS array shape error: {(a, b)}, expected {count}")
        offset += 8
        values = struct.unpack_from(f">{count}{code}", payload, offset)
        offset += item_size * count
        offset += (-offset) % 4
        return values

    rates = array(4, length, "f")
    times = array(8, nt, "d")
    lats = array(4, ny, "f")
    lons = array(4, nx, "f")
    if offset != len(payload):
        raise ValueError(f"Unparsed DODS payload bytes: {len(payload)-offset}")
    return rates, times, lats, lons


def imerg_version(day):
    # The v06 archive ends 2 June 2024; the August check uses the v07 archive.
    year = int(day[:4])
    return (f"precipitation_{year}", "precipitationCal", "v06") if day < "2024-06-02" else (f"precipitation_{year}_v07", "precipitation", "v07")


def imerg_day(day, basin, weights_cache):
    dataset, variable, version = imerg_version(day)
    end = day + "T23:30:00Z"
    start = day + "T00:00:00Z"
    xmin, ymin, xmax, ymax = basin.bounds
    # NOAA's IMERG cell centers are -179.95 + 0.1*n, -89.95 + 0.1*n.
    centers = lambda low, high, first: [round(first + n * .1, 2) for n in range(math.floor((low-.05-first)/.1), math.ceil((high+.05-first)/.1)+1)]
    lats = centers(ymin, ymax, -89.95)
    lons = centers(xmin, xmax, -179.95)
    lat_range = f"({lats[0]}):1:({lats[-1]})"
    lon_range = f"({lons[0]}):1:({lons[-1]})"
    query = f"{variable}[({start}):1:({end})][{lat_range}][{lon_range}]"
    url = f"{SOURCE}/{dataset}.dods?" + urllib.parse.quote(query, safe="[]():-.,")
    raw = RAW / "imerg" / "noaa_aoml" / "comparison_2026-10-26" / f"{day}_{version}.dods"
    body, receipt = get_saved(url, raw)
    rates, times, actual_lats, actual_lons = parse_dods(body)
    if len(times) != 48 or datetime.fromtimestamp(times[0], timezone.utc).isoformat().startswith(day) is False:
        raise ValueError(f"IMERG day does not contain 48 half-hour periods: {day}")
    if not math.isclose(times[-1]-times[0], 47*1800, abs_tol=1):
        raise ValueError("IMERG half-hour spacing changed")
    if any(abs(v - w) > 1e-3 for v, w in zip(actual_lats, lats)) or len(actual_lats) != len(lats):
        raise ValueError("IMERG latitude grid differs from request")
    if any(abs(v - w) > 1e-3 for v, w in zip(actual_lons, lons)) or len(actual_lons) != len(lons):
        raise ValueError("IMERG longitude grid differs from request")
    if "weights" not in weights_cache:
        pixels = [(lat, lon, box(lon-.05, lat-.05, lon+.05, lat+.05)) for lat in lats for lon in lons]
        weights_cache["weights"] = build_weights(basin, pixels)
    weights = weights_cache["weights"]
    ix = {(round(lat, 2), round(lon, 2)): j * len(lons) + i for j, lat in enumerate(lats) for i, lon in enumerate(lons)}
    pixels_per_step = len(lats) * len(lons)
    by_pixel = []
    missing = 0
    zero_intervals = 0
    for lat, lon, weight in weights:
        index = ix[(lat, lon)]
        values = [rates[step*pixels_per_step+index] for step in range(48)]
        zero_intervals += sum(value == 0 for value in values)
        if any(not math.isfinite(value) or value < 0 for value in values):
            missing += 1
        else:
            by_pixel.append((math.fsum(values)*.5, weight))
    positive_only = math.fsum(depth * weight for depth, weight in by_pixel) if missing == 0 else None
    # The NOAA v07 mirror marks 0 as both fill and missing; its zeros cannot
    # be distinguished from genuine dry intervals. Do not report a full mean.
    ambiguous = version == "v07" and zero_intervals > 0
    total = None if ambiguous else positive_only
    return {"date": day, "precipitation_mm_day": total, "cells": len(weights), "missing_cells": missing,
            "zero_intervals": zero_intervals, "positive_only_lower_bound_mm_day": positive_only if ambiguous else None,
            "quality_flag": "v07_zero_equals_fill_value" if ambiguous else ("missing_interval" if missing else "sample_complete"),
            "time_period_utc": f"{day}T00:00:00Z to next 00:00:00Z", "version": version,
            "source_run": "NOAA mirror of NASA IMERG half-hourly archive; run label retained in DAS metadata",
            "zero_encoding_note": "NOAA DAS has missing_value=0; raw DODS zeroes retained as zero because NASA IMERG specifies -9999.9 as missing. Review before training.",
            "raw_sha256": receipt["sha256"], "source_url": receipt["source_url"]}


def chirps_day(day, basin, weights_cache):
    year, month, dom = day.split("-")
    path = f"{year}/chirps-v3.0.rnl.{year}.{month}.{dom}.tif"
    url = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/rnl/" + path
    raw = RAW / "chirps_v3" / "rnl" / "comparison_2026-10-26" / path
    body, receipt = get_saved(url, raw, ranged=True)
    with MemoryFile(body) as mem, mem.open() as tif:
        if tif.count != 1 or tif.crs.to_epsg() != 4326:
            raise ValueError("CHIRPS raster shape or CRS changed")
        rough = from_bounds(*basin.bounds, transform=tif.transform)
        left, top = math.floor(rough.col_off), math.floor(rough.row_off)
        right, bottom = math.ceil(rough.col_off + rough.width), math.ceil(rough.row_off + rough.height)
        window = Window(left, top, right-left, bottom-top)
        data = tif.read(1, window=window, masked=False)
        if "weights" not in weights_cache:
            pixels = []
            for row in range(data.shape[0]):
                for col in range(data.shape[1]):
                    west, south, east, north = rasterio.windows.bounds(rasterio.windows.Window(window.col_off+col, window.row_off+row, 1, 1), tif.transform)
                    pixels.append((row, col, box(west, south, east, north)))
            weights_cache["weights"] = build_weights(basin, pixels)
        weights = weights_cache["weights"]
        missing = 0
        terms = []
        for row, col, weight in weights:
            value = float(data[row, col])
            if not math.isfinite(value) or value == tif.nodata or value < 0:
                missing += 1
            else:
                terms.append(value * weight)
        total = math.fsum(terms) if missing == 0 else None
        return {"date": day, "precipitation_mm_day": total, "cells": len(weights), "missing_cells": missing,
                "time_period_utc": "UTC day label; station observation windows within pentad may differ",
                "daily_method": "CHIRPS v3 Final rnl: pentad total distributed to days using ERA5",
                "nodata": tif.nodata, "raw_sha256": receipt["sha256"], "source_url": receipt["source_url"]}


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    boundary_bytes = BOUNDARY.read_bytes()
    basin = shape(json.loads(boundary_bytes)["features"][0]["geometry"])
    if not basin.is_valid:
        raise ValueError("Marala boundary is invalid")
    original = list((RAW / "nasa_power" / "cells").glob("*.json"))
    original_hashes = {str(p.relative_to(MODEL)): digest(p.read_bytes()) for p in original}
    power = power_audit()
    fresh_power_basin = power_basin_spot_checks()
    power_history = power_history_profile(fresh_power_basin)
    if (power["march_single_mm"], power["march_long_mm"]) == (35.47, 851.28):
        print("Confirmed: 2024-03-02 one-day=35.47; saved long-range=851.28", flush=True)
    # Existing NASA basin values are retained as disputed comparison data.
    existing = {}
    with (MODEL / "processed/marala/rainfall/marala_catchment_daily_precipitation.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            existing[row["date"]] = float(row["precipitation_mm_day"]) if row["precipitation_mm_day"] else None
    metadata = {}
    for dataset, variable, version in sorted({imerg_version(day) for day in DAYS}):
        url = f"{SOURCE}/{dataset}.das"
        path = RAW / "imerg/noaa_aoml/comparison_2026-10-26/metadata" / f"{dataset}.das"
        body, receipt = get_saved(url, path)
        das = body.decode("utf-8")
        block = das[das.find("  " + variable + " {"):das.find("  NC_GLOBAL {")]
        if 'String units "MM/Hr"' not in block:
            raise ValueError(f"IMERG rates are no longer in MM/Hr for {dataset}")
        metadata[dataset] = {"version": version, "variable": variable, "source_url": url,
                             "sha256": receipt["sha256"], "fill_value": re.search(r"Float32 _FillValue ([^;]+);", block).group(1),
                             "missing_value": re.search(r"Float32 missing_value ([^;]+);", block).group(1),
                             "source_archive": re.search(r"GPM_L3/([^/]+)", das).group(1)}
    imerg_cache, chirps_cache = {}, {}
    outcomes = {}
    def collect(day):
        # Each source is processed in its own worker; weights are immutable once built.
        return day, imerg_day(day, basin, imerg_cache), chirps_day(day, basin, chirps_cache)
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(collect, day): day for day in DAYS}
        for future in as_completed(jobs):
            day, imerg, chirps = future.result()
            outcomes[day] = (imerg, chirps)
            print(f"Compared {day}: IMERG={imerg['precipitation_mm_day']}, CHIRPS={chirps['precipitation_mm_day']}", flush=True)
    imerg_rows = [outcomes[day][0] for day in DAYS]
    chirps_rows = [outcomes[day][1] for day in DAYS]
    write_csv(OUT / "imerg_daily_catchment_sample.csv", imerg_rows)
    write_csv(OUT / "chirps_v3_daily_catchment_sample.csv", chirps_rows)
    comparison = [{"date": day, "case": CASE_FOR[day], "nasa_power_saved_mm": existing.get(day),
                   "nasa_power_fresh_single_day_mm": fresh_power_basin.get(day),
                   "imerg_mm": outcomes[day][0]["precipitation_mm_day"],
                   "imerg_positive_only_lower_bound_mm": outcomes[day][0]["positive_only_lower_bound_mm_day"],
                   "imerg_quality_flag": outcomes[day][0]["quality_flag"],
                   "chirps_v3_rnl_mm": outcomes[day][1]["precipitation_mm_day"],
                   "imerg_missing_cells": outcomes[day][0]["missing_cells"],
                   "chirps_missing_cells": outcomes[day][1]["missing_cells"],
                   "training_status": "HOLD; source comparison only"} for day in DAYS]
    write_csv(OUT / "marala_precipitation_source_comparison.csv", comparison)
    after = {str(p.relative_to(MODEL)): digest(p.read_bytes()) for p in original}
    if after != original_hashes:
        raise RuntimeError("Original NASA POWER grid files changed during audit")
    report = {"created_utc": datetime.now(timezone.utc).isoformat(), "catchment_boundary_sha256": digest(boundary_bytes),
              "saved_nasa_power_source_files_unchanged": True, "saved_nasa_power_originals_checked": len(original),
              "power_range_test": power, "case_dates": CASES, "comparison_rows": len(comparison),
              "power_fresh_single_day_basin_means_mm": fresh_power_basin,
              "power_historical_profile": power_history,
              "imerg_metadata": metadata,
              "imerg_full_days": sum(r["precipitation_mm_day"] is not None for r in imerg_rows),
              "chirps_full_days": sum(r["missing_cells"] == 0 for r in chirps_rows),
              "status": "investigation_only_do_not_train",
              "notes": ["Source disagreement is not resolved by selecting whichever rainfall value is closer to IMERG or CHIRPS.",
                        "CHIRPS v3 rnl uses ERA5 to distribute pentad totals across UTC dates; daily station observation windows are not uniform.",
                        "IMERG half-hourly rates (mm/hour) are integrated as rate x 0.5 hours for each of 48 intervals.",
                        "NOAA's v07 mirror encodes 0 as missing and fill as well as a valid dry value. For 2024-08-08 only a lower bound is saved; its catchment average is withheld.",
                        "IMERG and CHIRPS sample days are not complete historical training series."]}
    (OUT / "source_comparison_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"power": power, "days": len(DAYS), "imerg_full_days": report["imerg_full_days"],
                      "chirps_full_days": report["chirps_full_days"]}, indent=2), flush=True)


if __name__ == "__main__":
    main()
