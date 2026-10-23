"""Clip population without resampling; stream complete OSM PBF into GIS layers."""
import json
from contextlib import ExitStack

import fiona
import geopandas as gpd
import numpy as np
import osmium
import rasterio
from pyproj import Geod
from rasterio.features import geometry_mask, geometry_window
from rasterio.windows import Window
from rasterio.warp import transform_geom
from shapely import make_valid, wkb
from shapely.geometry import mapping, shape, Point, LineString
from shapely.prepared import prep

from common import setup, load, area, output_paths, manifest, write_json, now, record_area, boundary_path


def clip_population(source, destination, geom):
    # Windowed processing also supports the full Pakistan raster without a full-band read.
    total, valid, masked, negative = 0.0, 0, 0, 0
    with rasterio.open(source) as src:
        if src.crs is None or src.nodata is None or src.count != 1:
            raise ValueError("Population raster must have a CRS, nodata and a single count band")
        polygon = transform_geom("EPSG:4326", src.crs, mapping(geom))
        win = geometry_window(src, [polygon])
        profile = src.profile.copy()
        profile.update(width=int(win.width), height=int(win.height), transform=src.window_transform(win),
                       tiled=True, blockxsize=256, blockysize=256, compress="deflate", BIGTIFF="IF_SAFER")
        with rasterio.open(destination, "w", **profile) as dst:
            dst.update_tags(**src.tags())
            dst.update_tags(1, **src.tags(1))
            dst.set_band_description(1, src.descriptions[0] or "2025 population counts (people per cell)")
            for _, outwin in dst.block_windows(1):
                inwin = Window(outwin.col_off + win.col_off, outwin.row_off + win.row_off, outwin.width, outwin.height)
                values = src.read(1, window=inwin, masked=True)
                inside = geometry_mask([polygon], out_shape=values.shape, transform=dst.window_transform(outwin), invert=True, all_touched=False)
                mask = np.ma.getmaskarray(values) | ~inside
                result = np.ma.array(values.data, mask=mask)
                total += float(result.sum(dtype="float64")) if result.count() else 0
                valid += int(result.count())
                masked += int((inside & np.ma.getmaskarray(values)).sum())
                negative += int(((values.data < 0) & ~mask).sum())
                dst.write(result.filled(src.nodata), 1, window=outwin)
    return {"population_sum": total, "valid_cells": valid, "nodata_cells_inside_area": masked,
            "negative_cells": negative, "resampling": "none", "clip_rule": "pixel centre inside AOI; fractional boundary cells not apportioned"}


TAG_COLUMNS = ["name", "highway", "building", "amenity", "healthcare", "place", "bridge", "tunnel", "oneway", "access", "vehicle", "motor_vehicle", "motorcar", "foot", "bicycle", "service", "surface", "maxspeed", "lanes", "layer", "junction", "operator", "emergency"]
GEO = Geod(ellps="WGS84")


class Layer:
    def __init__(self, stack, name, path):
        props = {key: "str" for key in TAG_COLUMNS + ["osm_type", "osm_id", "feature_id", "tags_json", "u", "v", "direction"]}
        props["length_m"] = "float"
        driver = "GeoJSON" if path.suffix == ".geojson" else "GPKG"
        options = {"layer": name} if driver == "GPKG" else {}
        self.writer = stack.enter_context(fiona.open(path, "w", driver=driver, crs="EPSG:4326", schema={"geometry": "Unknown", "properties": props}, **options))
        self.count = 0
        self.buffer = []
        self.seen = set()

    def put(self, geom, kind, ident, tags, suffix="", **extra):
        key = f"{kind}/{ident}{suffix}"
        if key in self.seen:
            return
        self.seen.add(key)
        properties = {field: tags.get(field) for field in TAG_COLUMNS}
        properties.update(osm_type=kind, osm_id=str(ident), feature_id=key, tags_json=json.dumps(tags, ensure_ascii=False), u=None, v=None, direction=None, length_m=None)
        properties.update(extra)
        self.buffer.append({"geometry": mapping(geom), "properties": properties})
        self.count += 1
        if len(self.buffer) >= 1000:
            self.flush()

    def flush(self):
        self.writer.writerecords(self.buffer)
        self.buffer.clear()


class Extractor(osmium.SimpleHandler):
    def __init__(self, geom, layers, restrictions):
        super().__init__()
        self.geom, self.prepared, self.layers = geom, prep(geom), layers
        self.factory = osmium.geom.WKBFactory()
        self.restrictions = restrictions
        self.errors = {"invalid_node": 0, "invalid_way": 0, "invalid_area": 0, "repaired": 0}
        self.examples = []

    def failed(self, kind, ident, exc):
        self.errors[kind] += 1
        if len(self.examples) < 20:
            self.examples.append({"type": kind, "id": ident, "error": str(exc)})

    def targets(self, tags):
        names = []
        if tags.get("building") not in (None, "no"):
            names.append("buildings")
        if tags.get("amenity") in ("hospital", "clinic", "doctors") or tags.get("healthcare") in ("hospital", "clinic", "doctor", "centre"):
            names.append("hospitals")
        if tags.get("amenity") in ("school", "college", "university", "kindergarten"):
            names.append("schools")
        if tags.get("place") in ("city", "town", "village", "hamlet", "isolated_dwelling", "suburb", "neighbourhood"):
            names.append("settlements")
        if tags.get("amenity") in ("fire_station", "police", "shelter", "pharmacy") or tags.get("emergency"):
            names.append("critical_infrastructure")
        return names

    def emit(self, geom, kind, ident, tags):
        if not self.prepared.intersects(geom):
            return
        if not geom.is_valid:
            geom = make_valid(geom)
            self.errors["repaired"] += 1
        clipped = geom.intersection(self.geom)
        if clipped.is_empty:
            return
        for name in self.targets(tags):
            if name == "buildings" and clipped.geom_type not in ("Polygon", "MultiPolygon"):
                continue
            self.layers[name].put(clipped, kind, ident, tags)

    def node(self, node):
        if len(node.tags) == 0:
            return
        tags = dict(node.tags)
        if not self.targets(tags):
            return
        try:
            self.emit(Point(node.location.lon, node.location.lat), "node", node.id, tags)
        except (osmium.InvalidLocationError, ValueError) as exc:
            self.failed("invalid_node", node.id, exc)

    def way(self, way):
        if not way.tags.get("highway"):
            return
        tags = dict(way.tags)
        if "highway" not in tags or tags.get("area") == "yes":
            return
        try:
            coordinates = [(n.lon, n.lat) for n in way.nodes]
        except osmium.InvalidLocationError as exc:
            self.failed("invalid_way", way.id, exc)
            return
        if len(coordinates) < 2 or not self.prepared.intersects(LineString(coordinates)):
            return
        direction = "reverse" if tags.get("oneway") == "-1" else "forward" if tags.get("oneway") in ("yes", "1", "true") or (tags.get("junction") == "roundabout" and tags.get("oneway") not in ("no", "0", "false")) else "bidirectional"
        for index, (p, q) in enumerate(zip(coordinates, coordinates[1:])):
            if p == q:
                continue
            segment = LineString([p, q]).intersection(self.geom)
            parts = [segment] if segment.geom_type == "LineString" else list(getattr(segment, "geoms", []))
            for part_index, part in enumerate(parts):
                if part.geom_type != "LineString" or part.is_empty or part.length == 0:
                    continue
                ends = [tuple(part.coords[0]), tuple(part.coords[-1])]
                def endpoint(pt, orig, ref):
                    return f"node/{ref}" if pt == orig else "boundary/" + "/".join(float(c).hex() for c in pt)
                u = endpoint(ends[0], p, way.nodes[index].ref)
                v = endpoint(ends[1], q, way.nodes[index + 1].ref)
                self.layers["roads"].put(part, "way", way.id, tags, f"/{index}/{part_index}", u=u, v=v, direction=direction, length_m=abs(GEO.geometry_length(part)))

    def area(self, a):
        tags = dict(a.tags)
        if not self.targets(tags):
            return
        try:
            geom = wkb.loads(self.factory.create_multipolygon(a), hex=True)
            self.emit(geom, "way" if a.from_way() else "relation", a.orig_id(), tags)
        except (osmium.InvalidLocationError, RuntimeError, ValueError) as exc:
            self.failed("invalid_area", a.orig_id(), exc)

    def relation(self, rel):
        if rel.tags.get("type") == "restriction":
            self.restrictions.write(json.dumps({"osm_type": "relation", "osm_id": rel.id, "tags": dict(rel.tags), "members": [{"type": m.type, "ref": m.ref, "role": m.role} for m in rel.members]}, ensure_ascii=False) + "\n")


def prepare_boundaries(cfg, data, geom, path):
    results = {}
    for level in ("ADM1", "ADM2"):
        frame = gpd.read_file(boundary_path(cfg, data, level))
        if cfg.get("boundary_provider") == "hdx_cod" and not cfg.get("existing_boundaries", {}).get(level):
            from hdx_boundaries import normalize
            frame = normalize(frame, level)
        if frame.crs is None or not frame.geometry.is_valid.all():
            raise ValueError(f"{level} CRS/geometry invalid; verify boundary source before changing it")
        selected = frame.to_crs(4326)
        selected = selected[selected.intersects(geom)].copy()
        overlap = selected.geometry.intersection(geom)
        # Adjacent districts sharing only an edge are context neighbours, not exposure polygons.
        selected = selected[[not g.is_empty and g.area > 0 for g in overlap]].copy()
        selected["source_level"] = level
        selected["source_provider"] = "existing" if cfg.get("existing_boundaries", {}).get(level) else cfg.get("boundary_provider", "geoBoundaries gbOpen")
        selected.to_file(path, layer=level + "_context", driver="GPKG")
        selected.geometry = selected.geometry.intersection(geom)
        selected.to_file(path, layer=level, driver="GPKG")
        results[level + "_count"] = len(selected)
    return results


def run(cfg, data, vectors_only=False, population_only=False, boundaries_only=False):
    geom = area(cfg, data)
    write_json(data / f"metadata/{cfg['area']['name']}_study_area.geojson", {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": cfg["area"], "geometry": mapping(geom)}]})
    paths = output_paths(cfg, data)
    m = manifest(data)
    sources = m["sources"]
    if boundaries_only:
        previous = m["runs"].get(cfg["area"]["name"], {})
        if previous.get("area", {}).get("selection") != cfg["area"]:
            raise ValueError("Run all preprocessing first for a new study area")
        result = prepare_boundaries(cfg, data, geom, paths["boundaries"])
        result.update(path=paths["boundaries"].relative_to(data).as_posix(), bytes=paths["boundaries"].stat().st_size, crs="EPSG:4326")
        previous["datasets"]["boundaries"] = result
        previous["source_snapshots"].update({k: sources[k] for k in ("ADM1", "ADM2")})
        previous["processed_at"] = now()
        write_json(data / "metadata/manifest.json", m)
        return
    if population_only and m["runs"].get(cfg["area"]["name"], {}).get("area", {}).get("selection") != cfg["area"]:
        raise ValueError("Run vectors for this same area before population-only processing")
    for key in (("worldpop",) if population_only else ("osm", "ADM1", "ADM2") if vectors_only else ("worldpop", "osm", "ADM1", "ADM2")):
        if sources.get(key, {}).get("status") not in ("downloaded", "existing"):
            raise ValueError(f"Download {key} first")
    results = {}
    if not vectors_only:
        results["population"] = clip_population(data / sources["worldpop"]["raw_path"].replace("\\", "/"), paths["population"], geom)
    if population_only:
        previous = m["runs"].get(cfg["area"]["name"], {})
        with rasterio.open(paths["population"]) as raster:
            results["population"].update(path=paths["population"].relative_to(data).as_posix(), bytes=paths["population"].stat().st_size, crs=raster.crs.to_string())
        previous["datasets"].update(results)
        previous["source_snapshots"]["worldpop"] = sources["worldpop"]
        previous["processed_at"] = now()
        write_json(data / "metadata/manifest.json", m)
        print(json.dumps(results, indent=2), flush=True)
        return
    layers = {}
    print("Extracting OSM; assembling multipolygons and preserving all source tags...", flush=True)
    with ExitStack() as stack:
        for name in ("roads", "buildings", "hospitals", "schools", "settlements", "critical_infrastructure"):
            layers[name] = Layer(stack, name, paths[name])
        restriction_path = paths["roads"].parent / "turn_restrictions_pakistan.jsonl"
        restrictions = stack.enter_context(restriction_path.open("w", encoding="utf-8"))
        handler = Extractor(geom, layers, restrictions)
        index = cfg.get("osm_location_index", "disk")
        if index == "disk":
            index_path = (data / "metadata/osm_node_locations.idx").resolve()
            index_path.unlink(missing_ok=True)  # Derived cache only; never delete raw data.
            index = "sparse_file_array," + str(index_path)
        # Location caching/area assembly run before the tag filter. No way nodes
        # or multipolygon member geometry are lost; only Python callbacks shrink.
        handler.apply_file(str(data / sources["osm"]["raw_path"].replace("\\", "/")), locations=True, idx=index,
                           filters=[osmium.filter.KeyFilter("highway", "building", "amenity", "healthcare", "place", "emergency", "type")])
        for name, layer in layers.items():
            layer.flush()
            results[name] = {"feature_count": layer.count}
    if cfg.get("osm_location_index", "disk") == "disk":
        # Windows may retain the native memory mapping until process exit. A cache
        # cleanup failure must not discard the final buffered GIS features.
        try:
            index_path.unlink(missing_ok=True)
        except PermissionError:
            print("OSM node cache remains mapped; retained for cleanup after process exit.", flush=True)
    write_json(data / f"validation_reports/{cfg['area']['name']}_extraction.json", {"counts": handler.errors, "examples": handler.examples})
    results["boundaries"] = prepare_boundaries(cfg, data, geom, paths["boundaries"])
    for name, path in paths.items():
        if name not in results:
            continue
        results[name].update(path=path.relative_to(data).as_posix(), bytes=path.stat().st_size, crs="EPSG:4326")
    if "population" in results:
        with rasterio.open(paths["population"]) as raster:
            results["population"]["crs"] = raster.crs.to_string()
    m = manifest(data)
    m["runs"][cfg["area"]["name"]] = {"processed_at": now(), "area": record_area(cfg, geom), "datasets": results, "source_snapshots": sources,
        "limitations": ["OSM absence is not proof of absence; completeness requires external reference data", "Road edges preserve direction/access and node topology; router must apply access rules, conditional tags, barriers and supplied turn restrictions", "Source-ID duplicates removed; coincident distinct OSM objects are retained for review", "Administrative polygons are source-specific representations; no disputed-area reconciliation performed"]}
    write_json(data / "metadata/manifest.json", m)
    print(json.dumps(results, indent=2), flush=True)


if __name__ == "__main__":
    parser = setup(__doc__)
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--vectors-only", action="store_true", help="Prepare downloaded OSM/boundaries while population is pending")
    group.add_argument("--population-only", action="store_true", help="Add population to an already processed identical study area")
    group.add_argument("--boundaries-only", action="store_true", help="Refresh administrative layers for an already processed identical study area")
    args = parser.parse_args()
    run(*load(args), vectors_only=args.vectors_only, population_only=args.population_only, boundaries_only=args.boundaries_only)
