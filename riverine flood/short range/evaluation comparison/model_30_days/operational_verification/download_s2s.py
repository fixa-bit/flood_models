"""Retrieve bounded ECMWF S2S control forecasts for a real-weather hindcast pilot."""
import concurrent.futures
import hashlib
import json
import time
from pathlib import Path

import requests
import yaml

ROOT = Path(__file__).resolve().parent
SHORT = ROOT.parents[2]
RAW = SHORT / 'dataset/chenab_marala/raw/marala/weather_forecasts/operational_verification/ecmwf_s2s'
API = 'https://ecds.ecmwf.int/api/retrieve/v1'


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8')


def plan():
    constraints = json.loads((ROOT / 's2s_constraints.json').read_text())
    requests_list = []
    variables = [('precipitation', 'total_precipitation', [str(x) for x in range(48, 769, 24)]),
                 ('temperature', '2_m_temperature', [f'{x}_{x + 24}' for x in range(48, 768, 24)])]
    for year in (2022, 2023, 2024):
        for month in (6, 7, 8, 9):
            allowed = {}
            for name, variable, leads in variables:
                days = set()
                for row in constraints:
                    if ('ecmwf' in row.get('origin', []) and str(year) in row.get('year', [])
                        and f'{month:02}' in row.get('month', []) and variable in row.get('variable', [])
                        and 'single_level' in row.get('level_type', []) and '00:00' in row.get('time', [])
                        and 'control_forecast' in row.get('forecast_type', [])
                        and set(leads).issubset(row.get('leadtime_hour', []))):
                        days.update(row['day'])
                allowed[name] = days
            days = sorted(allowed['precipitation'] & allowed['temperature'])
            if not days:
                raise ValueError(f'No compatible forecast dates for {year}-{month}')
            for name, variable, leads in variables:
                request = {'origin': 'ecmwf', 'year': str(year), 'month': f'{month:02}',
                           'day': days, 'time': '00:00', 'level_type': 'single_level',
                           'variable': [variable], 'forecast_type': 'control_forecast',
                           'leadtime_hour': leads, 'data_format': 'grib',
                           'area': [35, 73.5, 31.5, 78]}
                requests_list.append({'id': f'{year}{month:02}_{name}', 'request': request,
                                      'origins': len(days), 'variable': name,
                                      'target': str(RAW / f'{year}{month:02}_{name}.grib')})
    save(ROOT / 's2s_pilot_request_plan.json', requests_list)
    return requests_list


def find_assets(obj):
    assets = []
    if isinstance(obj, dict):
        if 'href' in obj and any(k in obj for k in ('type', 'title', 'file:size')):
            href = obj['href']
            if isinstance(href, str) and href.startswith('https://') and '/api/retrieve/' not in href:
                assets.append(href)
        for value in obj.values():
            assets.extend(find_assets(value))
    elif isinstance(obj, list):
        for value in obj:
            assets.extend(find_assets(value))
    return list(dict.fromkeys(assets))


def main():
    jobs = plan()
    token = yaml.safe_load((Path.home() / '.cdsapirc').read_text(encoding='utf-8'))['key']
    headers = {'PRIVATE-TOKEN': token}
    print(f'Pilot: {sum(x["origins"] for x in jobs) // 2} initialization dates, {len(jobs)} small regional retrievals.', flush=True)

    def submit(item):
        receipt = ROOT / 'jobs' / (item['id'] + '.json')
        if receipt.exists():
            return json.loads(receipt.read_text())
        response = requests.post(API + '/processes/s2s-forecasts/execution', headers=headers,
                                 json={'inputs': item['request']}, timeout=40)
        try:
            body = response.json()
        except ValueError:
            body = {'message': response.text[:2000]}
        result = {**item, 'http_status': response.status_code, 'response': body}
        save(receipt, result)
        if not response.ok:
            raise RuntimeError(f'Retrieval rejected: {item["id"]}, HTTP {response.status_code}, {str(body)[:1000]}')
        return result
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        submitted = list(pool.map(submit, jobs))
    started = time.monotonic()
    pending = list(submitted)
    while pending:
        remaining = []
        for item in pending:
            target = Path(item['target'])
            proof = target.with_suffix('.receipt.json')
            if target.exists() and proof.exists():
                continue
            job_id = item['response']['jobID']
            status_url = API + '/jobs/' + job_id
            reply = requests.get(status_url, headers=headers, timeout=35)
            reply.raise_for_status()
            status = reply.json()
            save(ROOT / 'jobs' / (item['id'] + '_status.json'), status)
            if status['status'] == 'failed':
                raise RuntimeError(f'Archive retrieval failed: {item["id"]}, {str(status)[:1600]}')
            if status['status'] != 'successful':
                remaining.append(item)
                continue
            result_url = next(link['href'] for link in status['links'] if link.get('rel') == 'results')
            result_response = requests.get(result_url, headers=headers, timeout=35)
            result_response.raise_for_status()
            body = result_response.json()
            assets = find_assets(body)
            if not assets:
                save(ROOT / 'jobs' / (item['id'] + '_results_structure.json'), body)
                raise RuntimeError(f'No download asset found for {item["id"]}; inspect saved response')
            if len(assets) != 1:
                raise RuntimeError(f'Expected one regional asset for {item["id"]}, found {len(assets)}')
            download = requests.get(assets[0], timeout=60)
            download.raise_for_status()
            if not (download.content.startswith(b'GRIB') or download.content.startswith(b'PK')):
                raise ValueError('Unexpected archive format')
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(download.content)
            save(proof, {'dataset': 's2s-forecasts', 'provider': 'ECMWF',
                         'request': item['request'], 'job_id': job_id,
                         'sha256': hashlib.sha256(download.content).hexdigest(),
                         'bytes': len(download.content), 'format': 'grib' if download.content.startswith(b'GRIB') else 'zip',
                         'note': 'archive retrieval time is not the historical publication time'})
            print(f'Downloaded {item["id"]}: {len(download.content):,} bytes', flush=True)
        pending = remaining
        if pending:
            print(f'Waiting for {len(pending)} archive jobs; elapsed {time.monotonic() - started:.0f}s', flush=True)
            if time.monotonic() - started > 1500:
                print('Retrievals still queued; rerun to resume existing jobs.', flush=True)
                return
            time.sleep(10)
    save(ROOT / 's2s_download_complete.json', {'jobs': len(jobs), 'initialization_dates': sum(x['origins'] for x in jobs) // 2,
              'region': [35, 73.5, 31.5, 78], 'months': [6, 7, 8, 9], 'years': [2022, 2023, 2024],
              'forecast_type': 'control_forecast', 'lead_period': '48 to 768 hours',
              'source_folder': str(RAW)})
    print('Regional pilot forecast retrieval complete.', flush=True)


if __name__ == '__main__':
    main()
