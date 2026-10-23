"""Acquire OCHA COD-AB boundaries without overwriting geoBoundaries originals."""
import json
import re
import zipfile
from pathlib import Path

import geopandas as gpd

from common import write_json, manifest, now, digest


def acquire(cfg, data, metadata_only=False):
    from download import session, get_json, download
    s = session()
    package = get_json(s, 'https://data.humdata.org/api/3/action/package_show?id=cod-ab-pak')['result']
    resource = next(r for r in package['resources'] if r['name'].endswith('geojson.zip'))
    # Resource timestamps version the originals; a changed release cannot overwrite one.
    release = resource['last_modified'].split('T')[0]
    folder = data / 'raw/boundaries/hdx_cod' / release
    archive = folder / resource['name']
    write_json(data / 'metadata/hdx_cod_source.json', package)
    if metadata_only:
        return
    receipt = download(s, resource['url'], archive)
    m = manifest(data)
    m['sources']['hdx_cod_archive'] = dict(receipt, raw_path=archive.relative_to(data).as_posix(),
        status='downloaded', license=package['license_id'], source_metadata=package)
    notes = package['notes']
    # Preserve source wording, including every distinct date. Do not infer geometry age from upload date.
    meta = {'provider': 'OCHA COD-AB / HDX', 'dataset_url': 'https://data.humdata.org/dataset/cod-ab-pak',
            'resource_updated_at': resource['last_modified'], 'dataset_date': package['dataset_date'],
            'notes': notes, 'license': package['license_id'], 'boundaryYearRepresented': '2022',
            'geometry_created': '2022-09-02', 'last_reviewed': '2024-09-27'}
    # Fail rather than quietly applying hardcoded dates to a changed metadata release.
    if '02 September 2022' not in notes or '27 September 2024' not in notes:
        raise ValueError('HDX source dates changed; update the explicit provenance parser before use')
    with zipfile.ZipFile(archive) as z:
        print('HDX members:', z.namelist(), flush=True)
        for level in ('ADM0', 'ADM1', 'ADM2'):
            if cfg.get('existing_boundaries', {}).get(level):
                from common import resolve
                path = resolve(cfg, cfg['existing_boundaries'][level])
                if not path.exists():
                    raise FileNotFoundError(path)
                m['sources'][level] = {'status':'existing', 'path':str(path), 'sha256':digest(path),
                    'license':'User-provided; provenance must be verified'}
                continue
            number = level[-1]
            members = [n for n in z.namelist() if Path(n).name.lower() == f'pak_admin{number}.geojson']
            if len(members) != 1:
                raise ValueError(f'Ambiguous HDX {level} members: {members}')
            # Extract only the known member to a controlled filename; no archive path traversal.
            path = folder / f'PAK_{level}.geojson'
            payload = z.read(members[0])
            if path.exists() and path.read_bytes() != payload:
                raise ValueError('Extracted original changed; refusing overwrite')
            path.write_bytes(payload)
            frame = gpd.read_file(path)
            old = m['sources'].get(level)
            if old and old.get('raw_path') != path.relative_to(data).as_posix():
                history = m.setdefault('source_history', {}).setdefault(level, [])
                if not any(h.get('sha256') == old.get('sha256') for h in history):
                    history.append(old)
            entry = {'raw_path': path.relative_to(data).as_posix(), 'url': resource['url'],
                     'archive_member': members[0], 'archive_sha256': receipt['sha256'],
                     'sha256': digest(path), 'bytes': path.stat().st_size, 'downloaded_at': receipt['downloaded_at'],
                     'status': 'downloaded', 'license': package['license_id'], 'source_metadata': meta,
                     'year': 2022, 'version': release, 'crs': str(frame.crs), 'feature_count': len(frame)}
            m['sources'][level] = entry
            write_json(data / f'metadata/{level}_source.json', meta)
    m['updated_at'] = now()
    write_json(data / 'metadata/manifest.json', m)


def normalize(frame, level):
    """Add stable common fields without dropping original COD attributes."""
    number = level[-1]
    lower = {c.lower(): c for c in frame.columns}
    name = lower.get(f'adm{number}_name') or lower.get(f'adm{number}_en')
    code = lower.get(f'adm{number}_pcode')
    if name is None or code is None:
        raise ValueError(f'HDX {level} name/code fields unavailable: {list(frame.columns)}')
    frame = frame.copy()
    frame['shapeName'] = frame[name]
    frame['shapeID'] = frame[code]
    return frame


if __name__ == '__main__':
    from common import setup, load
    acquire(*load(setup(__doc__).parse_args()))
