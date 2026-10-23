"""Collect and check a Marala upstream research catchment against primary sources.

Requires shapely, pyproj, pymupdf and matplotlib. Run from any directory:
python collect_marala_catchment.py

Verification means the documented outlet, geometry, area and sensitivity checks below;
it does not mean an agency-certified or field-surveyed catchment boundary.
"""
import csv
import hashlib
import json
import re
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection
from matplotlib.patches import Polygon as PlotPolygon
import pymupdf
from pyproj import Geod, Transformer
from shapely import transform
from shapely.geometry import Point, box, mapping, shape
from shapely.ops import nearest_points, unary_union

MODEL = Path(__file__).resolve().parents[1]
RAW = MODEL / "raw/marala/catchment"
OUTPUT = MODEL / "processed/marala/catchment"
OUTLET = (74.46, 32.67)  # Longitude, latitude; JICA/PMD station inventory.
JICA_URL = "https://openjicareport.jica.go.jp/pdf/12395935.pdf"
PMD_URL = "https://www.pmd.gov.pk/rnd/rndweb/rnd_new/journal/vol13_issue26_files/5_Flood_Forecasting_of_an_Ungauged_Trans-boundary_Chenab_River_Basin_Using_Distributed_Hydrological_Model_Integrated_Flood_Analysis_System_%28IFAS%29.pdf"
BASE = "https://mghydro.com/app/"
SUFFIX = "&precision=high&simplify=false&beautify=false"
GEOD = Geod(ellps="WGS84")
PROJECT = Transformer.from_crs(4326, 32643, always_xy=True)


def area_km2(geometry):
    if geometry.is_empty:
        return 0.0
    if geometry.geom_type in ("MultiPolygon", "GeometryCollection"):
        return sum(area_km2(g) for g in geometry.geoms)
    return abs(GEOD.geometry_area_perimeter(geometry)[0]) / 1e6


def get_source(relative, url):
    path = RAW / relative
    receipt = path.with_name(path.stem + "_receipt.json")
    if not path.exists():
        if "mghydro.com/app/" in url:
            time.sleep(5)  # Provider requests sequential calls spaced by 5 seconds.
        with urllib.request.urlopen(url, timeout=55) as response:
            body = response.read()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(body)
    body = path.read_bytes()
    metadata = {"source_url": url, "raw_file": path.relative_to(MODEL).as_posix(),
                "sha256": hashlib.sha256(body).hexdigest(), "bytes": len(body)}
    if receipt.exists():
        previous = json.loads(receipt.read_text(encoding="utf-8"))
        if previous.get("sha256") != metadata["sha256"]:
            raise ValueError(f"Saved source differs from recorded hash: {path}")
        metadata.update({k: v for k, v in previous.items() if k not in metadata})
    else:
        metadata["downloaded_utc"] = datetime.now(timezone.utc).isoformat()
    metadata["last_checked_utc"] = datetime.now(timezone.utc).isoformat()
    receipt.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    return body, metadata


def save_geojson(name, features):
    (OUTPUT / name).write_text(json.dumps({"type": "FeatureCollection", "features": features}, separators=(",", ":")) + "\n", encoding="utf-8")


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    sources = []
    datasets = {}
    requests = [
        ("canonical", "global_watersheds/marala_32.67_74.46_high.geojson", BASE + "watershed_api?lat=32.67&lng=74.46" + SUFFIX),
        ("nearby", "global_watersheds/marala_nearby_32.671_74.461_high.geojson", BASE + "watershed_api?lat=32.671&lng=74.461" + SUFFIX),
        ("low", "global_watersheds/marala_32.67_74.46_low.geojson", BASE + "watershed_api?lat=32.67&lng=74.46&precision=low&simplify=false&beautify=false"),
        ("rivers", "global_watersheds/marala_upstream_rivers_high.geojson", BASE + "upstream_rivers_api?lat=32.67&lng=74.46" + SUFFIX),
    ]
    for key, relative, url in requests:
        body, receipt = get_source(relative, url)
        datasets[key] = json.loads(body)
        sources.append(receipt)
    for relative, url in [
        ("references/jica_station_locations.pdf", JICA_URL),
        ("references/global_watersheds_help.html", "https://mghydro.com/watersheds/help.html"),
        ("references/global_watersheds_data_terms.html", "https://mghydro.com/watersheds/data/"),
        ("references/merit_hydro_source.html", "https://global-hydrodynamics.github.io/MERIT_Hydro/"),
        ("references/nasa_power_meteorology.html", "https://power.larc.nasa.gov/docs/methodology/meteorology/"),
    ]:
        _, receipt = get_source(relative, url)
        sources.append(receipt)

    with pymupdf.open(RAW / "references/jica_station_locations.pdf") as document:
        station_pages = [i + 1 for i, page in enumerate(document) if re.search(r"12\.\s*Marala\s+Chenab\s+32\.67\s+74\.46", page.get_text())]
    if not station_pages:
        raise ValueError("JICA station-coordinate evidence was not found")
    pmd_path = MODEL / "raw/marala/discharge/pmd/marala_historical_flood_peaks_pmd_journal.pdf"
    if not pmd_path.exists():
        body, receipt = get_source("references/pmd_marala_catchment.pdf", PMD_URL)
        pmd_path = MODEL / receipt["raw_file"]
    with pymupdf.open(pmd_path) as document:
        area_pages = [i + 1 for i, page in enumerate(document) if re.search(r"catchment area up to\s+Marala is 29192", page.get_text())]
    if not area_pages:
        raise ValueError("PMD catchment-area evidence was not found")
    sources.append({"source_url": PMD_URL, "raw_file": pmd_path.relative_to(MODEL).as_posix(),
                    "sha256": hashlib.sha256(pmd_path.read_bytes()).hexdigest(), "role": "published_area_reference"})
    canonical = datasets["canonical"]["features"][0]
    basin = shape(canonical["geometry"])
    nearby = shape(datasets["nearby"]["features"][0]["geometry"])
    low = shape(datasets["low"]["features"][0]["geometry"])
    if not all(g.is_valid and not g.is_empty and g.geom_type in ("Polygon", "MultiPolygon") for g in (basin, nearby, low)):
        raise ValueError("Invalid or empty basin geometry; no automatic repair applied")
    outlet = Point(OUTLET)
    projected = transform(basin, PROJECT.transform, interleaved=False)
    outlet_projected = transform(outlet, PROJECT.transform, interleaved=False)
    area = area_km2(basin)
    near_iou = area_km2(basin.intersection(nearby)) / area_km2(basin.union(nearby))
    low_iou = area_km2(basin.intersection(low)) / area_km2(basin.union(low))
    boundary_distance = projected.boundary.distance(outlet_projected)
    river_shapes = [shape(f["geometry"]) for f in datasets["rivers"]["features"]]
    rivers = unary_union(river_shapes)
    river_distance = transform(rivers, PROJECT.transform, interleaved=False).distance(outlet_projected)
    checks = {
        "valid_polygon_without_repair": basin.is_valid,
        "outlet_coordinates_found_in_jica_pmd_table": bool(station_pages),
        "published_station_point_inside_or_on_boundary": basin.covers(outlet),
        "station_within_500m_of_catchment_edge": boundary_distance <= 500,
        # The published coordinates have two decimal places; a fixed 500 m
        # circle would imply greater precision than that source provides.
        "upstream_network_intersects_station_coordinate_rounding_box": rivers.intersects(box(OUTLET[0] - .005, OUTLET[1] - .005, OUTLET[0] + .005, OUTLET[1] + .005)),
        "area_within_5_percent_of_pmd_29192_km2": abs(area / 29192 - 1) <= .05,
        "nearby_outlet_polygon_iou_at_least_0_99": near_iou >= .99,
        "low_precision_polygon_iou_at_least_0_98": low_iou >= .98,
        "downstream_khanki_excluded": not basin.covers(Point(73.97, 32.41)),
    }
    if not all(checks.values()):
        raise ValueError(f"Catchment verification failed: {checks}")
    properties = {"station": "Marala", "river": "Chenab", "area_km2_geodesic": round(area, 3),
                  "outlet_longitude": OUTLET[0], "outlet_latitude": OUTLET[1],
                  "source": "Global Watersheds / MERIT-Hydro and MERIT-Basins",
                  "verification_status": "source_and_geometry_checked_research_delineation",
                  "agency_certified": False, "source_url": sources[0]["source_url"],
                  "nominal_source_resolution": "3 arc-seconds (~90 m at equator)",
                  "crs": "OGC:CRS84 (WGS84 longitude, latitude)",
                  "license_note": "Service derived-data terms: CC BY-NC-SA 4.0; see saved terms and README."}
    save_geojson("marala_upstream_catchment.geojson", [{"type": "Feature", "properties": properties, "geometry": canonical["geometry"]}])
    save_geojson("marala_outlet.geojson", [{"type": "Feature", "properties": {"station": "Marala", "role": "published_station_coordinate_not_surveyed_pour_point", "source_url": JICA_URL, "source_pdf_page": station_pages[0]}, "geometry": mapping(outlet)}])
    save_geojson("marala_upstream_rivers.geojson", datasets["rivers"]["features"])

    rainfall_metadata = MODEL / "processed/marala/rainfall/marala_rainfall_grid_cells.csv"
    footprint_features, footprints = [], []
    if rainfall_metadata.exists():
        with rainfall_metadata.open(newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                lon, lat = float(row["longitude"]), float(row["latitude"])
                cell = box(lon - .3125, lat - .25, lon + .3125, lat + .25)
                footprints.append(cell)
                overlap = basin.intersection(cell)
                footprint_features.append({"type": "Feature", "geometry": mapping(cell), "properties": {
                    "cell_id": row["cell_id"], "latitude": lat, "longitude": lon,
                    "intersection_km2": area_km2(overlap), "footprint_basis": "MERRA2 native 0.5 latitude x 0.625 longitude degree grid"}})
        covered = basin.intersection(unary_union(footprints))
        uncovered = basin.difference(unary_union(footprints))
        coverage = {"downloaded_cells": len(footprints), "intersecting_cells": sum(f["properties"]["intersection_km2"] > 0 for f in footprint_features),
                    "covered_area_km2": area_km2(covered), "uncovered_area_km2": area_km2(uncovered),
                    "covered_fraction": area_km2(covered) / area,
                    "full_coverage": uncovered.is_empty,
                    "method": "Intersect native cell footprints, not grid centers or the requested rectangle, with the catchment. WGS84 geodesic areas.",
                    "action": "Full catchment is covered; no spatial grid extension is required." if uncovered.is_empty else "Extend the downloaded rainfall grid westward before calculating a full-catchment rainfall mean; retain the small gap explicitly."}
        save_geojson("marala_rainfall_grid_footprints.geojson", footprint_features)
        save_geojson("marala_rainfall_grid_uncovered.geojson", [] if uncovered.is_empty else [{"type": "Feature", "properties": {"role": "missing_rainfall_grid_coverage"}, "geometry": mapping(uncovered)}])
        (OUTPUT / "marala_rainfall_grid_coverage.json").write_text(json.dumps(coverage, indent=2) + "\n", encoding="utf-8")
    else:
        coverage = None

    nearest = nearest_points(basin.boundary, outlet)[0]
    report = {"checked_utc": datetime.now(timezone.utc).isoformat(), "verification_status": properties["verification_status"],
              "agency_certified": False, "field_survey_verified": False, "checks": checks,
              "area_km2_geodesic": area, "service_rounded_area_km2": canonical["properties"]["area_km2"],
              "bounds_wgs84": list(basin.bounds), "outlet": {"longitude": OUTLET[0], "latitude": OUTLET[1],
              "station_to_boundary_m": boundary_distance, "station_to_upstream_network_m": river_distance,
              "nearest_boundary_coordinate": list(nearest.coords)[0], "actual_service_snapped_pour_point": "not exposed by API",
              "published_coordinate_rounding_half_width_degrees": .005,
              "network_check_basis": "Network intersects the +/-0.005 degree rounding box implied by two-decimal station coordinates, rather than assuming survey precision."},
              "sensitivity": {"nearby_test_outlet": [74.461, 32.671], "nearby_polygon_iou": near_iou,
                              "nearby_symmetric_difference_km2": area_km2(basin.symmetric_difference(nearby)),
                              "low_precision_area_km2": area_km2(low), "low_precision_polygon_iou": low_iou},
              "references": {"station_coordinate": {"url": JICA_URL, "pdf_pages": station_pages, "table_source": "Received from PMD"},
                             "catchment_area": {"url": PMD_URL, "pdf_pages": area_pages, "area_km2": 29192,
                                                "difference_percent": 100 * (area / 29192 - 1)}},
              "rainfall_grid_coverage": coverage, "source_receipts": sources,
              "limitations": ["Model-derived hydrological boundary; not a surveyed or WAPDA/PMD-issued polygon.",
                              "Literature area agreement is a consistency check, not independent field verification.",
                              "Input coordinate is published to two decimal degrees. A nearby test gives an identical polygon; the exact service snap point is not exposed.",
                              "Provider documents MERIT-Hydro/MERIT-Basins, but the live API does not expose exact underlying dataset/software versions.",
                              "Catchment follows modeled topographic drainage and does not encode time-varying canal transfers, dam operations, or groundwater exchanges."]}
    (OUTPUT / "marala_catchment_verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    make_map(basin, river_shapes, footprint_features, area)
    print(f"Saved research catchment: {area:,.3f} km2; {len(checks)} checks passed.")
    print(f"Boundary distance {boundary_distance:.1f} m; river distance {river_distance:.1f} m; low-precision IoU {low_iou:.6f}.")
    if coverage:
        print(f"Rainfall coverage: {100 * coverage['covered_fraction']:.6f}%; missing {coverage['uncovered_area_km2']:.3f} km2.")


def make_map(basin, river_shapes, footprint_features, area):
    fig, (ax, inset) = plt.subplots(1, 2, figsize=(14, 7), gridspec_kw={"width_ratios": [3, 1]})
    for plot in (ax, inset):
        plot.add_patch(PlotPolygon(list(basin.exterior.coords), facecolor="#e0f2e9", edgecolor="#116149", linewidth=1.1))
        lines = [list(g.coords) for g in river_shapes if g.geom_type == "LineString"]
        plot.add_collection(LineCollection(lines, colors="#287faf", linewidths=.55, alpha=.85))
        plot.scatter(*OUTLET, c="#c33130", s=45, zorder=5, marker="o")
        plot.grid(alpha=.2)
        plot.set_aspect(1 / .84)
        plot.set_xlabel("Longitude (degrees east)")
        plot.set_ylabel("Latitude (degrees north)")
    for f in footprint_features:
        if f["properties"]["intersection_km2"] > 0:
            ax.add_patch(PlotPolygon(f["geometry"]["coordinates"][0], fill=False, edgecolor="#9a7729", alpha=.5, linewidth=.65))
    xmin, ymin, xmax, ymax = basin.bounds
    ax.set_xlim(xmin - .15, xmax + .15)
    ax.set_ylim(ymin - .15, ymax + .15)
    ax.annotate("Marala\n32.67 N, 74.46 E", OUTLET, xytext=(74.7, 32.4), arrowprops={"arrowstyle": "-", "color": "#c33130"}, fontsize=10)
    ax.set_title(f"Upstream catchment to Marala | {area:,.0f} km²\nGreen: catchment; blue: upstream rivers; ochre: downloaded rainfall cells", fontsize=12)
    inset.set_xlim(74.44, 74.48)
    inset.set_ylim(32.65, 32.69)
    inset.set_title("Outlet detail\nRed: published station coordinate", fontsize=11)
    inset.tick_params(axis="x", rotation=45)
    fig.text(.06, .02, "Source: Global Watersheds (Heberger) / MERIT-Hydro & MERIT-Basins; outlet: JICA inventory, received from PMD.\nSource- and geometry-checked research delineation; no agency certification. WGS84 geographic display; no political boundaries shown.", fontsize=9)
    fig.tight_layout(rect=[0, .09, 1, 1])
    fig.savefig(OUTPUT / "marala_catchment_review.png", dpi=180)
    plt.close(fig)


if __name__ == "__main__":
    main()
