"""Select Groundsource flood events in Pakistan and map them to the 20 km grid.

Input:  raw/groundsource/groundsource_2026.parquet (Zenodo 10.5281/zenodo.18647054, CC-BY-4.0, unchanged)
Output: processed/groundsource_pakistan_events.csv, one row per event whose location lies mostly in Pakistan:
        uuid, start_date, end_date, duration_days, area_km2, centroid lon/lat, pakistan_share,
        centroid_cell, and cells = "cell_id:share_of_event:share_of_cell;..." for every grid cell it overlaps.
        Events larger than 20,000 km2 keep an empty cells list (located only to a province or country).

No filtering by duration or size happens here; the flash-flood label rule is applied at training time.
Run from this folder: ../../../.venv/Scripts/python.exe extract_groundsource_pakistan.py
"""
from __future__ import annotations

import csv
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pyarrow.parquet as pq
import pyproj
import shapely
from shapely import STRtree, box, from_wkb
from shapely.geometry import shape

DATASET = Path(__file__).resolve().parents[1]
SOURCE = DATASET / "raw" / "groundsource" / "groundsource_2026.parquet"
GRID_DIR = DATASET / "raw" / "gee" / "grid"
OUTPUT = DATASET / "processed" / "groundsource_pakistan_events.csv"
MAX_CELL_LISTING_KM2 = 20000
TO_GRID = pyproj.Transformer.from_crs(4326, 6933, always_xy=True)


def to_grid(geometry):
    return shapely.transform(geometry, lambda xy: np.column_stack(TO_GRID.transform(xy[:, 0], xy[:, 1])))


def main():
    grid = json.loads((GRID_DIR / "grid_definition.json").read_text(encoding="utf-8"))
    cell_m = grid["cell_m"]
    with (GRID_DIR / "cells.csv").open(encoding="utf-8") as handle:
        cells = list(csv.DictReader(handle))
    by_rowcol = {(int(c["row"]), int(c["col"])): int(c["cell_id"]) for c in cells}
    boxes = [box(grid["x0"] + int(c["col"]) * cell_m, grid["y1"] - (int(c["row"]) + 1) * cell_m,
                 grid["x0"] + (int(c["col"]) + 1) * cell_m, grid["y1"] - int(c["row"]) * cell_m) for c in cells]
    tree = STRtree(boxes)
    boundary = json.loads((GRID_DIR / "pakistan_lsib.geojson").read_text(encoding="utf-8"))
    pakistan_ll = shapely.union_all([shape(f["geometry"]) for f in boundary["features"]])
    pakistan = to_grid(pakistan_ll)
    shapely.prepare(pakistan)
    minx, miny, maxx, maxy = pakistan_ll.bounds

    table = pq.read_table(SOURCE, columns=["uuid", "area_km2", "geometry", "start_date", "end_date"])
    geometries = from_wkb(table.column("geometry").to_numpy(zero_copy_only=False))
    bounds = shapely.bounds(geometries)
    near = np.flatnonzero((bounds[:, 2] >= minx) & (bounds[:, 0] <= maxx) & (bounds[:, 3] >= miny) & (bounds[:, 1] <= maxy))
    print(f"{len(geometries):,} events in the file; {len(near):,} touch the Pakistan bounding box", flush=True)
    uuids = table.column("uuid").to_pylist()
    areas = table.column("area_km2").to_pylist()
    starts = table.column("start_date").to_pylist()
    ends = table.column("end_date").to_pylist()

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    kept = invalid = 0
    with OUTPUT.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["uuid", "start_date", "end_date", "duration_days", "area_km2", "lon", "lat", "pakistan_share", "centroid_cell", "cells_overlapped", "cells"])
        for index in near:
            geometry = geometries[index]
            if geometry is None or geometry.is_empty:
                invalid += 1
                continue
            if not geometry.is_valid:
                geometry = shapely.make_valid(geometry)
            projected = to_grid(geometry)
            area = projected.area
            if area > 0:
                share = projected.intersection(pakistan).area / area
            else:
                share = 1.0 if pakistan.contains(projected.centroid) else 0.0
            if share < 0.5:
                continue
            centroid = projected.centroid if area > 0 else projected.representative_point()
            col = int((centroid.x - grid["x0"]) // cell_m)
            row = int((grid["y1"] - centroid.y) // cell_m)
            centroid_cell = by_rowcol.get((row, col), "")
            listing = []
            if areas[index] is not None and areas[index] <= MAX_CELL_LISTING_KM2:
                for hit in tree.query(projected):
                    overlap = boxes[hit].intersection(projected).area if area > 0 else (1.0 if boxes[hit].covers(projected) else 0.0)
                    of_event = overlap / area if area > 0 else overlap
                    if of_event <= 0:
                        continue
                    listing.append(f"{int(cells[hit]['cell_id'])}:{of_event:.3f}:{overlap / boxes[hit].area:.4f}")
            lon, lat = TO_GRID.transform(centroid.x, centroid.y, direction="INVERSE")
            start, end = starts[index], ends[index]
            duration = (datetime.fromisoformat(end) - datetime.fromisoformat(start)).days + 1 if start and end else ""
            writer.writerow([uuids[index], start, end, duration, round(areas[index], 4) if areas[index] is not None else "",
                             round(lon, 5), round(lat, 5), round(share, 4), centroid_cell, len(listing), ";".join(listing)])
            kept += 1
    receipt = {"created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "source": {"title": "Groundsource: A Dataset of Flood Events from News", "doi": "10.5281/zenodo.18647054",
                          "record": "https://zenodo.org/records/18647054", "license": "CC-BY-4.0",
                          "file": "raw/groundsource/groundsource_2026.parquet", "md5_published": "cd1b5de6508f7aad8e1d1d0dd4cecea6"},
               "selection": "event area at least 50% inside the LSIB Pakistan boundary (points: inside)",
               "events_in_file": len(geometries), "events_near_pakistan": int(len(near)), "events_kept": kept, "invalid_geometries": invalid,
               "output": OUTPUT.relative_to(DATASET).as_posix(), "output_sha256": None}
    import hashlib
    receipt["output_sha256"] = hashlib.sha256(OUTPUT.read_bytes()).hexdigest()
    (DATASET / "processed" / "groundsource_pakistan_receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"kept {kept:,} Pakistan events -> {OUTPUT}", flush=True)


if __name__ == "__main__":
    main()
