"""Collect the Marala catchment's CHIRPS v3 daily rainfall, 1990 onward.

Historical Final RNL is read from a public, 0.1-mm-quantized Zarr copy of the
CHC GeoTIFF release. Original CHC GeoTIFF samples verify the conversion.
Newer Final RNL and Preliminary SAT dates are clipped from CHC directly.
Existing NASA POWER files and comparison results are never changed.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import math
import re
import time
import urllib.request
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import rasterio
import zstandard
from rasterio.windows import Window, from_bounds
from shapely.geometry import box, shape

from audit_marala_precipitation_sources import build_weights

MODEL = Path(__file__).resolve().parents[1]
RAW = MODEL / "raw/marala/rainfall/chirps_v3"
OUT = MODEL / "processed/marala/rainfall/chirps_v3_primary"
BOUNDARY = MODEL / "processed/marala/catchment/marala_upstream_catchment.geojson"
ZARR_URL = "https://huggingface.co/datasets/aaguilar90/chirps-v3-daily-rnl/resolve/main/chirps-v3-daily-rnl.zarr"
CHC_BASE = "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily"
ZARR_RAW = RAW / "rnl/historical_1990_2026/compact_copy_zarr"
FINAL_CLIPS = RAW / "rnl/historical_1990_2026/official_final_clips"
PRELIM_CLIPS = RAW / "sat/preliminary_2026/official_clips"
START = date(1990, 1, 1)
ZARR_ORIGIN = date(1981, 1, 1)
ZARR_END = date(2026, 8, 31)
MAX_WORKERS = 6


def sha(body: bytes) -> str:
    return hashlib.sha256(body).hexdigest()


def saved_get(url: str, path: Path) -> tuple[bytes, dict]:
    """Keep first response bytes and a checksum; repeat runs never overwrite them."""
    receipt_path = path.with_name(path.name + ".receipt.json")
    if path.exists():
        if not receipt_path.exists():
            raise ValueError(f"Source without receipt: {path}")
        body = path.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["sha256"] != sha(body) or receipt["source_url"] != url:
            raise ValueError(f"Source bytes or URL changed: {path}")
        return body, receipt
    if receipt_path.exists():
        raise ValueError(f"Receipt without source: {receipt_path}")
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "Marala-CHIRPS-collector/1.0"}), timeout=120) as response:
                body = response.read()
            if not body:
                raise ValueError("Empty HTTP response")
            break
        except Exception:
            if attempt == 3:
                raise
            time.sleep(2 * (attempt + 1))
    receipt = {"source_url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
               "sha256": sha(body), "bytes": len(body), "raw_file": path.relative_to(MODEL).as_posix(),
               "representation": "Original downloaded Zarr metadata or compressed chunk"}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".part")
    temporary.write_bytes(body)
    temporary.replace(path)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return body, receipt


def source_index(subpath: str) -> tuple[list[date], dict]:
    url = f"{CHC_BASE}/{subpath}/"
    body, receipt = saved_get(url, RAW / "source_indexes_2026-10-26" / f"{subpath.replace('/', '_')}.html")
    prefix = "chirps-v3.0.rnl." if subpath.startswith("final") else "chirps-v3.0.prelim."
    dates = []
    for match in re.finditer(re.escape(prefix) + r"(\d{4})\.(\d{2})\.(\d{2})\.tif", body.decode("utf-8")):
        dates.append(date(*map(int, match.groups())))
    return sorted(set(dates)), receipt


def zarr_metadata() -> dict:
    metadata = {}
    for key in ("", "precip", "time", "lat", "lon"):
        path = (key + "/" if key else "") + "zarr.json"
        body, _ = saved_get(f"{ZARR_URL}/{path}", ZARR_RAW / path)
        metadata[key or "root"] = json.loads(body)
    precip = metadata["precip"]
    if (precip["shape"] != [16679, 2400, 7200]
            or precip["chunk_grid"]["configuration"]["chunk_shape"] != [128, 300, 300]
            or precip["attributes"]["scale_factor"] != 0.1
            or precip["fill_value"] != -9999):
        raise ValueError("Unexpected compact CHIRPS data schema")
    decoder = zstandard.ZstdDecompressor()
    coords = {}
    for key, dtype, expected in (("time", "<i4", 16679), ("lat", "<f8", 2400), ("lon", "<f8", 7200)):
        pieces = []
        count = metadata[key]["chunk_grid"]["configuration"]["chunk_shape"][0]
        for chunk in range(math.ceil(expected / count)):
            path = f"{key}/c/{chunk}"
            body, _ = saved_get(f"{ZARR_URL}/{path}", ZARR_RAW / path)
            pieces.append(np.frombuffer(decoder.decompress(body), dtype=dtype))
        # The compact store pads its final coordinate chunk to a full chunk.
        coords[key] = np.concatenate(pieces)[:expected]
        if len(coords[key]) != expected:
            raise ValueError(f"CHIRPS {key} coordinate count changed")
    expected_time = np.arange(366, 366 + 16679, dtype=np.int32)
    if not np.array_equal(coords["time"], expected_time):
        raise ValueError("CHIRPS Zarr time coordinate has gaps or different origin")
    if not np.allclose(coords["lat"], 59.975 - 0.05 * np.arange(2400), atol=1e-6):
        raise ValueError("CHIRPS latitude coordinate differs from official raster")
    if not np.allclose(coords["lon"], -179.975 + 0.05 * np.arange(7200), atol=1e-6):
        raise ValueError("CHIRPS longitude coordinate differs from official raster")
    return metadata


def catchment_weights(basin):
    west, south, east, north = basin.bounds
    row0 = max(0, math.floor((60 - north) / .05))
    row1 = min(2399, math.floor((60 - south) / .05))
    col0 = max(0, math.floor((west + 180) / .05))
    col1 = min(7199, math.floor((east + 180) / .05))
    pixels = []
    for row in range(row0, row1 + 1):
        for col in range(col0, col1 + 1):
            pixels.append((row, col, box(-180 + col * .05, 60 - (row + 1) * .05,
                                         -180 + (col + 1) * .05, 60 - row * .05)))
    weights = build_weights(basin, pixels)
    rows = [{"global_row": row, "global_col": col,
             "latitude_center": f"{59.975 - row*.05:.3f}",
             "longitude_center": f"{-179.975 + col*.05:.3f}",
             "area_weight": f"{weight:.12f}", "time_grid": "CHIRPS v3 0.05-degree"}
            for row, col, weight in weights]
    write_csv(OUT / "chirps_v3_marala_cell_weights.csv", rows)
    if not math.isclose(math.fsum(w for _, _, w in weights), 1, abs_tol=2e-5):
        raise ValueError("CHIRPS catchment grid fails full area coverage")
    return weights


def one_row(day: date, mean, covered, missing, status, source, quantized) -> dict:
    return {"date": day.isoformat(), "precipitation_mm": "" if mean is None else f"{mean:.6f}",
            "unit": "mm per UTC-labelled day", "valid_area_fraction": f"{covered:.8f}",
            "missing_catchment_cells": missing, "source_product": "CHIRPS v3 daily",
            "edition": status, "daily_allocation": "ERA5" if status.startswith("final") else "IMERG Late V07",
            "source_representation": "0.1-mm quantized compact copy" if quantized else "official CHC GeoTIFF clip",
            "source_url": source,
            "period_start_utc": f"{day}T00:00:00Z", "period_end_utc_exclusive": f"{day+timedelta(days=1)}T00:00:00Z",
            "quality_flag": "complete" if mean is not None else "missing_catchment_cell",
            "training_status": "candidate; review daily timing and publication latency" if status.startswith("final") else "preliminary; separate from Final RNL"}


def historical_rows(weights, metadata):
    first = (START - ZARR_ORIGIN).days // 128
    last = (ZARR_END - ZARR_ORIGIN).days // 128
    groups = {}
    for row, col, weight in weights:
        groups.setdefault(col // 300, []).append((row % 300, col % 300, weight))
    if set(groups) != {16, 17} or {row // 300 for row, _, _ in weights} != {1}:
        raise ValueError("CHIRPS catchment crosses unexpected compact grid chunks")
    base = metadata["root"]["attributes"].get("time_coverage_end")
    if base != "2026-08-31":
        raise ValueError("Compact copy's time coverage changed; inspect before continuing")

    def process(chunk_id):
        part_means = []
        part_missing = []
        receipts = []
        # Stored chunks are always full-sized, including the padded last one.
        count = 128
        for col_chunk in (16, 17):
            path = f"precip/c/{chunk_id}/1/{col_chunk}"
            body, receipt = saved_get(f"{ZARR_URL}/{path}", ZARR_RAW / path)
            raw = zstandard.ZstdDecompressor().decompress(body)
            arr = np.frombuffer(raw, dtype="<i2")
            if arr.size != count * 300 * 300:
                raise ValueError(f"Unexpected CHIRPS chunk shape: {path}")
            arr = arr.reshape(count, 300, 300)
            cells = groups[col_chunk]
            vals = arr[:, [r for r, _, _ in cells], [c for _, c, _ in cells]]
            bad = (vals < 0).any(axis=1)
            part_missing.append(bad)
            part_means.append(vals.astype(np.float64) @ np.array([w for _, _, w in cells]) * .1)
            receipts.append(receipt)
        means = part_means[0] + part_means[1]
        missing = part_missing[0] | part_missing[1]
        result = []
        for offset in range(count):
            day = ZARR_ORIGIN + timedelta(days=chunk_id * 128 + offset)
            if START <= day <= ZARR_END:
                result.append(one_row(day, None if missing[offset] else float(means[offset]),
                                      0 if missing[offset] else 1, int(missing[offset]), "final_rnl",
                                      ZARR_URL + "/precip/c/", True))
        return chunk_id, result, receipts

    results = {}
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        futures = {pool.submit(process, chunk): chunk for chunk in range(first, last + 1)}
        for n, future in enumerate(as_completed(futures), 1):
            chunk, rows, _ = future.result()
            results[chunk] = rows
            if n % 10 == 0 or n == len(futures):
                print(f"Historical CHIRPS chunks: {n}/{len(futures)}", flush=True)
    rows = [row for chunk in sorted(results) for row in results[chunk]]
    if len(rows) != (ZARR_END - START).days + 1:
        raise ValueError("Historical CHIRPS dates are incomplete")
    return rows


def clip_official(day: date, edition: str, basin, weights):
    if edition == "final_rnl":
        sub = f"final/rnl/{day.year}/chirps-v3.0.rnl.{day:%Y.%m.%d}.tif"
        folder = FINAL_CLIPS
    else:
        sub = f"prelim/sat/{day.year}/chirps-v3.0.prelim.{day:%Y.%m.%d}.tif"
        folder = PRELIM_CLIPS
    url = f"{CHC_BASE}/{sub}"
    path = folder / f"{day}.npy"
    receipt_path = path.with_name(path.name + ".receipt.json")
    if path.exists():
        data = path.read_bytes()
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if receipt["sha256"] != sha(data) or receipt["source_url"] != url:
            raise ValueError(f"CHC clip changed: {path}")
        arr = np.load(io.BytesIO(data))
        row0, col0 = receipt["global_window_row_col"]
    else:
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as response:
            source_headers = {"content_length": response.headers.get("Content-Length"),
                              "last_modified": response.headers.get("Last-Modified"),
                              "etag": response.headers.get("ETag")}
        for attempt in range(3):
            try:
                with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", GDAL_HTTP_MAX_RETRY="2"):
                    with rasterio.open("/vsicurl/" + url) as raster:
                        if raster.count != 1 or raster.crs.to_epsg() != 4326 or raster.width != 7200 or raster.height != 2400:
                            raise ValueError("Official CHIRPS raster grid changed")
                        w = from_bounds(*basin.bounds, transform=raster.transform)
                        row0, col0 = max(0, math.floor(w.row_off)), max(0, math.floor(w.col_off))
                        row1, col1 = min(2400, math.ceil(w.row_off + w.height)), min(7200, math.ceil(w.col_off + w.width))
                        arr = raster.read(1, window=Window(col0, row0, col1-col0, row1-row0))
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2 * (attempt + 1))
        out = io.BytesIO()
        np.save(out, arr, allow_pickle=False)
        data = out.getvalue()
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name + ".part")
        temp.write_bytes(data)
        temp.replace(path)
        receipt = {"source_url": url, "retrieved_utc": datetime.now(timezone.utc).isoformat(),
                   "sha256": sha(data), "bytes": len(data), "raw_file": path.relative_to(MODEL).as_posix(),
                   "representation": "Exact float32 CHC raster window, not full original GeoTIFF",
                   "global_window_row_col": [row0, col0], "source_headers": source_headers}
        receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    values = np.array([arr[row-row0, col-col0] for row, col, _ in weights], dtype=np.float64)
    bad = ~np.isfinite(values) | (values < 0)
    covered = math.fsum(weight for is_bad, (_, _, weight) in zip(bad, weights) if not is_bad)
    mean = None if bad.any() else float(values @ np.array([w for _, _, w in weights]))
    return one_row(day, mean, covered, int(bad.sum()), edition, url, False)


def write_csv(path: Path, rows: list[dict]):
    if not rows:
        raise ValueError(f"No rows to save: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    boundary_sha = sha(BOUNDARY.read_bytes())
    basin = shape(json.loads(BOUNDARY.read_text(encoding="utf-8"))["features"][0]["geometry"])
    if not basin.is_valid:
        raise ValueError("Marala catchment is invalid")
    final_dates, final_index_receipt = source_index("final/rnl/2026")
    prelim_dates, prelim_index_receipt = source_index("prelim/sat/2026")
    if not final_dates or not prelim_dates:
        raise ValueError("CHC 2026 archive listing returned no dates")
    final_end = max(final_dates)
    if final_end < ZARR_END or final_end >= date.today():
        raise ValueError("CHC Final listing coverage is unexpected")
    extra_final = [ZARR_END + timedelta(days=n) for n in range(1, (final_end-ZARR_END).days + 1)]
    if not set(extra_final).issubset(final_dates):
        raise ValueError("CHC Final dates have a gap after compact copy")
    extra_prelim = [d for d in prelim_dates if d > final_end and d < date.today()]
    if extra_prelim and extra_prelim != [final_end + timedelta(days=n) for n in range(1, len(extra_prelim)+1)]:
        raise ValueError("CHC Preliminary dates after Final have a gap")
    print(f"CHC archive: Final through {final_end}; separate Preliminary through {max(extra_prelim) if extra_prelim else 'none'}", flush=True)
    metadata = zarr_metadata()
    weights = catchment_weights(basin)
    print(f"Catchment cells: {len(weights)}; area weights sum to {math.fsum(w for _, _, w in weights):.9f}", flush=True)
    historical = historical_rows(weights, metadata)
    official = []
    tasks = [(day, "final_rnl") for day in extra_final] + [(day, "preliminary_sat") for day in extra_prelim]
    with ThreadPoolExecutor(max_workers=4) as pool:
        future_map = {pool.submit(clip_official, day, edition, basin, weights): (day, edition) for day, edition in tasks}
        for n, future in enumerate(as_completed(future_map), 1):
            official.append(future.result())
            if n % 10 == 0 or n == len(tasks):
                print(f"Official CHC recent days: {n}/{len(tasks)}", flush=True)
    final_rows = sorted(historical + [row for row in official if row["edition"] == "final_rnl"], key=lambda row: row["date"])
    prelim_rows = sorted([row for row in official if row["edition"] == "preliminary_sat"], key=lambda row: row["date"])
    if len(final_rows) != (final_end - START).days + 1 or len({row["date"] for row in final_rows}) != len(final_rows):
        raise ValueError("Final CHIRPS series has missing or duplicate dates")
    write_csv(OUT / "marala_chirps_v3_final_rnl_daily_1990_2026.csv", final_rows)
    if prelim_rows:
        write_csv(OUT / "marala_chirps_v3_preliminary_sat_2026.csv", prelim_rows)
    # Check compact-copy precision against original CHC float32 GeoTIFFs saved
    # during the prior ten-day source audit. This check does not use NASA POWER.
    sample_file = MODEL / "processed/marala/rainfall/source_comparison_2026-10-26/chirps_v3_daily_catchment_sample.csv"
    samples = []
    if sample_file.exists():
        prior = {row["date"]: row for row in csv.DictReader(sample_file.open(encoding="utf-8", newline=""))}
        current = {row["date"]: row for row in final_rows}
        for day, source in sorted(prior.items()):
            if day not in current:
                continue
            original = float(source["precipitation_mm_day"])
            compact = float(current[day]["precipitation_mm"])
            difference = compact - original
            samples.append({"date": day, "original_chc_geotiff_mm": f"{original:.6f}",
                            "compact_copy_mm": f"{compact:.6f}", "difference_mm": f"{difference:.6f}",
                            "within_quantization_limit": abs(difference) <= 0.051})
        if samples:
            write_csv(OUT / "compact_copy_official_geotiff_check.csv", samples)
        if any(not row["within_quantization_limit"] for row in samples):
            raise ValueError("Compact copy differs from official CHC sample beyond 0.05 mm")
    yearly = {}
    for year in range(1990, final_end.year + 1):
        subset = [row for row in final_rows if row["date"].startswith(str(year))]
        yearly[str(year)] = {"dates": len(subset), "complete_values": sum(row["precipitation_mm"] != "" for row in subset),
                             "missing_values": sum(row["precipitation_mm"] == "" for row in subset)}
    report = {"built_utc": datetime.now(timezone.utc).isoformat(), "start": str(START),
              "final_end": str(final_end), "preliminary_end": str(max(extra_prelim)) if extra_prelim else None,
              "boundary_sha256": boundary_sha, "catchment_cells": len(weights),
              "area_weight_sum": math.fsum(w for _, _, w in weights),
              "final_daily_rows": len(final_rows), "final_complete_days": sum(r["precipitation_mm"] != "" for r in final_rows),
              "preliminary_daily_rows": len(prelim_rows), "preliminary_complete_days": sum(r["precipitation_mm"] != "" for r in prelim_rows),
              "compact_copy_until": str(ZARR_END), "compact_copy_quantization_mm": 0.1,
              "original_chc_samples_checked": len(samples),
              "maximum_sample_absolute_difference_mm": max((abs(float(r["difference_mm"])) for r in samples), default=None),
              "yearly": yearly, "provider_final_index": final_index_receipt,
              "provider_preliminary_index": prelim_index_receipt,
              "source_notes": ["Historical source is a third-party Zarr conversion of official CHIRPS v3 Final RNL; original CHC GeoTIFF samples check its 0.1-mm quantization.",
                               "Final RNL daily allocation uses ERA5. Preliminary SAT daily allocation uses IMERG and is stored separately.",
                               "UTC day labels do not prove uniform observation windows for contributing station records.",
                               "Daily rainfall histories are observations/reanalysis estimates, not future rainfall forecasts."]}
    (OUT / "collection_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: report[key] for key in ("final_daily_rows", "final_complete_days", "preliminary_daily_rows", "preliminary_complete_days", "original_chc_samples_checked", "maximum_sample_absolute_difference_mm")}, indent=2), flush=True)


if __name__ == "__main__":
    main()
