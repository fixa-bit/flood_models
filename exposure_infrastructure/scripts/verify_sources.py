"""Download independent references and measure coverage; never invent OSM features."""
import csv
import gzip
import io
import json
import math
import re
import zipfile
import hashlib
import xml.etree.ElementTree as ET
from pathlib import Path

import fiona
import geopandas as gpd
import osmium
from shapely import make_valid, is_valid_reason
from shapely.geometry import box, shape, mapping, Point
from shapely.prepared import prep

from common import setup, load, area, manifest, write_json, now, digest, output_paths
from download import session, get_json, download


def compare_buildings(cfg, data, target):
    from pyproj import Transformer
    from shapely.ops import transform
    osm = gpd.read_file(output_paths(cfg,data)['buildings'])
    metric = osm.estimate_utm_crs() if not osm.empty else gpd.GeoSeries([area(cfg,data)],crs=4326).estimate_utm_crs()
    candidates = osm.to_crs(metric).geometry.buffer(10) if not osm.empty else None
    idx = candidates.sindex if candidates is not None else None
    convert = Transformer.from_crs(4326,metric,always_xy=True).transform
    count=matched=0
    with fiona.open(target) as refs:
        for feature in refs:
            count+=1
            if idx is not None:
                g=transform(convert,shape(feature['geometry']))
                matched += bool(len(idx.query(g,predicate='intersects')))
    return {'feature_count':count, 'osm_buildings':len(osm), 'reference_buildings_near_osm':matched,
            'reference_buildings_without_nearby_osm':count-matched,
            'osm_reference_match_fraction':matched/count if count else None}


def quadkey_bounds(q):
    x = y = 0
    for digit in q:
        x = x*2 + (int(digit) & 1)
        y = y*2 + int(digit)//2
    n = 2**len(q)
    lat = lambda y: math.degrees(math.atan(math.sinh(math.pi*(1-2*y/n))))
    return box(x/n*360-180, lat(y+1), (x+1)/n*360-180, lat(y))


def reference_buildings(cfg, data, geom):
    s = session()
    readme_url = 'https://raw.githubusercontent.com/microsoft/GlobalMLBuildingFootprints/main/README.md'
    r = s.get(readme_url, timeout=90); r.raise_for_status()
    links = re.findall(r'https://[^\s)]+dataset-links.csv', r.text)
    if not links:
        raise ValueError('Official Microsoft index not discovered')
    url = links[0]
    release = url.split('/')[-2]
    root = data / 'raw/microsoft_buildings' / release
    index = root / 'dataset-links.csv'
    download(s, url, index)
    tiles = [r for r in csv.DictReader(index.open(encoding='utf-8')) if r['Location']=='Pakistan' and quadkey_bounds(r['QuadKey']).intersects(geom)]
    if not tiles:
        raise ValueError('No Microsoft reference tiles overlap study area')
    target = data / 'processed' / cfg['area']['name'] / 'reference_buildings/buildings.gpkg'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.unlink(missing_ok=True)  # Only this derived output is replaced.
    schema = {'geometry':'Unknown', 'properties':{'reference_id':'str','quadkey':'str','source_file':'str','source_row':'int','tags_json':'str'}}
    receipts=[]; count=0; invalid=0
    selected = prep(geom)
    west,south,east,north=geom.bounds
    with fiona.open(target, 'w', driver='GPKG', layer='reference_buildings', crs='EPSG:4326', schema=schema) as out:
        for tile in tiles:
            path = root / (tile['QuadKey'] + '.geojsonl.gz')
            receipt = download(s, tile['Url'], path)
            receipts.append(dict(tile, raw_path=path.relative_to(data).as_posix(), **receipt))
            batch=[]
            with gzip.open(path, 'rt', encoding='utf-8') as stream:
                for row, line in enumerate(stream, 1):
                    feature=json.loads(line)
                    geometry=feature['geometry']
                    # Cheap ring bounds reject distant tile detections before GEOS construction.
                    if geometry['type']=='Polygon':
                        ring=geometry['coordinates'][0]
                        xs=[c[0] for c in ring]; ys=[c[1] for c in ring]
                        if max(xs)<west or min(xs)>east or max(ys)<south or min(ys)>north:
                            continue
                    g=shape(geometry)
                    if not selected.intersects(g):
                        continue
                    if not g.is_valid:
                        invalid += 1
                        continue
                    if not selected.covers(g):
                        g=g.intersection(geom)
                    if g.is_empty or g.geom_type not in ('Polygon','MultiPolygon'):
                        continue
                    batch.append({'geometry':mapping(g), 'properties':{'reference_id':f"{tile['QuadKey']}/row/{row}", 'quadkey':tile['QuadKey'], 'source_file':tile['Url'], 'source_row':row, 'tags_json':json.dumps(feature.get('properties',{}))}})
                    count+=1
                    if len(batch)>=1000:
                        out.writerecords(batch); batch=[]
            out.writerecords(batch)
            print(f"Reference tile {tile['QuadKey']} complete; {count:,} district footprints retained so far",flush=True)
    comparison=compare_buildings(cfg,data,target)
    result={'status':'ASSESSED', 'source':readme_url, 'license':'CDLA-Permissive-2.0', 'release':release,
            'index_url':url, 'tiles':receipts, 'processed_path':target.relative_to(data).as_posix(),
            **comparison, 'invalid_reference_features_skipped':invalid, 'matching_distance_m':10,
            'method':'Independent footprint intersects OSM footprint buffered by 10 metres in local UTM. This measures mapping gaps, not validated detection accuracy.',
            'limitations':['Image-derived detections can contain omissions/false positives; not field-verified ground truth.',
                           'Imagery dates vary; upload date is not the observation date.',
                           'Reference IDs are explicitly derived tile/line identifiers, not OSM IDs.',
                           'Reference footprints are kept separately; they are not silently merged into OSM.']}
    return result


def flood_reference(cfg, data, geom):
    s=session()
    metadata=get_json(s, 'https://unosat.org/our_products/4197')['map_event']
    write_json(data / 'metadata/unosat_4197_source.json', metadata)
    url='https://unosat.org'+metadata['shp_link']
    archive=data / 'raw/flood_reference/unosat_4197' / Path(metadata['shp_link']).name
    receipt=download(s,url,archive)
    with zipfile.ZipFile(archive) as z:
        names=[n for n in z.namelist() if Path(n).name == 'VIIRS_20250826_20250907_FloodWaterExtent_PAK.shp']
    if len(names) != 1:
        raise ValueError('Expected dated VIIRS flood-water layer not found unambiguously')
    print('UNOSAT shapefiles:', names, flush=True)
    target=data / 'processed' / cfg['area']['name'] / 'flood_reference/unosat_4197.gpkg'
    target.parent.mkdir(parents=True,exist_ok=True)
    layers=[]; repairs=[]
    for i,name in enumerate(names):
        # GDAL reads the original archive; do not extract arbitrary archive paths.
        path=f'/vsizip/{archive.resolve().as_posix()}/{name}'
        with fiona.open(path) as src:
            if not src.crs:
                raise ValueError('UNOSAT layer CRS missing')
            from pyproj import Transformer
            from shapely.ops import transform
            convert=Transformer.from_crs(4326,src.crs,always_xy=True).transform
            bbox=transform(convert,geom).bounds
        frame=gpd.read_file(path,bbox=bbox,engine='fiona').to_crs(4326)
        if frame.empty:
            continue
        print(name, len(frame), list(frame.columns), flush=True)
        # Only polygonal water extent layers qualify, not roads, settlements or map AOIs.
        if not any(k in name.lower() for k in ('water','flood')) or not frame.geom_type.isin(['Polygon','MultiPolygon']).all():
            continue
        for row in frame.index[~frame.geometry.is_valid]:
            original=frame.loc[row,'geometry']
            fixed=make_valid(original)
            if fixed.geom_type not in ('Polygon','MultiPolygon') or not fixed.is_valid:
                raise ValueError(f'Water geometry repair changed dimensionality: {name}')
            repairs.append({'source_member':name,'source_row':int(row),'reason':is_valid_reason(original),
                            'method':'GEOS make_valid; raw archive unchanged',
                            'original_area_degrees2':original.area,'repaired_area_degrees2':fixed.area})
            frame.loc[row,'geometry']=fixed
        frame=frame[frame.intersects(geom)].copy()
        frame.geometry=frame.geometry.intersection(geom)
        frame=frame[~frame.geometry.is_empty]
        if frame.empty:
            continue
        layer=f'water_extent_{i}'
        frame['source_product']='UNOSAT 4197'
        frame.to_file(target,layer=layer,driver='GPKG')
        layers.append({'layer':layer,'source_member':name,'count':len(frame),'crs':'EPSG:4326'})
    if not layers:
        raise ValueError('No satellite-detected water polygons overlap this pilot')
    return {'status':'COMPATIBLE_REFERENCE_EXTENT','source':'https://unosat.org/products/4197',
            'observation_period':'2025-08-26/2025-09-07','resolution_m':375,
            'license':'UNOSAT terms of use; attribution required, see https://unosat.org/about-us',
            'raw_path':archive.relative_to(data).as_posix(), 'receipt':receipt,
            'path':target.relative_to(data).as_posix(), 'layers':layers, 'geometry_repairs':repairs,
            'limitations':'Preliminary satellite-detected water, not field validated. Historical reference, not user model output or guaranteed flood-only water.'}


def live_osm(cfg,data,geom):
    s=session()
    source=manifest(data)['sources']['osm']
    reader=osmium.io.Reader(str(data/source['raw_path']))
    stamp=reader.header().get('osmosis_replication_timestamp'); reader.close()
    if not stamp:
        raise ValueError('OSM extract timestamp unavailable')
    west,south,east,north=geom.bounds
    bounds=f'{south},{west},{north},{east}'
    query=f'''[out:json][timeout:180][date:"{stamp}"];
    (nwr[building]({bounds});way[highway]({bounds});nwr[amenity~"^(hospital|clinic|doctors|school|college|university|kindergarten|fire_station|police|shelter|pharmacy)$"]({bounds});nwr[healthcare]({bounds});nwr[emergency]({bounds});nwr[place~"^(village|town|city|hamlet|isolated_dwelling|suburb|neighbourhood)$"]({bounds}););out tags;'''
    errors=[]
    raw=data / 'raw/osm/verification' / f"{cfg['area']['name']}_{stamp[:10]}.json"
    query_path=raw.with_suffix('.query.json')
    for endpoint in ('https://overpass-api.de/api/interpreter','https://overpass.private.coffee/api/interpreter','https://maps.mail.ru/osm/tools/overpass/api/interpreter'):
        try:
            cached=json.loads(query_path.read_text(encoding='utf-8')) if query_path.exists() else {}
            if raw.exists() and cached.get('query') == query and cached.get('sha256') == digest(raw):
                payload=json.loads(raw.read_text(encoding='utf-8'))
                endpoint=cached['endpoint']
            else:
                response=s.post(endpoint,data={'data':query},timeout=(30,210));response.raise_for_status()
                payload=response.json()
            if payload.get('remark'):
                raise ValueError(payload['remark'])
            write_json(raw,payload)
            write_json(query_path,{'query':query,'endpoint':endpoint,'sha256':digest(raw),'retrieved_at':now()})
            remote={(e['type'],str(e['id'])) for e in payload['elements']}
            if cfg['area']['name'] not in manifest(data)['runs']:
                return {'status':'SOURCE_INVENTORY_DOWNLOADED','snapshot_timestamp':stamp,'raw_path':raw.relative_to(data).as_posix(),
                        'bbox_remote_unique_objects':len(remote),'reason':'Repeat after preprocessing has completed to compare extracted source IDs'}
            local=set()
            for name,path in output_paths(cfg,data).items():
                if name in ('population','boundaries'):
                    continue
                with fiona.open(path) as layer:
                    for f in layer:
                        p=dict(f['properties']); local.add((p['osm_type'],str(p['osm_id'])))
            missing=sorted(local-remote)
            return {'status':'SNAPSHOT_INVENTORY_CHECKED','endpoint':endpoint,'snapshot_timestamp':stamp,
                    'query':query,'raw_path':raw.relative_to(data).as_posix(),'sha256':digest(raw),
                    'local_unique_objects':len(local),'bbox_remote_unique_objects':len(remote),
                    'local_objects_absent_from_remote':missing[:100], 'absent_count':len(missing),
                    'bbox_remote_objects_not_clipped_locally':len(remote-local),
                    'method':'Same dated OSM snapshot; local AOI objects compared with independent Overpass bbox inventory. Bbox-only objects may be outside district; intersecting ways may have no vertices in bbox.',
                    'license':'ODbL-1.0; OpenStreetMap contributors',
                    'limitations':'Checks source inventory, not real-world completeness of roads or facilities.'}
        except Exception as exc:
            errors.append(f'{endpoint}: {exc}')
    return {'status':'NOT_CHECKED','errors':errors}


def locate_extraction_errors(cfg,data,geom):
    path=data/f"validation_reports/{cfg['area']['name']}_extraction.json"
    if not path.exists():
        return {'status':'NOT_CHECKED','reason':'Extraction has not finished'}
    extraction=json.loads(path.read_text(encoding='utf-8'))
    source=manifest(data)['sources']['osm']
    reader=osmium.io.Reader(str(data/source['raw_path']))
    stamp=reader.header().get('osmosis_replication_timestamp'); reader.close()
    examples=[]; s=session()
    for e in extraction.get('examples',[]):
        item=dict(e)
        try:
            # libosmium encodes way areas as 2*way_id; identify element type explicitly.
            match=re.search(r'area_id=(\d+)',e.get('error',''))
            if not match or int(match[1]) != 2*e['id']:
                raise ValueError('Not an unambiguous way-area failure')
            url=f"https://api.openstreetmap.org/api/0.6/way/{e['id']}/full"
            response=s.get(url,timeout=45); response.raise_for_status()
            root=ET.fromstring(response.content)
            nodes=root.findall('node')
            xs=[float(n.attrib['lon']) for n in nodes]; ys=[float(n.attrib['lat']) for n in nodes]
            bounds=[min(xs),min(ys),max(xs),max(ys)]
            members=nodes+root.findall('way')
            unchanged=bool(stamp) and all(n.attrib.get('timestamp','9999') <= stamp for n in members)
            checksum=hashlib.sha256(response.content).hexdigest()
            raw=data/'raw/osm/verification/errors'/f"way_{e['id']}_{checksum[:12]}.xml"
            raw.parent.mkdir(parents=True,exist_ok=True); raw.write_bytes(response.content)
            item.update(source_url=url,raw_path=raw.relative_to(data).as_posix(),sha256=checksum,
                        bbox=bounds,outside_aoi=not box(*bounds).intersects(geom),
                        all_objects_unchanged_since_extract=unchanged,snapshot_timestamp=stamp,status='LOCATED')
        except Exception as exc:
            item.update(status='NOT_CHECKED',error=str(exc))
        examples.append(item)
    return {'status':'CHECKED','failures':examples,'method':'OSM API full way and node bounds; timestamps checked against the national extract. Raw responses preserved.'}


def run(cfg,data,skip_buildings=False,skip_osm=False,skip_flood=False):
    geom=area(cfg,data); stem=cfg['area']['name']
    path=data / f'validation_reports/{stem}_source_verification.json'
    report=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    report.update(checked_at=now(), area=cfg['area'])
    station=cfg['area'].get('station')
    if station:
        report['station_boundary_check']={'contains_station':geom.covers(Point(station['coordinates'])), 'station':station,
            'boundary_type':'Official administrative district exposure area, not hydrological catchment'}
    for key,action,skip in [('flood_reference',flood_reference,skip_flood),('buildings_reference',reference_buildings,skip_buildings),('osm_inventory',live_osm,skip_osm)]:
        if skip:
            continue
        try:
            result=action(cfg,data,geom)
        except Exception as exc:
            result={'status':'NOT_CHECKED','error':repr(exc)}
        # Merge the latest report after a potentially long download; independent stages
        # may be run separately without erasing a completed check.
        if path.exists():
            report.update(json.loads(path.read_text(encoding='utf-8')))
        report[key]=result
        write_json(data / f'validation_reports/{stem}_{key}.json',result)
        write_json(path,report)
    report['extraction_failure_locations']=locate_extraction_errors(cfg,data,geom)
    write_json(path,report)
    print(json.dumps({k:{f:v[f] for f in ('status','feature_count','absent_count','error') if f in v} for k,v in report.items() if isinstance(v,dict)},indent=2),flush=True)
    return report


if __name__=='__main__':
    parser=setup(__doc__)
    parser.add_argument('--skip-buildings',action='store_true')
    parser.add_argument('--skip-osm',action='store_true')
    parser.add_argument('--skip-flood',action='store_true')
    parser.add_argument('--compare-existing-buildings',action='store_true',help='Refresh comparison after OSM preprocessing without repeating tile extraction')
    args=parser.parse_args()
    cfg,data=load(args)
    if args.compare_existing_buildings:
        path=data / f"validation_reports/{cfg['area']['name']}_source_verification.json"
        report=json.loads(path.read_text(encoding='utf-8'))
        ref=report['buildings_reference']
        ref.update(compare_buildings(cfg,data,data/ref['processed_path']))
        ref['comparison_updated_at']=now()
        write_json(path,report)
        print(json.dumps({k:ref[k] for k in ('feature_count','osm_buildings','reference_buildings_without_nearby_osm','osm_reference_match_fraction')},indent=2))
    else:
        report=run(cfg,data,skip_buildings=args.skip_buildings,skip_osm=args.skip_osm,skip_flood=args.skip_flood)
        requested=[k for k,skip in [('buildings_reference',args.skip_buildings),('flood_reference',args.skip_flood),('osm_inventory',args.skip_osm)] if not skip]
        raise SystemExit(1 if any(report.get(k,{}).get('status')=='NOT_CHECKED' for k in requested) else 0)
