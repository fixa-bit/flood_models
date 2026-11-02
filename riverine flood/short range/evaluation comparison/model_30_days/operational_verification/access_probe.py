"""Check real 30-day archive access; never print keys or accept new terms."""
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent


def save(name, value):
    ROOT.mkdir(parents=True, exist_ok=True)
    (ROOT / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def main():
    collection_url = 'https://ecds.ecmwf.int/api/catalogue/v1/collections/s2s-forecasts'
    response = requests.get(collection_url, timeout=25)
    response.raise_for_status()
    metadata = response.json()
    save('s2s_collection_metadata.json', metadata)
    process_url = 'https://ecds.ecmwf.int/api/retrieve/v1/processes/s2s-forecasts'
    process = requests.get(process_url, timeout=25)
    process.raise_for_status()
    save('s2s_process_schema.json', process.json())
    request = {'origin': 'ecmwf', 'year': '2022', 'month': '08', 'day': '01',
               'time': '00:00', 'level_type': 'single_level',
               'variable': ['total_precipitation'], 'forecast_type': 'control_forecast',
               'leadtime_hour': ['24'], 'data_format': 'grib',
               'area': [35, 73.5, 31.5, 78]}
    save('s2s_minimal_access_request.json', request)
    credential = Path.home() / '.cdsapirc'
    result = {'credentials_file_present': credential.exists(),
              'credential_values_recorded': False, 'new_licences_accepted': False,
              'endpoint': process_url + '/execution'}
    if credential.exists():
        values = yaml.safe_load(credential.read_text(encoding='utf-8'))
        token = values.get('key')
        if token:
            # ECMWF documents that CDS/ECDS share the same account/API key.
            reply = requests.post(process_url + '/execution', headers={'PRIVATE-TOKEN': token},
                                  json={'inputs': request}, timeout=35)
            result['http_status'] = reply.status_code
            try:
                body = reply.json()
            except ValueError:
                body = {'message': reply.text[:3000]}
            # Response bodies must never retain the local authentication token.
            result['response'] = json.loads(json.dumps(body).replace(str(token), '[REDACTED]'))
            result['location'] = reply.headers.get('Location')
    save('s2s_access_result.json', result)
    print('ECDS access:', result.get('http_status'),
          json.dumps(result.get('response', {}))[:2200], flush=True)
    catalog = 'https://www.ncei.noaa.gov/thredds/catalog/model-cfs_v2_for_ts/2022/202208/20220801/catalog.xml'
    reply = requests.get(catalog, timeout=25)
    ncei = {'url': catalog, 'http_status': reply.status_code, 'entries': []}
    if reply.ok:
        tree = ET.fromstring(reply.text)
        ncei['entries'] = [{'name': item.attrib.get('name'),
                            'href': item.attrib.get('{http://www.w3.org/1999/xlink}href'),
                            'url_path': item.attrib.get('urlPath')}
                           for item in tree.iter() if item.tag.endswith(('catalogRef', 'dataset'))]
    save('noaa_cfs_archive_access.json', ncei)
    print('NOAA CFS archive:', reply.status_code, ncei['entries'][:12], flush=True)


if __name__ == '__main__':
    main()
