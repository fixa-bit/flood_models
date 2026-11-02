"""Marala catchment daily precipitation, 1980-01-01 through 2024-12-31.

Requires earthengine-api only. See README.md beside this file for execution,
scientific qualifications, UTC day conventions and local gauge-day alignment.
All paths default to this script's directory, independent of working directory.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import statistics
import subprocess
import sys
import time
from datetime import date, timedelta
from urllib.request import urlopen

START, END = date(1980, 1, 1), date(2025, 1, 1)  # exclusive end
PRODUCTS = {
    "era5land_mm": ("ECMWF/ERA5_LAND/DAILY_AGGR", "total_precipitation_sum", "1980-01-01", 1000),
    "chirps_mm": ("UCSB-CHG/CHIRPS/DAILY", "precipitation", "1981-01-01", 1),
    "persiann_mm": ("NOAA/PERSIANN-CDR", "precipitation", "1983-01-01", 1),
    "imerg_mm": ("NASA/GPM_L3/IMERG_V07", "precipitation", "2000-06-01", .5),
}
FIELDS = ["date", "value_mm", "raw_min_mm", "negative_area_fraction", "coverage_fraction", "n_images"]
WORKSPACE = next(parent for parent in Path(__file__).resolve().parents if (parent / "data_portal/build_dashboard.py").is_file())
DEFAULT_CATCHMENT = (WORKSPACE / "riverine flood/short range/dataset/chenab_marala/processed/marala/catchment/marala_upstream_catchment.geojson")
ee = None  # Imported only for extraction; merge/QA works without credentials/API.


def save_json(path, data):
    path.write_text(json.dumps(data, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def days(start=START, end=END):
    while start < end:
        yield start
        start += timedelta(days=1)


def upstream_ids(rows, outlet):
    """Reverse NEXT_DOWN adjacency, including the outlet's entire subbasin."""
    reverse = {}
    for basin, downstream in rows:
        reverse.setdefault(int(downstream), []).append(int(basin))
    seen, stack = set(), [int(outlet)]
    while stack:
        basin = stack.pop()
        if basin not in seen:
            seen.add(basin)
            stack.extend(reverse.get(basin, []))
    return sorted(seen)


def read_catchment(path):
    """Load the existing polygon without silently selecting or changing features."""
    body = path.read_bytes()
    document = json.loads(body)
    if document.get("type") == "FeatureCollection":
        if len(document.get("features", [])) != 1:
            raise ValueError("Catchment GeoJSON must contain exactly one polygon feature")
        feature = document["features"][0]
    elif document.get("type") == "Feature":
        feature = document
    else:
        feature = {"type": "Feature", "properties": {}, "geometry": document}
    if feature["geometry"]["type"] not in ("Polygon", "MultiPolygon"):
        raise ValueError("Catchment must be a Polygon or MultiPolygon")
    return feature, hashlib.sha256(body).hexdigest()


def existing_catchment(args):
    feature, digest = read_catchment(args.catchment)
    geometry = ee.Geometry(feature["geometry"])
    area = geometry.area(maxError=10).divide(1e6).getInfo()
    report_path = args.catchment.with_name("marala_catchment_verification.json")
    verification = json.loads(report_path.read_text(encoding="utf-8")) if report_path.exists() else None
    metadata = {
        "method": "reuse_existing_catchment_without_redelineation",
        "source_file": str(args.catchment.resolve()), "source_sha256": digest,
        "source_properties": feature.get("properties", {}),
        "catchment_area_km2": area,
        "saved_verification_report": verification,
        "qualification": "Existing MERIT-derived research polygon; original service's exact snapped cell is not exposed. Saved checks are provenance, not a new independent validation.",
    }
    print(f"Using existing catchment: {args.catchment}")
    print(f"Catchment area (Earth Engine): {area:,.3f} km2")
    if verification:
        print(f"Saved geodesic area: {verification.get('area_km2_geodesic')} km2")
        print(f"Saved geometry/source checks: {verification.get('checks')}")
    save_json(args.output / "catchment_metadata.json", metadata)
    # Preserve the source coordinates and properties in the local GeoJSON export.
    save_json(args.output / "marala_upstream_catchment.geojson", {
        "type": "FeatureCollection", "features": [feature]})
    return geometry, metadata


def delineate(args):
    point = ee.Geometry.Point([args.lon, args.lat])
    merit = ee.Image("MERIT/Hydro/v1_0_1")
    projection = merit.select("upa").projection()
    # River cells are defined explicitly by upstream drainage area, not every
    # land cell with a flow direction. Select nearest qualifying cell CENTER.
    river = merit.select("upa").gte(args.river_threshold_km2)
    samples = merit.select("upa").updateMask(river).sample(
        region=point.buffer(args.snap_radius_m), projection=projection,
        geometries=True, tileScale=4)
    samples = samples.map(lambda f: f.set("distance_m", f.geometry().distance(point, 1)))
    if not samples.size().getInfo():
        raise ValueError("No river cell found; increase --snap-radius-m or review pour point")
    snapped = ee.Feature(samples.sort("distance_m").first())
    snap_info = snapped.getInfo()
    snap_point = snapped.geometry()
    basins = ee.FeatureCollection("WWF/HydroSHEDS/v1/Basins/hybas_12")
    hits = basins.filterBounds(snap_point).sort("HYBAS_ID")
    if not hits.size().getInfo():
        raise ValueError("Snapped point does not intersect a HydroBASINS polygon")
    outlet = ee.Feature(hits.first())
    outlet_info = outlet.toDictionary(["HYBAS_ID", "MAIN_BAS", "SUB_AREA", "UP_AREA"]).getInfo()
    # Retrieve only topology for the entire main basin: no arbitrary bounding
    # box that could truncate headwaters. Geometry stays on Earth Engine.
    network = basins.filter(ee.Filter.eq("MAIN_BAS", outlet_info["MAIN_BAS"]))
    rows = network.reduceColumns(ee.Reducer.toList(2), ["HYBAS_ID", "NEXT_DOWN"]).get("list").getInfo()
    ids = upstream_ids(rows, outlet_info["HYBAS_ID"])
    selected = network.filter(ee.Filter.inList("HYBAS_ID", ids))
    polygon = selected.geometry(maxError=10).dissolve(maxError=10)
    area = polygon.area(maxError=10).divide(1e6).getInfo()
    metadata = {
        "input_lon_lat": [args.lon, args.lat], "snapped_lon_lat": snap_info["geometry"]["coordinates"],
        "snap_distance_m": snap_info["properties"]["distance_m"],
        "merit_upstream_area_km2": snap_info["properties"]["upa"],
        "river_threshold_km2": args.river_threshold_km2,
        "catchment_area_km2": area, "expected_area_km2": 26000,
        "relative_difference_from_26000": area / 26000 - 1,
        "hydrobasins_outlet": outlet_info, "subbasin_count": len(ids),
        "qualification": "Whole level-12 subbasins; outlet subbasin includes land downstream of the snapped cell. MERIT snap and HydroSHEDS boundaries can differ.",
    }
    print(json.dumps(metadata, indent=2), flush=True)
    save_json(args.output / "catchment_metadata.json", metadata)
    save_json(args.output / "marala_upstream_catchment.geojson", {
        "type": "FeatureCollection", "features": [{"type": "Feature", "properties": metadata,
                                                     "geometry": polygon.getInfo()}]})
    save_json(args.output / "marala_snapped_outlet.geojson", {
        "type": "FeatureCollection", "features": [snap_info]})
    # Never silently substitute another outlet or reshape a basin to hit 26k.
    if abs(area / 26000 - 1) > .20 and not args.allow_area_mismatch:
        raise ValueError("Area differs from 26,000 km2 by >20%; inspect GeoJSON and metadata. "
                         "Use --allow-area-mismatch only after reviewing the outlet.")
    if abs(area / 26000 - 1) > .10:
        print("AREA WARNING: >10% difference from 26,000 km2; review catchment metadata.")
    return polygon, metadata


def daily_features(key, start, end, geometry, projection, args):
    collection_id, band, _, factor = PRODUCTS[key]
    collection = ee.ImageCollection(collection_id).select(band)
    if key == "imerg_mm":
        # 'permanent' excludes provisional/near-real-time replacements.
        collection = collection.filter(ee.Filter.eq("status", "permanent"))
    collection = collection.filterDate(start.isoformat(), end.isoformat())
    grid = {"crs": projection["crs"], "crsTransform": projection["transform"]}
    # Exact native affine transform preserves pixel origin and resolution;
    # crsTransform and scale are mutually exclusive in reduceRegion.
    options = dict(geometry=geometry, maxPixels=10_000_000, tileScale=4, **grid)
    pixel_area = ee.Image.pixelArea().rename("area")
    total_grid_area = pixel_area.reduceRegion(ee.Reducer.sum(), **options).get("area")
    empty = ee.Image.constant(0).rename(band).updateMask(ee.Image.constant(0))

    def feature(day_text):
        day = ee.Date(day_text)
        subset = collection.filterDate(day, day.advance(1, "day"))
        n = subset.size()
        if key == "imerg_mm":
            # mm/hour * 0.5 hour, summed over 48 intervals [00:00,24:00) UTC.
            # Per-pixel count==48 rejects partial days instead of treating missing
            # half-hours as dry. Also verify timestamp completeness client-side.
            summed = subset.sum().multiply(factor)
            raw = ee.Image(ee.Algorithms.If(n.eq(48), summed, empty))
            count = ee.Image(ee.Algorithms.If(n.gt(0), subset.count(), empty))
            raw = raw.updateMask(count.eq(48))
            timestamps = subset.aggregate_array("system:time_start").distinct().sort()
            expected = ee.List.sequence(0, 47).map(lambda i: day.millis().add(ee.Number(i).multiply(1800000)))
            time_ok = ee.Algorithms.IsEqual(timestamps, expected)
        else:
            raw = ee.Image(ee.Algorithms.If(n.eq(1), subset.first(), empty)).multiply(factor)
            time_ok = n.eq(1)
        raw = raw.rename("mm")
        minimum = raw.reduceRegion(ee.Reducer.min(), **options).get("mm")
        negative = raw.lt(0).rename("negative")

        def mean(image):
            # Default ee.Reducer.mean() weights polygon boundary pixels by
            # fractional intersection (quantized ~1/256), also respecting masks.
            # splitWeights adds physical pixel area: geographic pixels are not
            # equal-area. Effective weight = cell area * boundary fraction for
            # binary valid masks. No unweighted(), centroid-only selection or
            # bestEffort coarsening. This remains a mean reducer at native scale.
            result = image.addBands(pixel_area).reduceRegion(
                ee.Reducer.mean().splitWeights(), **options)
            return result.values().get(0)

        coverage = pixel_area.updateMask(raw.mask()).reduceRegion(
            ee.Reducer.sum(), **options).get("area")
        fraction = ee.Number(ee.Algorithms.If(coverage, coverage, 0)).divide(total_grid_area)
        # ERA5 GRIB packing can yield negative precipitation. Preserve raw min
        # and affected area; clip only ERA5 to zero. Other negatives fail QA.
        cleaned = raw.max(0) if key == "era5land_mm" else raw
        valid = fraction.gte(args.min_coverage)
        return ee.Feature(None, {
            "date": day.format("YYYY-MM-dd", "UTC"),
            "value_mm": ee.Algorithms.If(ee.Algorithms.If(time_ok, valid, False), mean(cleaned), None),
            "raw_min_mm": minimum, "negative_area_fraction": mean(negative),
            "coverage_fraction": fraction, "n_images": n,
        })

    return ee.FeatureCollection(ee.List([d.isoformat() for d in days(start, end)]).map(feature))


def download_chunk(key, start, end, geometry, projection, args):
    folder = args.output / "chunks" / key
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{start}_{end}.csv"
    # A matching run fingerprint is checked before any chunk is reused.
    if path.exists():
        return
    # Resume an adaptively split request without creating an overlapping parent.
    children = [p for p in folder.glob("*.csv")
                if start.isoformat() <= p.stem.split("_")[0] < end.isoformat()]
    if children and (end - start).days > 1:
        midpoint = start + timedelta(days=(end - start).days // 2)
        download_chunk(key, start, midpoint, geometry, projection, args)
        download_chunk(key, midpoint, end, geometry, projection, args)
        return
    error = None
    for attempt in range(3):
        try:
            table = daily_features(key, start, end, geometry, projection, args)
            url = table.getDownloadURL(filetype="CSV", selectors=FIELDS)
            with urlopen(url, timeout=300) as response:
                body = response.read()
            parsed = list(csv.DictReader(io.StringIO(body.decode("utf-8-sig"))))
            if sorted(r["date"] for r in parsed) != [d.isoformat() for d in days(start, end)]:
                raise ValueError("Downloaded dates do not match requested chunk")
            temporary = path.with_suffix(".tmp")
            temporary.write_bytes(body)
            temporary.replace(path)
            print(f"Saved {key}: {start} to {end} (exclusive)", flush=True)
            return
        except Exception as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** (attempt + 1))
    # A monthly request hitting computation limits is retried as smaller chunks.
    if (end - start).days > 1:
        midpoint = start + timedelta(days=(end - start).days // 2)
        download_chunk(key, start, midpoint, geometry, projection, args)
        download_chunk(key, midpoint, end, geometry, projection, args)
    else:
        raise RuntimeError(f"Failed {key} {start}: {error}") from error


def number(value):
    if value is None or str(value).strip().lower() in ("", "nan", "null", "none"):
        return math.nan
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"Nonfinite value: {value}")
    return result


def merge(args):
    merged = {d.isoformat(): {} for d in days()}
    report, annual, issues = {}, [], []
    for key, (_, _, available, _) in PRODUCTS.items():
        records = {}
        for path in sorted((args.output / "chunks" / key).glob("*.csv")):
            with path.open(newline="", encoding="utf-8-sig") as stream:
                for row in csv.DictReader(stream):
                    stamp = row["date"]
                    if stamp not in merged or stamp < available:
                        raise ValueError(f"Unexpected date in {path}: {stamp}")
                    if stamp in records:
                        raise ValueError(f"Overlapping chunks for {key} {stamp}; remove redundant parent/child chunks")
                    records[stamp] = row
        missing, negative_dates, negative_source = [], [], []
        values = []
        for stamp in merged:
            row = records.get(stamp, {})
            value = number(row.get("value_mm"))
            if row:
                coverage = number(row.get("coverage_fraction"))
                if not math.isfinite(coverage) or coverage < args.min_coverage:
                    value = math.nan
                expected_n = 48 if key == "imerg_mm" else 1
                if number(row.get("n_images")) != expected_n:
                    value = math.nan
                if number(row.get("negative_area_fraction")) > 0:
                    negative_source.append(stamp)
            if math.isfinite(value) and value < 0:
                negative_dates.append(stamp)
                value = math.nan  # No negative precipitation in final file.
            if stamp >= available and math.isnan(value):
                missing.append(stamp)
            if math.isfinite(value):
                values.append(value)
            merged[stamp][key] = value
        report[key] = {
            "units": "mm/day", "available_from_in_this_workflow": available,
            "valid_days": len(values), "expected_missing_before_start": sum(s < available for s in merged),
            "unexpected_missing_days": missing, "rejected_negative_days": negative_dates,
            "days_with_negative_source_pixels": negative_source,
            "negative_policy": "clip negative ERA5 pixels to zero before spatial mean; audit preserved" if key == "era5land_mm" else "reject negative daily means",
            "min": min(values) if values else None, "max": max(values) if values else None,
            "mean": statistics.mean(values) if values else None,
            "std": statistics.pstdev(values) if values else None,
        }
        print(key, json.dumps({k: v for k, v in report[key].items() if not isinstance(v, list)}))
        if missing or negative_dates or (negative_source and key != "era5land_mm"):
            issues.append(key)
        for year in range(1980, 2025):
            stamps = [s for s in merged if s.startswith(str(year))]
            observed = [merged[s][key] for s in stamps if math.isfinite(merged[s][key])]
            complete = len(observed) == len(stamps)
            item = {"year": year, "product": key, "valid_days": len(observed), "calendar_days": len(stamps),
                    "annual_total_mm": sum(observed) if complete else "NaN",
                    "observed_partial_total_mm": sum(observed) if observed else "NaN"}
            annual.append(item)
            print(f"  {year}: annual={item['annual_total_mm']} mm; days={len(observed)}/{len(stamps)}")
    with (args.output / "marala_daily_precipitation_1980_2024.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["date", *PRODUCTS])
        for stamp, row in merged.items():
            writer.writerow([stamp, *["NaN" if math.isnan(row[k]) else row[k] for k in PRODUCTS]])
    with (args.output / "annual_totals.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(annual[0]))
        writer.writeheader()
        writer.writerows(annual)
    save_json(args.output / "quality_report.json", {"day_definition": "00:00 to 24:00 UTC; Pakistan 05:00 to next-day 05:00",
                                                   "merged_csv_sha256": hashlib.sha256((args.output / "marala_daily_precipitation_1980_2024.csv").read_bytes()).hexdigest(),
                                                   "products": report, "qa_passed": not issues})
    if issues:
        raise ValueError(f"QA found missing data or negative precipitation: {issues}; see quality_report.json")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", default=os.environ.get("EE_PROJECT"))
    parser.add_argument("--authenticate", action="store_true", help="Explicit interactive Earth Engine login")
    parser.add_argument("--output", type=Path, default=Path(__file__).resolve().parent)
    parser.add_argument("--merge-only", action="store_true")
    parser.add_argument("--update-portal", action="store_true", help="Rebuild the local portal after extraction and QA succeed")
    parser.add_argument("--catchment", type=Path, default=DEFAULT_CATCHMENT,
                        help="Existing catchment GeoJSON; defaults to the project's verified Marala polygon")
    parser.add_argument("--redelineate", action="store_true",
                        help="Build a fresh HydroBASINS catchment instead of reusing --catchment")
    parser.add_argument("--lon", type=float, default=74.46)
    parser.add_argument("--lat", type=float, default=32.67)
    parser.add_argument("--snap-radius-m", type=float, default=3000)
    parser.add_argument("--river-threshold-km2", type=float, default=1000)
    parser.add_argument("--allow-area-mismatch", action="store_true")
    parser.add_argument("--min-coverage", type=float, default=.999)
    args = parser.parse_args()
    if not 0 < args.min_coverage <= 1:
        parser.error("--min-coverage must lie in (0, 1]")
    args.output.mkdir(parents=True, exist_ok=True)
    if args.merge_only:
        merge(args)
        return
    if not args.project:
        parser.error("Provide --project YOUR_EE_CLOUD_PROJECT or set EE_PROJECT")
    global ee
    try:
        import ee
    except ImportError:
        parser.error("Install dependency: python -m pip install earthengine-api")
    if args.authenticate:
        ee.Authenticate()
    ee.Initialize(project=args.project)
    geometry, catchment = delineate(args) if args.redelineate else existing_catchment(args)
    manifest = {"version": 1, "period": [START.isoformat(), END.isoformat()],
                "products": PRODUCTS, "min_coverage": args.min_coverage,
                "catchment": catchment, "projections": {}}
    for key, (collection, band, _, _) in PRODUCTS.items():
        images = ee.ImageCollection(collection).select(band)
        if key == "imerg_mm":
            images = images.filter(ee.Filter.eq("status", "permanent"))
        # Only inspect the first week for grid metadata; sorting decades of
        # half-hourly IMERG assets is unnecessarily expensive.
        grid_start = date.fromisoformat(PRODUCTS[key][2])
        first = ee.Image(images.filterDate(str(grid_start), str(grid_start + timedelta(days=7))).first())
        manifest["projections"][key] = first.projection().getInfo()
        manifest["projections"][key]["nominal_scale_m"] = first.projection().nominalScale().getInfo()
        print(key, manifest["projections"][key])
    fingerprint = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    manifest_path = args.output / "run_manifest.json"
    if manifest_path.exists():
        old = json.loads(manifest_path.read_text(encoding="utf-8"))
        if old["fingerprint"] != fingerprint:
            raise ValueError("Run settings changed; use a fresh --output folder to avoid mixing chunks")
    elif list((args.output / "chunks").glob("*/*.csv")):
        raise ValueError("Chunks exist without a run manifest; use a fresh --output folder")
    save_json(manifest_path, {"fingerprint": fingerprint, **manifest})
    for key, (_, _, available, _) in PRODUCTS.items():
        start = max(START, date.fromisoformat(available))
        while start < END:
            end = min(END, date(start.year + (start.month == 12), start.month % 12 + 1, 1))
            projection = {k: v for k, v in manifest["projections"][key].items() if k != "nominal_scale_m"}
            download_chunk(key, start, end, geometry, projection, args)
            start = end
    merge(args)
    if args.update_portal:
        subprocess.run([sys.executable, str(WORKSPACE / "data_portal/build_dashboard.py")], check=True)


if __name__ == "__main__":
    main()
