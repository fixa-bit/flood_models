"""Storage, geometry and provenance shared by the three command-line stages."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path



def now():
    return datetime.now(timezone.utc).isoformat()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8")
    temporary.replace(path)


def digest(path, algorithm="sha256"):
    h = hashlib.new(algorithm)
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def setup(description):
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "configs/trimmu_jhang.json"))
    parser.add_argument("--root", help="Override persistent project storage")
    return parser


def load(args):
    config_path = Path(args.config).resolve()
    cfg = json.loads(config_path.read_text(encoding="utf-8"))
    if args.root:
        root = Path(args.root).resolve()
    else:
        try:
            from google.colab import drive
        except ImportError:
            root = (config_path.parent / cfg["storage"]["local_root"]).resolve()
        else:
            drive.mount("/content/drive")
            root = Path(cfg["storage"]["colab_drive_root"])
    cfg["_config_dir"] = str(config_path.parent)
    cfg["_root"] = str(root)
    data = root / "datasets/exposure"
    for folder in ("raw/worldpop", "raw/osm", "raw/boundaries", "metadata", "validation_reports"):
        (data / folder).mkdir(parents=True, exist_ok=True)
    return cfg, data


def resolve(cfg, path):
    p = Path(path)
    return p if p.is_absolute() else (Path(cfg["_config_dir"]) / p).resolve()


def boundary_path(cfg, data, level):
    existing = cfg.get("existing_boundaries", {}).get(level)
    if existing:
        return resolve(cfg, existing)
    if cfg.get("boundary_provider") == "hdx_cod":
        source = manifest(data)["sources"].get(level, {})
        if source.get("source_metadata", {}).get("provider") != "OCHA COD-AB / HDX":
            raise ValueError("Download configured HDX boundaries first")
        return data / source["raw_path"]
    return data / f"raw/boundaries/PAK_{level}.geojson"


def area(cfg, data):
    import geopandas as gpd
    from shapely.geometry import box
    a = cfg["area"]
    if not a["name"] or any(c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in a["name"]):
        raise ValueError("area.name must be a safe folder name")
    mode = a["mode"]
    if mode == "bbox":
        west, south, east, north = a["bbox"]
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("Invalid WGS84 [west, south, east, north] bbox")
        return box(west, south, east, north)
    if mode == "polygon":
        frame = gpd.read_file(resolve(cfg, a["path"]), **({"layer": a["layer"]} if a.get("layer") else {}))
    elif mode in ("admin", "pakistan"):
        level = "ADM0" if mode == "pakistan" else a["level"]
        frame = gpd.read_file(boundary_path(cfg, data, level))
        if cfg.get("boundary_provider") == "hdx_cod" and not cfg.get("existing_boundaries", {}).get(level):
            from hdx_boundaries import normalize
            frame = normalize(frame, level)
        if mode == "admin":
            frame = frame[frame[a.get("field", "shapeName")] == a["value"]]
    else:
        raise ValueError("area.mode must be bbox, polygon, admin or pakistan")
    if frame.empty or frame.crs is None:
        raise ValueError("Study area is empty or has no CRS; do not guess its coordinates")
    geom = frame.to_crs(4326).geometry.union_all()
    if geom.geom_type not in ("Polygon", "MultiPolygon") or not geom.is_valid:
        raise ValueError("Study area must contain valid polygons; repair and verify it explicitly")
    return geom


def output_paths(cfg, data):
    base = data / "processed" / cfg["area"]["name"]
    paths = {name: base / name / (name + (".geojson" if name in ("hospitals", "schools", "critical_infrastructure") else ".gpkg"))
             for name in ("roads", "buildings", "hospitals", "schools", "settlements", "critical_infrastructure", "boundaries")}
    paths["population"] = base / "population/population_2025.tif"
    for path in paths.values():
        path.parent.mkdir(parents=True, exist_ok=True)
    return paths


def manifest(data):
    p = data / "metadata/manifest.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"schema_version": 1, "sources": {}, "runs": {}}


def record_area(cfg, geom):
    from shapely.geometry import mapping
    return {"selection": cfg["area"], "crs": "EPSG:4326", "bbox": list(geom.bounds), "geometry": mapping(geom)}
