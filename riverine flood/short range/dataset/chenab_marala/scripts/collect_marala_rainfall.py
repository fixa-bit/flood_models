"""Download and area-weight precipitation for the checked Marala catchment.

Requires shapely and pyproj. Uses only the native NASA POWER meteorological
cells intersecting the saved catchment. Defaults preserve the requested period.
Run: python collect_marala_rainfall.py --start 2016-03-01 --end 2026-10-22
"""
import argparse
import csv
import hashlib
import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from pyproj import Transformer
from shapely import segmentize, transform
from shapely.geometry import box, mapping, shape
from shapely.ops import unary_union

MODEL = Path(__file__).resolve().parents[1]
RAW = MODEL / "raw/marala/rainfall/nasa_power"
OUTPUT = MODEL / "processed/marala/rainfall"
BOUNDARY = MODEL / "processed/marala/catchment/marala_upstream_catchment.geojson"
LAEA = "+proj=laea +lat_0=33 +lon_0=76 +datum=WGS84 +units=m +no_defs"
PROJECT = Transformer.from_crs(4326, LAEA, always_xy=True)
UNPROJECT = Transformer.from_crs(LAEA, 4326, always_xy=True)
PKT = timezone(timedelta(hours=5))


def project(geometry):
    # Densify geographic edges before projection so constant-latitude cell
    # boundaries retain their shape. Intersection areas share one equal-area CRS.
    return transform(segmentize(geometry, .005), PROJECT.transform, interleaved=False)


def select_cells(basin):
    if not basin.is_valid or basin.is_empty:
        raise ValueError("Catchment must be valid and nonempty; no repair applied")
    basin_projected = project(basin)
    xmin, ymin, xmax, ymax = basin.bounds
    cells = []
    for j in range(math.floor(ymin / .5) - 1, math.ceil(ymax / .5) + 2):
        for i in range(math.floor(xmin / .625) - 1, math.ceil(xmax / .625) + 2):
            lon, lat = i * .625, j * .5
            footprint = box(lon - .3125, lat - .25, lon + .3125, lat + .25)
            if not basin.intersection(footprint).area:
                continue
            overlap = basin_projected.intersection(project(footprint))
            if overlap.area <= 0:
                continue
            cells.append({"cell_id": f"lat_{lat:g}_lon_{lon:g}", "latitude": lat, "longitude": lon,
                          "catchment_overlap_km2": overlap.area / 1e6,
                          "area_weight": overlap.area / basin_projected.area,
                          "footprint": footprint, "overlap_projected": overlap})
    covered = unary_union([c["overlap_projected"] for c in cells])
    missing_fraction = basin_projected.difference(covered).area / basin_projected.area
    weight_sum = math.fsum(c["area_weight"] for c in cells)
    if missing_fraction > 1e-9 or abs(weight_sum - 1) > 1e-9:
        raise ValueError(f"Incomplete/overlapping grid coverage: gap={missing_fraction}, weight sum={weight_sum}")
    return cells, basin_projected.area / 1e6, missing_fraction


def aggregate_day(cells, values):
    available = [c for c in cells if values.get(c["cell_id"]) is not None]
    fraction = math.fsum(c["area_weight"] for c in available)
    # Full-area mean is undefined if even one required cell is missing.
    mean = math.fsum(c["area_weight"] * values[c["cell_id"]] for c in cells) if len(available) == len(cells) else None
    return mean, fraction, len(available)


def write_csv(name, rows):
    with (OUTPUT / name).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def fetch_cell(cell, start, end):
    params = {"parameters": "PRECTOTCORR", "community": "AG", "longitude": f"{cell['longitude']:g}",
              "latitude": f"{cell['latitude']:g}", "start": start.strftime("%Y%m%d"),
              "end": end.strftime("%Y%m%d"), "format": "JSON", "time-standard": "UTC"}
    url = "https://power.larc.nasa.gov/api/temporal/daily/point?" + urllib.parse.urlencode(params)
    path = RAW / "cells" / f"{cell['cell_id']}.json"
    receipt_path = path.with_suffix(".receipt.json")
    if path.exists():
        body = path.read_bytes()
        if not receipt_path.exists():
            raise ValueError(f"Cached source has no receipt: {path}")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["sha256"] != hashlib.sha256(body).hexdigest() or receipt["source_url"] != url:
            raise ValueError(f"Cached source hash/request differs: {path}; inspect before refreshing")
    else:
        for attempt in range(3):
            try:
                with urllib.request.urlopen(url, timeout=55) as response:
                    body = response.read()
                break
            except (urllib.error.URLError, TimeoutError):
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        receipt = {"source_url": url, "downloaded_utc": datetime.now(timezone.utc).isoformat(),
                   "downloaded_pakistan": datetime.now(PKT).isoformat(),
                   "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    data = json.loads(body)
    header = data["header"]
    if header["time_standard"] != "UTC" or data["parameters"]["PRECTOTCORR"]["units"] != "mm/day":
        raise ValueError("Unexpected time standard or precipitation units")
    if header["start"] != start.strftime("%Y%m%d") or header["end"] != end.strftime("%Y%m%d"):
        raise ValueError("Returned period differs from requested history")
    lon, lat, elevation = data["geometry"]["coordinates"]
    if abs(lon - cell["longitude"]) > 1e-6 or abs(lat - cell["latitude"]) > 1e-6:
        raise ValueError("Returned point differs from requested native-grid center")
    receipt.update(raw_file=path.relative_to(MODEL).as_posix(), cell_id=cell["cell_id"],
                   header=header, parameters=data["parameters"], last_checked_utc=datetime.now(timezone.utc).isoformat())
    receipt.setdefault("downloaded_pakistan", datetime.fromisoformat(receipt["downloaded_utc"]).astimezone(PKT).isoformat())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(body)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return cell, data, receipt, elevation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", type=date.fromisoformat, default=date(2016, 3, 1))
    parser.add_argument("--end", type=date.fromisoformat, default=date(2026, 10, 22))
    args = parser.parse_args()
    if args.start > args.end:
        raise ValueError("Start must precede end")
    boundary_bytes = BOUNDARY.read_bytes()
    boundary_data = json.loads(boundary_bytes)
    if len(boundary_data["features"]) != 1:
        raise ValueError("Expected exactly one Marala catchment feature")
    verification = json.loads(BOUNDARY.with_name("marala_catchment_verification.json").read_text())
    if not all(verification["checks"].values()):
        raise ValueError("Catchment verification has failed checks")
    source_boundary = verification["source_receipts"][0]
    source_bytes = (MODEL / source_boundary["raw_file"]).read_bytes()
    if hashlib.sha256(source_bytes).hexdigest() != source_boundary["sha256"]:
        raise ValueError("Catchment verification source checksum mismatch")
    if boundary_data["features"][0]["geometry"] != json.loads(source_bytes)["features"][0]["geometry"]:
        raise ValueError("Catchment differs from its verified source geometry")
    basin = shape(boundary_data["features"][0]["geometry"])
    cells, catchment_area, uncovered_fraction = select_cells(basin)
    RAW.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    weights = [{k: v for k, v in c.items() if k not in ("footprint", "overlap_projected")} for c in cells]
    write_csv("marala_rainfall_grid_cells.csv", weights)
    geometries = [{"type": "Feature", "geometry": mapping(transform(c["overlap_projected"], UNPROJECT.transform, interleaved=False)),
                   "properties": weights[i]} for i, c in enumerate(cells)]
    (OUTPUT / "marala_rainfall_catchment_cells.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": geometries}) + "\n", encoding="utf-8")
    dates = []
    day = args.start
    while day <= args.end:
        dates.append(day)
        day += timedelta(days=1)
    by_day = {str(day): {} for day in dates}
    grid_rows, receipts, failures = [], [], []
    with ThreadPoolExecutor(max_workers=3) as executor:
        futures = {executor.submit(fetch_cell, cell, args.start, args.end): cell for cell in cells}
        for future in as_completed(futures):
            try:
                cell, data, receipt, _ = future.result()
                receipts.append(receipt)
                values = data["properties"]["parameter"]["PRECTOTCORR"]
                for day in dates:
                    value = values.get(day.strftime("%Y%m%d"))
                    if value == data["header"]["fill_value"] or value is None:
                        value = None
                    elif not math.isfinite(value) or value < 0:
                        raise ValueError(f"Invalid precipitation value on {day}")
                    by_day[str(day)][cell["cell_id"]] = value
                    grid_rows.append({"date": str(day), "cell_id": cell["cell_id"],
                                      "precipitation_mm_day": value if value is not None else "",
                                      "quality_flag": "missing_in_source" if value is None else "",
                                      "day_time_standard": "UTC", "source": "NASA POWER", "parameter": "PRECTOTCORR",
                                      "source_url": receipt["source_url"], "source_file": receipt["raw_file"]})
                print(f"Collected {cell['cell_id']} ({len(receipts)}/{len(cells)})", flush=True)
            except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
                failures.append({"cell_id": futures[future]["cell_id"], "error": str(exc)})
    if failures:
        (OUTPUT / "marala_rainfall_download_failures.json").write_text(json.dumps(failures, indent=2), encoding="utf-8")
        raise RuntimeError(f"{len(failures)} cells could not be collected; daily catchment output not published")
    grid_rows.sort(key=lambda r: (r["date"], r["cell_id"]))
    write_csv("marala_catchment_grid_daily_precipitation.csv", grid_rows)
    daily = []
    for day in dates:
        mean, fraction, valid = aggregate_day(cells, by_day[str(day)])
        start = datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        daily.append({"date": str(day), "precipitation_mm_day": "" if mean is None else f"{mean:.6f}",
                      "period_start_utc": start.isoformat(), "period_end_utc_exclusive": end.isoformat(),
                      "period_start_pakistan": start.astimezone(PKT).isoformat(), "period_end_pakistan_exclusive": end.astimezone(PKT).isoformat(),
                      "valid_grid_cells": valid, "required_grid_cells": len(cells), "valid_area_fraction": f"{fraction:.12f}",
                      "quality_flag": "missing_grid_precipitation" if mean is None else "",
                      "source": "NASA POWER", "parameter": "PRECTOTCORR", "method": "catchment_intersection_area_weighted",
                      "source_manifest": "raw/marala/rainfall/nasa_power/source_receipt.json",
                      "catchment_file": BOUNDARY.relative_to(MODEL).as_posix()})
    write_csv("marala_catchment_daily_precipitation.csv", daily)
    valid_dates = [r["date"] for r in daily if r["precipitation_mm_day"] != ""]
    report = {"built_utc": datetime.now(timezone.utc).isoformat(), "requested_start": str(args.start), "requested_end": str(args.end),
              "catchment_file": BOUNDARY.relative_to(MODEL).as_posix(), "catchment_sha256": hashlib.sha256(boundary_bytes).hexdigest(),
              "boundary_status": verification["verification_status"], "agency_certified": False,
              "catchment_area_km2_equal_area": catchment_area, "grid_cells": len(cells),
              "spatial_coverage_fraction": 1 - uncovered_fraction, "weight_sum": math.fsum(c["area_weight"] for c in cells),
              "daily_rows": len(daily), "valid_daily_rows": len(valid_dates), "first_valid_date": min(valid_dates) if valid_dates else None,
              "last_valid_date": max(valid_dates) if valid_dates else None,
              "dates_with_missing_precipitation": [r["date"] for r in daily if r["precipitation_mm_day"] == ""],
              "grid_daily_rows": len(grid_rows), "missing_grid_values": sum(r["precipitation_mm_day"] == "" for r in grid_rows),
              "source_names_as_returned": sorted({s for r in receipts for s in r["header"]["sources"]}),
              "source_transition": "POWER may append GEOS-IT recent estimates to MERRA2. Per-date source transition is not exposed in these responses; preserve the source headers and retrieval date.",
              "area_method": "Densify WGS84 edges to at most 0.005 degrees, project boundary and native cell footprints into WGS84 Lambert azimuthal equal-area centered at 33 N, 76 E, and intersect. Weight = intersection area / full catchment area.",
              "area_crs": LAEA, "missing_value_policy": "Full-catchment daily mean is blank if any required grid value is missing. No interpolation or renormalization over available cells.",
              "time_standard": "UTC; each period is [00:00, next 00:00), equivalent to [05:00, next 05:00) Pakistan time.",
              "forecast_use": "Use only completed periods available by issue time. Retrospective reanalysis is not an archived weather forecast or proof of historical operational availability. Do not use a full day's value at 06:00 Pakistan on that same date.",
              "receipts": sorted(receipts, key=lambda r: r["cell_id"]), "failures": failures}
    for path in (OUTPUT / "marala_rainfall_collection_report.json", RAW / "source_receipt.json"):
        path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"Saved {len(daily)} catchment days; {len(valid_dates)} complete; {len(cells)} cells; coverage {100*(1-uncovered_fraction):.9f}%.")


if __name__ == "__main__":
    main()
