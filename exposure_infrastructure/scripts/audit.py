"""Audit GIS readiness, write dataset summary and render a sample map."""
import csv
import hashlib
import json
import sqlite3
import tempfile
from pathlib import Path

import fiona
import geopandas as gpd
import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.warp import transform_bounds
from shapely.geometry import shape, box
from shapely.ops import transform
from shapely.prepared import prep

from common import setup, load, area, output_paths, manifest, write_json, now, digest, resolve

REQUIRED = {"roads": ["osm_id", "highway", "u", "v", "direction", "length_m", "bridge", "tunnel", "oneway", "access", "tags_json"],
            "buildings": ["osm_id", "building", "tags_json"],
            "hospitals": ["osm_id", "tags_json"], "schools": ["osm_id", "amenity", "tags_json"],
            "settlements": ["osm_id", "place", "tags_json"], "boundaries": ["shapeName", "source_level"],
            "reference_buildings": ["reference_id", "quadkey", "source_file", "source_row", "tags_json"]}


def audit_vector(path, name, geom, reports):
    result = {"status": "READY", "issues": [], "recommendations": [], "feature_count": 0,
              "invalid": 0, "empty": 0, "outside_area": 0, "duplicate_ids": 0, "coincident_geometries": 0,
              "attribute_nonempty": {}, "bbox_wgs84": None, "crs": []}
    result["type_counts"] = {}
    xmin, ymin, xmax, ymax = geom.bounds
    tiles = [[0 for _ in range(5)] for _ in range(5)]
    containment = prep(geom.buffer(1e-9))
    # Disk-backed keys let the audit scale to millions of Pakistan buildings/edges.
    with tempfile.TemporaryDirectory(dir=reports) as scratch:
        db = sqlite3.connect(str(Path(scratch) / "keys.sqlite"))
        db.execute("CREATE TABLE ids (k TEXT PRIMARY KEY)")
        db.execute("CREATE TABLE geoms (k TEXT PRIMARY KEY)")
        try:
            layer_names = ["ADM1", "ADM2"] if name == "boundaries" else fiona.listlayers(path)
            for layer in layer_names:
                with fiona.open(path, layer=layer) as src:
                    if not src.crs:
                        raise ValueError("Missing CRS")
                    crs = CRS.from_user_input(src.crs)
                    result["crs"].append(crs.to_string())
                    convert = None if crs == CRS.from_epsg(4326) else Transformer.from_crs(crs, 4326, always_xy=True).transform
                    fields = src.schema["properties"]
                    missing = sorted(set(REQUIRED.get(name, [])) - set(fields))
                    if missing:
                        result["issues"].append(f"Missing columns: {missing}")
                        result["status"] = "BLOCKED"
                    for feat in src:
                        result["feature_count"] += 1
                        props = dict(feat["properties"])
                        if name == 'roads':
                            length = props.get('length_m')
                            if length is None or not np.isfinite(length) or length <= 0 or props.get('direction') not in ('forward','reverse','bidirectional') or not props.get('u') or not props.get('v'):
                                result.setdefault('invalid_network_edges',0)
                                result['invalid_network_edges'] += 1
                            else:
                                result['road_length_km'] = result.get('road_length_km',0) + length/1000
                        category = props.get("highway") if name == "roads" else props.get("building") if name == "buildings" else props.get("place") if name == "settlements" else props.get("source_level") if name == "boundaries" else props.get("amenity") or props.get("healthcare") or props.get("emergency")
                        category = category or "unknown"
                        result["type_counts"][category] = result["type_counts"].get(category, 0) + 1
                        for key, value in props.items():
                            if value is not None and value != "":
                                result["attribute_nonempty"][key] = result["attribute_nonempty"].get(key, 0) + 1
                        if not feat["geometry"]:
                            result["empty"] += 1
                            continue
                        g = shape(feat["geometry"])
                        if convert is not None:
                            g = transform(convert, g)
                        if g.is_empty:
                            result["empty"] += 1
                            continue
                        if not g.is_valid:
                            result["invalid"] += 1
                        if not containment.covers(g):
                            result["outside_area"] += 1
                        point = g.representative_point()
                        column = min(4, max(0, int(5 * (point.x - xmin) / (xmax - xmin))))
                        row = min(4, max(0, int(5 * (point.y - ymin) / (ymax - ymin))))
                        tiles[row][column] += 1
                        bounds = g.bounds
                        b = result["bbox_wgs84"]
                        result["bbox_wgs84"] = list(bounds) if b is None else [min(b[0], bounds[0]), min(b[1], bounds[1]), max(b[2], bounds[2]), max(b[3], bounds[3])]
                        key = props.get("feature_id") or props.get("shapeID") or props.get("reference_id") or str(feat["id"])
                        try:
                            db.execute("INSERT INTO ids VALUES (?)", (layer + "/" + str(key),))
                        except sqlite3.IntegrityError:
                            result["duplicate_ids"] += 1
                        fingerprint = hashlib.sha256(g.normalize().wkb).hexdigest()
                        try:
                            db.execute("INSERT INTO geoms VALUES (?)", (layer + "/" + fingerprint,))
                        except sqlite3.IntegrityError:
                            result["coincident_geometries"] += 1
            db.commit()
        finally:
            db.close()
    for key in ("invalid", "empty", "outside_area", "duplicate_ids", "invalid_network_edges"):
        if result.get(key):
            result["issues"].append(f"{key}: {result[key]}")
            result["status"] = "BLOCKED"
    if not result["feature_count"]:
        result["issues"].append("No mapped features; source absence cannot establish real-world absence")
        result["recommendations"].append("Check the AOI and compare with an authoritative facility/settlement inventory")
    if result["coincident_geometries"]:
        result["issues"].append("Coincident geometry detected; review source objects before deduplicating")
    optional_road_tags = {'bridge','tunnel','oneway','access'}
    for key in REQUIRED.get(name, []):
        if name == 'roads' and key in optional_road_tags:
            continue  # Null means tag not supplied; do not invent unavailable source attributes.
        if result["feature_count"] and not result["attribute_nonempty"].get(key):
            result["issues"].append(f"Required attribute entirely missing: {key}")
    if result["issues"] and result["status"] != "BLOCKED":
        result["status"] = "REVIEW"
    result["spatial_distribution"] = {"representative_point_counts_5x5": tiles, "row_order": "south to north", "column_order": "west to east", "note": "Screening for sparse mapped areas only; a feature can extend into adjacent tiles. Empty tiles require independent completeness checks."}
    return result


def audit_population(path, geom, expected):
    result = {"status": "READY", "issues": [], "recommendations": [], "valid_cells": 0, "population_sum": 0.0, "negative_cells": 0, "nodata_cells_inside_area": 0, "nonfinite_cells": 0}
    with rasterio.open(path) as src:
        if src.crs is None:
            raise ValueError("Raster has no CRS")
        bounds = transform_bounds(src.crs, 4326, *src.bounds, densify_pts=21)
        result.update(crs=src.crs.to_string(), bbox_wgs84=list(bounds), resolution=list(src.res), nodata=src.nodata, dtype=src.dtypes[0])
        if not box(*bounds).intersects(geom):
            raise ValueError("Population raster does not overlap AOI")
        equal_area = Transformer.from_crs(4326, 6933, always_xy=True).transform
        area_m2 = transform(equal_area, geom).area
        covered_m2 = transform(equal_area, geom.intersection(box(*bounds))).area
        result["aoi_footprint_coverage_fraction"] = covered_m2 / area_m2
        if result["aoi_footprint_coverage_fraction"] < 0.999:
            result["status"] = "REVIEW"
            result["issues"].append("Population raster footprint does not cover the entire selected AOI")
            result["recommendations"].append("Inspect source coverage differences, especially at borders; do not infer zero population outside source footprint")
        from rasterio.features import geometry_mask
        from rasterio.warp import transform_geom
        from shapely.geometry import mapping
        polygon = transform_geom(4326, src.crs, mapping(geom))
        outside = 0
        for _, window in src.block_windows(1):
            a = src.read(1, window=window, masked=True)
            good = ~np.ma.getmaskarray(a)
            inside = geometry_mask([polygon], out_shape=a.shape, transform=src.window_transform(window), invert=True)
            outside += int((good & ~inside).sum())
            result["nodata_cells_inside_area"] += int((inside & ~good).sum())
            result["nonfinite_cells"] += int((~np.isfinite(a.data) & good).sum())
            result["valid_cells"] += int(good.sum())
            result["population_sum"] += float(a.sum(dtype="float64")) if a.count() else 0.0
            result["negative_cells"] += int(((a.data < 0) & good).sum())
        if not result["valid_cells"] or result["negative_cells"] or result["nonfinite_cells"] or outside:
            result["status"] = "BLOCKED"
            result["issues"].append(f"valid cells={result['valid_cells']}; negative={result['negative_cells']}; outside={outside}")
        result["nodata_interpretation"] = "Constrained WorldPop nodata is retained as unknown/masked; not silently converted to zero"
        if expected and not np.isclose(result["population_sum"], expected["population_sum"], rtol=1e-10):
            result["status"] = "BLOCKED"
            result["issues"].append("Population sum differs from preprocessing manifest")
    return result


def flood_alignment(cfg, geom, references=False):
    results = []
    for item in cfg.get("flood_reference_extents" if references else "flood_extents", []):
        filename = item["path"] if isinstance(item, dict) else item
        path = resolve(cfg, filename)
        try:
            if path.suffix.lower() in (".tif", ".tiff"):
                with rasterio.open(path) as src:
                    if src.crs is None:
                        raise ValueError("Flood raster CRS missing")
                    footprint = box(*transform_bounds(src.crs, 4326, *src.bounds, densify_pts=21))
                    crs = src.crs.to_string()
            else:
                frame = gpd.read_file(path, **({"layer": item["layer"]} if isinstance(item, dict) and item.get("layer") else {}))
                if frame.crs is None or frame.empty or not frame.geometry.is_valid.all():
                    raise ValueError("Flood vectors missing CRS, empty or invalid")
                crs = str(frame.crs)
                footprint = frame.to_crs(4326).geometry.union_all()
            overlap = footprint.intersection(geom)
            intersects = not overlap.is_empty and overlap.area > 0
            areas = gpd.GeoSeries([overlap, geom], crs=4326).to_crs(6933).area
            results.append({"path": str(path), "crs": crs, "overlaps_aoi": intersects,
                            "overlap_area_km2":float(areas.iloc[0]/1e6), "aoi_overlap_fraction":float(areas.iloc[0]/areas.iloc[1]),
                            "status": "COMPATIBLE_EXTENT" if intersects else "BLOCKED", "note": "CRS and footprint check only; does not establish geolocation accuracy or flood-mask correctness"})
        except Exception as exc:
            results.append({"path": str(path), "status": "BLOCKED", "error": str(exc)})
    return results or [{"status": "NOT_CHECKED", "reason": "No reference flood extents configured" if references else "No georeferenced model segmentation outputs supplied; configure flood_extents. Published reference observations are audited separately."}]


def sample_map(paths, geom, destination, label="Balloki", verified=False, reference_path=None, station=None):
    import os
    os.environ.setdefault("MPLCONFIGDIR", str(destination.parent / ".matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.lines import Line2D
    fig, ax = plt.subplots(figsize=(11, 10))
    with rasterio.open(paths["population"]) as src:
        scale = min(1, 1400 / max(src.width, src.height))
        image = src.read(1, masked=True, out_shape=(max(1, int(src.height * scale)), max(1, int(src.width * scale))))
        bounds = transform_bounds(src.crs, 4326, *src.bounds)
        # This preview only is downsampled. Analytical raster is untouched.
        raster = ax.imshow(np.log1p(image.clip(min=0)), extent=[bounds[0], bounds[2], bounds[1], bounds[3]], cmap="YlOrRd", origin="upper", alpha=0.85)
        fig.colorbar(raster, ax=ax, shrink=0.7, label="log(1 + population count per source cell); display preview")
    if reference_path and reference_path.exists():
        water = gpd.read_file(reference_path).to_crs(4326)
        water.plot(ax=ax, color="#1879cb", alpha=0.4, linewidth=0, zorder=2)
    colours = {"roads": "#555555", "buildings": "#284a78", "settlements": "#181818", "hospitals": "#00875a", "schools": "#6829ad"}
    markers = {"settlements": "o", "hospitals": "P", "schools": "^"}
    for name, colour in colours.items():
        if paths[name].exists():
            frame = gpd.read_file(paths[name], bbox=geom.bounds).to_crs(4326)
            if frame.empty:
                continue
            if name in ("hospitals", "schools", "settlements"):
                frame.geometry = frame.geometry.representative_point()
                frame.plot(ax=ax, color=colour, markersize=9 if name == "settlements" else 130, marker=markers[name],
                           edgecolor="white" if name != "settlements" else colour, linewidth=0.8, alpha=0.55 if name == "settlements" else 1,
                           zorder=4 if name == "settlements" else 8)
                if name != "settlements":
                    for point in frame.geometry:
                        ax.annotate("Hospital" if name == "hospitals" else "School", (point.x, point.y), xytext=(8, 8), textcoords="offset points", color=colour, fontsize=9,
                                    bbox={"facecolor": "white", "alpha": 0.85, "edgecolor": "none", "pad": 2}, zorder=9)
            else:
                frame.plot(ax=ax, color=colour, linewidth=0.5)
    gpd.GeoSeries([geom], crs=4326).boundary.plot(ax=ax, color="black", linewidth=1)
    if station:
        x,y=station['coordinates']
        ax.scatter([x],[y],marker='*',s=170,color='red',edgecolors='white',zorder=10)
        ax.annotate(station['name'],(x,y),xytext=(8,-15),textcoords='offset points',color='darkred',zorder=10)
    ax.set(xlim=(geom.bounds[0], geom.bounds[2]), ylim=(geom.bounds[1], geom.bounds[3]), xlabel="Longitude (WGS84)", ylabel="Latitude (WGS84)", title=f"{label} exposure datasets" + (" — provisional study boundary" if not verified else ""))
    ax.legend(handles=[Line2D([0], [0], color=c, marker=markers.get(n), linestyle="None" if n in markers else "-", label=n) for n, c in colours.items()], loc="upper right")
    if reference_path:
        ax.text(0.02,0.02,'Blue: UNOSAT VIIRS water reference, 26 Aug–7 Sep 2025\nPreliminary historical water extent; not model output',transform=ax.transAxes,fontsize=8,bbox={'facecolor':'white','alpha':0.9,'edgecolor':'none'})
    fig.text(0.04, 0.025, "WorldPop (CC BY 4.0); © OpenStreetMap contributors (ODbL), Geofabrik.\nOSM feature absence does not prove absence." + (" Pilot boundary requires verification." if not verified else ""), fontsize=9)
    fig.savefig(destination, dpi=180, bbox_inches="tight")
    plt.close(fig)


def run(cfg, data, make_map=True):
    geom, paths, m = area(cfg, data), output_paths(cfg, data), manifest(data)
    run_record = m["runs"].get(cfg["area"]["name"], {})
    # An older run must be checked against its actual source snapshot, not a later provider selection.
    run_sources = run_record.get("source_snapshots", m["sources"])
    reports = data / "validation_reports"
    report = {"audited_at": now(), "area": cfg["area"], "datasets": {}, "sources": {}, "flood_alignment": flood_alignment(cfg, geom),
              "completeness": "UNKNOWN: spatial gaps and real-world completeness require independent reference inventories; sparse OSM mapping is not a reliable absence label"}
    if cfg['area']['name'] == 'trimmu_jhang':
        import os
        balloki = data/'processed/balloki'
        pilot = paths['population'].parents[1]
        shared_outputs=[]
        for name,path in paths.items():
            peer=balloki/path.relative_to(pilot)
            if path.exists() and peer.exists() and os.path.samefile(path,peer):
                shared_outputs.append(name)
        baseline_path=data/'metadata/balloki_preservation_baseline.json'
        changed=[]
        if baseline_path.exists():
            baseline=json.loads(baseline_path.read_text(encoding='utf-8'))
            changed=[name for name,checksum in baseline.items() if not (balloki/name).exists() or digest(balloki/name)!=checksum]
        report['pilot_separation']={'status':'BLOCKED' if shared_outputs or changed else 'VERIFIED' if baseline_path.exists() else 'DISTINCT_OUTPUT_PATHS',
            'trimmu_directory':str(pilot), 'balloki_directory':str(balloki),'shared_processed_files':shared_outputs,
            'balloki_changed_files':changed,'balloki_preservation_checked':baseline_path.exists(),
            'original_storage':'National raw originals are shared cache; processed datasets and pilot manifests are separate.'}
    for key, source in run_sources.items():
        try:
            raw = data / source["raw_path"].replace("\\", "/") if source.get("raw_path") else Path(source["path"])
            ok = raw.exists() and digest(raw) == source["sha256"]
            report["sources"][key] = {"status": "VERIFIED" if ok else "BLOCKED", "bytes": raw.stat().st_size if raw.exists() else 0}
        except Exception as exc:
            report["sources"][key] = {"status": "BLOCKED", "error": str(exc)}
    for name, path in paths.items():
        try:
            if not path.exists():
                raise FileNotFoundError(str(path))
            result = audit_population(path, geom, run_record.get("datasets", {}).get(name)) if name == "population" else audit_vector(path, name, geom, reports)
            result['technical_status'] = result['status']
            result["processed_bytes"] = path.stat().st_size
            source_keys = ["worldpop"] if name == "population" else ["ADM1", "ADM2"] if name == "boundaries" else ["osm"]
            result["downloaded_bytes"] = sum(report["sources"].get(k, {}).get("bytes", 0) for k in source_keys)
            result["source_size_note"] = "OSM raw size shared by all OSM layers" if source_keys == ["osm"] else ""
            if any(report["sources"].get(k, {}).get("status") != "VERIFIED" for k in source_keys):
                result["status"] = "BLOCKED"
                result["issues"].append("Missing or unverified source download")
            if not cfg["area"].get("verified", False):
                if result["status"] == "READY":
                    result["status"] = "REVIEW"
                result["recommendations"].append("Replace/verify the provisional study boundary")
            if name == "boundaries":
                years = {k: run_sources.get(k, {}).get("source_metadata", {}).get("boundaryYearRepresented") for k in ("ADM1", "ADM2")}
                result["provenance"] = {k: run_sources.get(k, {}).get("source_metadata", {}) for k in ("ADM1", "ADM2")}
                if any(y and str(y).isdigit() and int(y) < 2025 for y in years.values()):
                    if result["status"] == "READY":
                        result["status"] = "REVIEW"
                    result["issues"].append(f"Administrative source representation years: {years}")
                    result["recommendations"].append("Review any district changes since the source geometry date. Source review and publication dates are recorded separately; a 2026 upload does not establish 2026 geometry.")
            report["datasets"][name] = result
        except Exception as exc:
            report["datasets"][name] = {"status": "BLOCKED", "issues": [str(exc)], "recommendations": ["Run download and preprocessing, then repeat audit"]}
    extraction_path = reports / f"{cfg['area']['name']}_extraction.json"
    report["extraction"] = json.loads(extraction_path.read_text(encoding="utf-8")) if extraction_path.exists() else {"status": "NOT_CHECKED"}
    population_sum = report["datasets"].get("population", {}).get("population_sum", 0)
    verification_path = reports / f"{cfg['area']['name']}_source_verification.json"
    verification = json.loads(verification_path.read_text(encoding="utf-8")) if verification_path.exists() else {}
    report["source_verification"] = verification
    station_check = verification.get("station_boundary_check", {})
    if station_check and not station_check.get("contains_station"):
        report["datasets"]["boundaries"]["status"] = "BLOCKED"
        report["datasets"]["boundaries"]["issues"].append("Selected district does not contain configured station coordinates")
    reference = verification.get("flood_reference", {})
    reference_cfg = dict(cfg)
    if reference.get("path"):
        reference_cfg["flood_reference_extents"] = [{"path": str(data/reference["path"]), "layer": l["layer"]} for l in reference.get("layers", [])]
    report["flood_reference_alignment"] = flood_alignment(reference_cfg, geom, references=True)
    if reference.get("raw_path"):
        raw = data/reference["raw_path"]
        if not raw.exists() or digest(raw) != reference.get("receipt", {}).get("sha256"):
            report["flood_reference_alignment"].append({"status":"BLOCKED", "reason":"UNOSAT raw reference checksum mismatch or missing file"})
    building_check = verification.get("buildings_reference", {})
    if building_check.get("status") == "ASSESSED":
        try:
            report["reference_buildings_audit"] = audit_vector(data/building_check["processed_path"], "reference_buildings", geom, reports)
            for tile in building_check.get("tiles", []):
                raw = data/tile["raw_path"]
                if not raw.exists() or digest(raw) != tile['sha256']:
                    raise ValueError(f"Reference building tile missing or checksum mismatch: {raw}")
            report["reference_buildings_audit"]["originals_verified"] = True
        except Exception as exc:
            report["reference_buildings_audit"] = {"status":"BLOCKED", "issues":[str(exc)]}
        gaps = building_check["reference_buildings_without_nearby_osm"]
        report["completeness"] = f"ASSESSED against Microsoft image-derived building footprints: {gaps:,} reference detections lack a nearby OSM footprint. Roads and facilities still lack independently verified real-world inventories."
        if gaps:
            d=report["datasets"]["buildings"]
            if d["status"] == "READY":
                d["status"] = "REVIEW"
            d["issues"].append(f"Independent reference reveals {gaps:,} building detections without nearby OSM footprint; OSM alone is incomplete for exposure estimates")
            d["recommendations"].append("Use the separate reference_buildings layer after reviewing detection quality, imagery age and duplicates; retain source identity.")
    report["readiness_checks"] = {
        "study_boundary": "DOCUMENTED_ADMINISTRATIVE_AREA" if cfg["area"].get("verified") and cfg["area"]["mode"] == "admin" else "REVIEW",
        "osm_inventory": verification.get("osm_inventory", {}).get("status", "NOT_CHECKED"),
        "building_completeness": building_check.get("status", "NOT_CHECKED"),
        "model_output_alignment": "NOT_CHECKED" if not cfg.get("flood_extents") else "CHECKED_EXTENT_ONLY",
        "reference_flood_alignment": report["flood_reference_alignment"]}
    for name in ('roads','hospitals','schools','settlements','critical_infrastructure'):
        d=report['datasets'].get(name,{})
        if d.get('status')=='READY':
            d['status']='REVIEW'
        d.setdefault('coverage_status','UNKNOWN_REAL_WORLD_COMPLETENESS')
        d.setdefault('recommendations',[]).append('Compare with an independent road/facility/settlement inventory before operational impact or evacuation analysis; source extraction is not a completeness guarantee.')
    for name in ("buildings", "hospitals", "schools"):
        d = report["datasets"].get(name, {})
        if "feature_count" in d:
            d.setdefault("recommendations", []).append(f"Verify completeness against independent inventories: {d['feature_count']} mapped {name} in an AOI with an estimated {population_sum:,.0f} people; source counts alone do not establish full coverage")
    failure_count=sum(v for k,v in report['extraction'].get('counts',{}).items() if k!='repaired')
    located=verification.get('extraction_failure_locations',{}).get('failures',[])
    failures_outside = len(located)==failure_count and all(e.get('outside_aoi') and e.get('all_objects_unchanged_since_extract') for e in located)
    report['extraction']['all_failures_verified_outside_aoi']=failures_outside
    if failure_count and not failures_outside:
        for name, d in report["datasets"].items():
            if name not in ("population", "boundaries"):
                if d["status"] == "READY":
                    d["status"] = "REVIEW"
                d.setdefault("recommendations", []).append("Review source geometry extraction failures; see extraction report (national counts, may be outside AOI)")
    report["overall_status"] = "BLOCKED" if any(d["status"] == "BLOCKED" for d in report["datasets"].values()) or any(f["status"] == "BLOCKED" for f in report["flood_alignment"] + report["flood_reference_alignment"]) or report.get("reference_buildings_audit", {}).get("status") == "BLOCKED" else "REVIEW" if any(d["status"] == "REVIEW" for d in report["datasets"].values()) or not cfg.get("flood_extents") else "READY"
    if report.get('pilot_separation',{}).get('status')=='BLOCKED':
        report['overall_status']='BLOCKED'
    report['technical_preparation_status']='FAILED' if any(d.get('technical_status')=='BLOCKED' for d in report['datasets'].values()) or any(s.get('status')=='BLOCKED' for s in report['sources'].values()) or report.get('reference_buildings_audit',{}).get('status')=='BLOCKED' else 'PASSED'
    stem = cfg["area"]["name"]
    write_json(reports / f"{stem}_audit.json", report)
    text = [f"# {stem} dataset audit", "", f"Technical preparation: **{report['technical_preparation_status']}**", "", f"Overall operational readiness: **{report['overall_status']}**", "", "| Dataset | Status | Records/cells | Downloaded MB | Processed MB |", "|---|---|---:|---:|---:|"]
    with (data / f"metadata/{stem}_summary.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["dataset", "readiness", "records_or_valid_cells", "downloaded_bytes", "processed_bytes", "bbox_wgs84", "notes"])
        for name, d in report["datasets"].items():
            count = d.get("feature_count", d.get("valid_cells", 0))
            writer.writerow([name, d["status"], count, d.get("downloaded_bytes", 0), d.get("processed_bytes", 0), json.dumps(d.get("bbox_wgs84")), d.get("source_size_note", "")])
            text.append(f"| {name} | {d['status']} | {count:,} | {d.get('downloaded_bytes', 0)/1e6:.2f} | {d.get('processed_bytes', 0)/1e6:.2f} |")
    text.extend(["", "Downloaded OSM size is shared; do not sum it across vector layers.", "", report["completeness"], ""])
    for name, d in report["datasets"].items():
        text.extend([f"## {name}", "", *[f"- {x}" for x in d.get("issues", []) + d.get("recommendations", [])], ""])
    text.extend(["## Flood alignment", "", "```json", json.dumps(report["flood_alignment"], indent=2), "```"])
    text.extend(["", "## Published flood reference alignment", "", "```json", json.dumps(report["flood_reference_alignment"], indent=2), "```", "", "## Source verification", "", f"See {stem}_source_verification.json for independent inventory checks, provenance and coverage measurements."])
    if report.get('pilot_separation'):
        text.extend(['','## Pilot separation','','```json',json.dumps(report['pilot_separation'],indent=2),'```'])
    (reports / f"{stem}_audit.md").write_text("\n".join(text), encoding="utf-8")
    current = m["runs"].setdefault(stem, {})
    current["audit"] = {"status": report["overall_status"], "report": f"validation_reports/{stem}_audit.json", "date": now()}
    if verification:
        current["source_verification"] = {"report": verification_path.relative_to(data).as_posix(), "checks": report["readiness_checks"]}
        supplemental = current.setdefault("supplemental_datasets", {})
        for key, info, filename in (("reference_buildings", building_check, building_check.get("processed_path")), ("flood_reference", reference, reference.get("path"))):
            if filename:
                p=data/filename
                supplemental[key]={"path":filename,"bytes":p.stat().st_size,"source":info.get("source"),
                                   "license":info.get("license"),"crs":"EPSG:4326","bbox":list(geom.bounds),
                                   "feature_count":info.get("feature_count",sum(l['count'] for l in info.get('layers',[]))),
                                   "metadata_report":verification_path.relative_to(data).as_posix(),
                                   "status":report.get("reference_buildings_audit",{}).get("status") if key=='reference_buildings' else info.get('status')}
    for name, d in report["datasets"].items():
        if name in current.get("datasets", {}):
            current["datasets"][name].update({k: d[k] for k in ("bbox_wgs84", "crs", "feature_count", "valid_cells", "status") if k in d})
            current["datasets"][name]["path"] = paths[name].relative_to(data).as_posix()
    write_json(data / "metadata/manifest.json", m)
    # Each pilot carries its own immutable-source snapshot and reports. National
    # originals remain checksum-addressed shared cache; no Balloki output is moved.
    import shutil
    pilot = paths['population'].parents[1]
    pilot_metadata = pilot / 'metadata'
    pilot_reports = pilot / 'validation_reports'
    pilot_metadata.mkdir(parents=True, exist_ok=True)
    pilot_reports.mkdir(parents=True, exist_ok=True)
    write_json(pilot_metadata / 'manifest.json', {'schema_version':1,'pilot':stem,'created_at':now(),
        'configuration':{k:v for k,v in cfg.items() if not k.startswith('_')}, 'sources':run_sources,
        'run':current,'storage_note':'Processed layers belong exclusively to this pilot. Original national datasets are shared read-only cache under datasets/exposure/raw; source hashes and paths are recorded here.'})
    shutil.copy2(data / f'metadata/{stem}_summary.csv', pilot_metadata / 'summary.csv')
    shutil.copy2(reports / f'{stem}_audit.json', pilot_reports / 'audit.json')
    shutil.copy2(reports / f'{stem}_audit.md', pilot_reports / 'audit.md')
    if verification_path.exists():
        shutil.copy2(verification_path, pilot_reports / 'source_verification.json')
    extraction = reports / f'{stem}_extraction.json'
    if extraction.exists():
        shutil.copy2(extraction, pilot_reports / 'extraction.json')
    vector_count = sum(d.get("feature_count", 0) for d in report["datasets"].values())
    if make_map and vector_count > 250000:
        print("Map skipped for large selection; use a smaller preview AOI. Dataset audit completed.", flush=True)
    elif make_map and all(paths[n].exists() for n in ("population", "roads", "buildings")):
        sample_map(paths, geom, reports / f"{stem}_sample_map.png", label=stem, verified=cfg["area"].get("verified", False), reference_path=data/reference['path'] if reference.get('path') else None, station=cfg['area'].get('station'))
        shutil.copy2(reports / f'{stem}_sample_map.png', pilot_reports / 'sample_map.png')
    print(f"Audit: {report['overall_status']} — {reports / (stem + '_audit.md')}", flush=True)
    return report


if __name__ == "__main__":
    parser = setup(__doc__)
    parser.add_argument("--no-map", action="store_true")
    args = parser.parse_args()
    result = run(*load(args), make_map=not args.no_map)
    raise SystemExit(1 if result["overall_status"] == "BLOCKED" else 0)
