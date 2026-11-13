"""Shared Earth Engine settings for the Pakistan 20 km flash-flood grid.

The grid is a fixed 20 km x 20 km grid in EASE-Grid 2.0 (EPSG:6933, equal area), snapped to
multiples of 20 km and covering the LSIB Pakistan boundary (USDOS/LSIB_SIMPLE/2017), which
includes Azad Jammu and Kashmir and Gilgit-Baltistan. Earth Engine aggregates every input to
these cells (``reduceResolution`` area means or maxima) and returns them as arrays through
``ee.data.computePixels``, so no point sampling or interpolation is involved.
"""
from __future__ import annotations

import hashlib
import io
import json
import time
from pathlib import Path

import ee
import numpy as np

PROJECT = "n8n-gmail-send-503521"
CRS = "EPSG:6933"          # recorded in metadata; Earth Engine is given the equivalent WKT below
CELL_M = 20000
# Earth Engine cannot parse the EPSG:6933 code, so it receives the projection as WKT1 (checked to
# reproduce pyproj's EPSG:6933 coordinates exactly).
WKT = ('PROJCS["WGS 84 / NSIDC EASE-Grid 2.0 Global",GEOGCS["WGS 84",DATUM["WGS_1984",SPHEROID["WGS 84",6378137,'
       '298.257223563,AUTHORITY["EPSG","7030"]],AUTHORITY["EPSG","6326"]],PRIMEM["Greenwich",0,AUTHORITY["EPSG","8901"]],'
       'UNIT["degree",0.0174532925199433,AUTHORITY["EPSG","9122"]],AUTHORITY["EPSG","4326"]],'
       'PROJECTION["Cylindrical_Equal_Area"],PARAMETER["standard_parallel_1",30],PARAMETER["central_meridian",0],'
       'PARAMETER["false_easting",0],PARAMETER["false_northing",0],UNIT["metre",1,AUTHORITY["EPSG","9001"]],'
       'AXIS["Easting",EAST],AXIS["Northing",NORTH],AUTHORITY["EPSG","6933"]]')


def projection(scale=None):
    proj = ee.Projection(WKT)
    return proj.atScale(scale) if scale else proj
DATASET = Path(__file__).resolve().parents[1]
GEE_DIR = DATASET / "raw" / "gee"
GRID_JSON = GEE_DIR / "grid" / "grid_definition.json"
CHENAB_DISTRICTS = ["Sialkot", "Gujrat", "Gujranwala", "Mandi Bahauddin", "Hafizabad", "Chiniot", "Jhang"]


def initialize():
    ee.Initialize(project=PROJECT)


def pakistan():
    return ee.FeatureCollection("USDOS/LSIB_SIMPLE/2017").filter(ee.Filter.eq("country_na", "Pakistan"))


def chenab_districts():
    return (ee.FeatureCollection("FAO/GAUL/2025/level2")
            .filter(ee.Filter.eq("GAUL0_NAME", "Pakistan"))
            .filter(ee.Filter.inList("GAUL2_NAME", CHENAB_DISTRICTS)))


def grid_spec(grid=None):
    """computePixels grid for the full bounding box of the 20 km grid."""
    grid = grid or json.loads(GRID_JSON.read_text(encoding="utf-8"))
    return {"dimensions": {"width": grid["width"], "height": grid["height"]},
            "affineTransform": {"scaleX": CELL_M, "shearX": 0, "translateX": grid["x0"],
                                "shearY": 0, "scaleY": -CELL_M, "translateY": grid["y1"]},
            "crsWkt": WKT}


def compute(image, grid=None, retries=5):
    """Return a structured NumPy array (height x width) with one field per band."""
    request = {"expression": image, "fileFormat": "NUMPY_NDARRAY", "grid": grid_spec(grid)}
    for attempt in range(retries):
        try:
            return ee.data.computePixels(request)
        except Exception as error:  # Earth Engine raises plain exceptions for quota/timeout
            transient = any(word in str(error).lower() for word in ("timed out", "timeout", "quota", "rate", "429", "500", "502", "503", "internal", "unavailable", "connection"))
            if attempt == retries - 1 or not transient:
                raise
            wait = 20 * (attempt + 1)
            print(f"  retry {attempt + 1} after error: {str(error)[:160]} (waiting {wait}s)", flush=True)
            time.sleep(wait)


def compute_tiled(image, band, grid=None, tiles=(3, 3)):
    """Compute one band over the grid in tiles (keeps each request within Earth Engine memory)."""
    grid = grid or json.loads(GRID_JSON.read_text(encoding="utf-8"))
    out = np.full((grid["height"], grid["width"]), np.nan, dtype=np.float32)
    row_edges = np.linspace(0, grid["height"], tiles[0] + 1).astype(int)
    col_edges = np.linspace(0, grid["width"], tiles[1] + 1).astype(int)
    for r0, r1 in zip(row_edges[:-1], row_edges[1:]):
        for c0, c1 in zip(col_edges[:-1], col_edges[1:]):
            sub = {"x0": grid["x0"] + c0 * CELL_M, "y1": grid["y1"] - r0 * CELL_M, "width": int(c1 - c0), "height": int(r1 - r0)}
            array = compute(image.select([band]), sub)
            out[r0:r1, c0:c1] = np.asarray(array[band], dtype=np.float32)
    return out


def to_float_bands(array, names):
    return {name: np.asarray(array[name], dtype=np.float32) for name in names}


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def save_npz(path, **arrays):
    """Write a compressed .npz atomically and return its SHA-256."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    buffer = io.BytesIO()
    np.savez_compressed(buffer, **arrays)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(buffer.getvalue())
    temporary.replace(path)
    return sha256_file(path)
