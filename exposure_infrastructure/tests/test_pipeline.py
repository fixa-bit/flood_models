"""Small synthetic fixtures test GIS invariants, never used as acquired data."""
import sys
from contextlib import ExitStack
from pathlib import Path

import fiona
import osmium
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import box, shape

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from preprocess import clip_population, Layer, Extractor
from audit import audit_vector
from download import download


def test_hdx_normalization_preserves_provenance_and_station_selection():
    import geopandas as gpd
    from hdx_boundaries import normalize
    frame = gpd.GeoDataFrame({'adm2_name':['Jhang'], 'adm2_pcode':['PK-JH'], 'version':['01']}, geometry=[box(71.6,30.5,72.9,31.8)], crs=4326)
    normalized = normalize(frame, 'ADM2')
    assert normalized.shapeName.tolist() == ['Jhang']
    assert normalized.shapeID.tolist() == ['PK-JH']
    assert normalized['version'].tolist() == ['01']
    assert 'adm2_pcode' in normalized
    assert 'shapeID' not in frame


def test_reference_alignment_is_separate_from_model_alignment(tmp_path):
    import geopandas as gpd
    from audit import flood_alignment
    path = tmp_path / 'published.gpkg'
    gpd.GeoDataFrame(geometry=[box(72,31,72.2,31.2)],crs=4326).to_file(path,layer='water')
    cfg = {'_config_dir':str(tmp_path), 'flood_extents':[], 'flood_reference_extents':[{'path':str(path),'layer':'water'}]}
    assert flood_alignment(cfg, box(71.9,30.9,72.3,31.3))[0]['status'] == 'NOT_CHECKED'
    assert flood_alignment(cfg, box(71.9,30.9,72.3,31.3),references=True)[0]['status'] == 'COMPATIBLE_EXTENT'
    assert flood_alignment(cfg, box(73,32,74,33),references=True)[0]['status'] == 'BLOCKED'


def test_population_keeps_native_values_nodata_grid(tmp_path):
    source, target = tmp_path / "original.tif", tmp_path / "clip.tif"
    data = np.array([[1, 2, 3, 4], [5, -99999, 7, 8], [9, 10, 11, 12], [13, 14, 15, 16]], dtype="float32")
    transform = from_origin(0, 4, 1, 1)
    with rasterio.open(source, "w", driver="GTiff", height=4, width=4, count=1, dtype="float32", crs=4326, transform=transform, nodata=-99999) as dst:
        dst.write(data, 1)
    result = clip_population(source, target, box(1, 1, 3, 3))
    with rasterio.open(target) as src:
        np.testing.assert_array_equal(src.read(1), data[1:3, 1:3])
        assert src.nodata == -99999 and src.res == (1, 1)
        assert src.transform == from_origin(1, 3, 1, 1)
    assert result["population_sum"] == 28
    assert result["valid_cells"] == 3


def test_osm_node_connectivity_tags_polygons_and_clipping(tmp_path):
    osm = tmp_path / "fixture.osm"
    osm.write_text('''<osm version="0.6">
<node id="1" lat="1" lon="-1"/><node id="2" lat="1" lon="1"/>
<node id="3" lat="1" lon="3"/><node id="4" lat="-1" lon="1"/>
<node id="5" lat="3" lon="1"/>
<node id="10" lat="0.2" lon="0.2"/><node id="11" lat="0.2" lon="0.4"/>
<node id="12" lat="0.4" lon="0.4"/><node id="13" lat="0.4" lon="0.2"/>
<node id="20" lat="1.5" lon="1.5"><tag k="amenity" v="hospital"/><tag k="name" v="Test hospital"/></node>
<way id="100"><nd ref="1"/><nd ref="2"/><nd ref="3"/><tag k="highway" v="primary"/><tag k="oneway" v="-1"/><tag k="bridge" v="yes"/><tag k="access:conditional" v="no @ (flood)"/></way>
<way id="101"><nd ref="4"/><nd ref="5"/><tag k="highway" v="secondary"/></way>
<way id="200"><nd ref="10"/><nd ref="11"/><nd ref="12"/><nd ref="13"/><nd ref="10"/><tag k="building" v="school"/><tag k="amenity" v="school"/></way>
</osm>''', encoding="utf-8")
    names = ("roads", "buildings", "hospitals", "schools", "settlements", "critical_infrastructure")
    paths = {name: tmp_path / (name + ".gpkg") for name in names}
    geom = box(0, 0, 2, 2)
    with ExitStack() as stack:
        layers = {name: Layer(stack, name, paths[name]) for name in names}
        restrictions = stack.enter_context((tmp_path / "restrictions.jsonl").open("w"))
        handler = Extractor(geom, layers, restrictions)
        handler.apply_file(str(osm), locations=True, filters=[osmium.filter.KeyFilter("highway", "building", "amenity", "healthcare", "place", "emergency", "type")])
        for layer in layers.values():
            layer.flush()
    with fiona.open(paths["roads"]) as src:
        roads = list(src)
        assert len(roads) == 3
        primary = [r for r in roads if r["properties"]["osm_id"] == "100"]
        assert primary[0]["properties"]["v"] == "node/2"
        assert primary[1]["properties"]["u"] == "node/2"
        assert primary[0]["properties"]["u"].startswith("boundary/")
        assert all(r["properties"]["direction"] == "reverse" for r in primary)
        assert "access:conditional" in primary[0]["properties"]["tags_json"]
        # Crossing road has no shared source node at the bridge intersection.
        secondary = [r for r in roads if r["properties"]["osm_id"] == "101"][0]
        assert "node/2" not in (secondary["properties"]["u"], secondary["properties"]["v"])
        assert all(geom.covers(shape(r["geometry"])) for r in roads)
    for name in ("buildings", "schools", "hospitals"):
        with fiona.open(paths[name]) as src:
            assert len(src) == 1
    report = audit_vector(paths["roads"], "roads", geom, tmp_path)
    assert report["status"] == "READY"
    assert report["duplicate_ids"] == 0


class Response:
    def __init__(self, data, status, headers):
        self.data, self.status_code, self.headers = data, status, headers
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def raise_for_status(self):
        pass
    def iter_content(self, size):
        yield self.data


def test_resume_when_server_ignores_range_restarts_safely(tmp_path):
    import json
    path = tmp_path / "asset.bin"
    path.with_suffix(".bin.part").write_bytes(b"old")
    path.with_suffix(".bin.part.json").write_text(json.dumps({"url": "https://example.test/data", "validator": '"a"'}))
    class Server:
        def get(self, url, **kwargs):
            assert kwargs["headers"]["Range"] == "bytes=3-"
            return Response(b"complete", 200, {"Content-Length": "8", "ETag": '"b"'})
    receipt = download(Server(), "https://example.test/data", path)
    assert path.read_bytes() == b"complete"
    assert receipt["bytes"] == 8


def test_valid_resume_appends_only_matching_content_range(tmp_path):
    import json
    path = tmp_path / "asset.bin"
    path.with_suffix(".bin.part").write_bytes(b"abc")
    path.with_suffix(".bin.part.json").write_text(json.dumps({"url": "https://example.test/data", "validator": '"a"'}))
    class Server:
        def get(self, url, **kwargs):
            return Response(b"def", 206, {"Content-Range": "bytes 3-5/6", "ETag": '"a"'})
    download(Server(), "https://example.test/data", path)
    assert path.read_bytes() == b"abcdef"


def test_multipolygon_members_survive_callback_filter(tmp_path):
    osm = tmp_path / "relation.osm"
    osm.write_text('''<osm version="0.6">
<node id="1" lat="0" lon="0"/><node id="2" lat="0" lon="4"/>
<node id="3" lat="4" lon="4"/><node id="4" lat="4" lon="0"/>
<node id="5" lat="1" lon="1"/><node id="6" lat="1" lon="2"/>
<node id="7" lat="2" lon="2"/><node id="8" lat="2" lon="1"/>
<way id="10"><nd ref="1"/><nd ref="2"/><nd ref="3"/><nd ref="4"/><nd ref="1"/></way>
<way id="11"><nd ref="5"/><nd ref="6"/><nd ref="7"/><nd ref="8"/><nd ref="5"/></way>
<relation id="99"><member type="way" ref="10" role="outer"/><member type="way" ref="11" role="inner"/><tag k="type" v="multipolygon"/><tag k="building" v="hospital"/><tag k="amenity" v="hospital"/></relation>
</osm>''', encoding="utf-8")
    names = ("roads", "buildings", "hospitals", "schools", "settlements", "critical_infrastructure")
    with ExitStack() as stack:
        layers = {name: Layer(stack, name, tmp_path / (name + ".gpkg")) for name in names}
        restrictions = stack.enter_context((tmp_path / "restrictions.jsonl").open("w"))
        handler = Extractor(box(-1, -1, 5, 5), layers, restrictions)
        handler.apply_file(str(osm), locations=True, filters=[osmium.filter.KeyFilter("building", "amenity", "type")])
        for layer in layers.values():
            layer.flush()
    with fiona.open(tmp_path / "buildings.gpkg") as src:
        features = list(src)
        assert len(features) == 1
        assert features[0]["properties"]["osm_type"] == "relation"
        assert shape(features[0]["geometry"]).area == 15
    with fiona.open(tmp_path / "hospitals.gpkg") as src:
        assert len(src) == 1
