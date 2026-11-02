"""Create the requested model queue and a self-contained first LSTM experiment."""
import ast
import hashlib
import json
import shutil
from pathlib import Path

import yaml

SHORT = Path(__file__).resolve().parent.parent
GROUP = SHORT / 'model/model_30_days'
FAMILIES = [
    ('Hindcast-forecast LSTM', 'Hindcast-forecast LSTM, including pretrained variants'),
    ('Encoder-decoder LSTM', 'Encoder-decoder LSTM'),
    ('HBV hybrids', 'delta-HBV, physical HBV and HBV residual hybrids'),
    ('Spatial elevation-band LSTM', 'Spatial elevation-band LSTM'),
    ('N-HiTS', 'N-HiTS'), ('N-BEATSx', 'N-BEATSx'),
]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    GROUP.mkdir(parents=True, exist_ok=True)
    queue = []
    for number, (folder, title) in enumerate(FAMILIES, 1):
        target = GROUP / folder
        target.mkdir(exist_ok=True)
        status = 'first experiment prepared' if number == 1 else 'pending user feedback; not trained'
        queue.append({'order': number, 'family': title, 'folder': folder, 'status': status})
        readme = target / 'README.md'
        if not readme.exists():
            content = f'# {title}: 30-day models\n\nStatus: **{status}**.\n\n'
            if number == 1:
                content += '[First variant: weather-only LSTM trained from scratch](scratch/README.md). Pretrained variants will be separate experiments after feedback.\n'
            else:
                content += 'This folder is reserved for a later experiment. No training, checkpoint or accuracy claim exists here. Its own data, training code and results will be stored here when that experiment is authorized after feedback.\n'
            readme.write_text(content, encoding='utf-8')
    (GROUP / 'training_queue.json').write_text(json.dumps(queue, indent=2) + '\n', encoding='utf-8')
    index = ['# 30-day flood forecasting experiments', '',
             'One model is trained and evaluated at a time. After the first result, work stops for feedback before the next model is trained.', '',
             '| Order | Model family | Status |', '|---:|---|---|']
    index += [f'| {row["order"]} | [{row["family"]}]({row["folder"].replace(" ", "%20")}/README.md) | {row["status"]} |' for row in queue]
    index += ['', 'The first experiment uses a reanalysis weather proxy because no archived 30-day weather forecasts were found. It cannot establish operational 30-day flood forecast accuracy.', '']
    (GROUP / 'README.md').write_text('\n'.join(index), encoding='utf-8')
    root = GROUP / 'Hindcast-forecast LSTM/scratch'
    root.mkdir(parents=True, exist_ok=True)
    data = root / 'data/marala_daily.csv'
    source = SHORT / 'evaluation comparison/common/data/marala_daily.csv'
    data.parent.mkdir(exist_ok=True)
    if data.exists() and sha(data) != sha(source):
        raise ValueError('Local table differs from original source')
    if not data.exists():
        shutil.copy2(source, data)
    reference = root / 'source_reference'
    reference.mkdir(exist_ok=True)
    original = SHORT / 'model/model_10 days/lstm'
    copies = [
        (SHORT / 'evaluation comparison/common/data.py', 'data.py', 'import argparse'),
        (original / 'model.py', 'model.py', 'import torch'),
        (original / 'train.py', '_training.py', 'import argparse'),
    ]
    records = []
    for src, name, start in copies:
        receipt = reference / name
        if not receipt.exists():
            shutil.copy2(src, receipt)
        text = receipt.read_text(encoding='utf-8-sig')
        local = root / name
        if not local.exists():
            local.write_text('"""Bundled project implementation with local imports; see source_reference."""\n' + text[text.index(start):], encoding='utf-8')
        records.append({'source': str(src), 'original_sha256': sha(receipt),
                        'bundled': name, 'bundled_sha256': sha(local),
                        'change': 'Removed workspace sys.path bootstrap only'})
    cfg = yaml.safe_load((original / 'config.yaml').read_text(encoding='utf-8-sig'))
    cfg = {k: cfg[k] for k in ('data', 'splits', 'normalization', 'model', 'training', 'finetuning')}
    cfg['data']['daily_file'] = 'data/marala_daily.csv'
    cfg['data']['forecast_horizon'] = 30
    cfg['data']['past_discharge'] = False
    cfg['training'].update(output_dir='runs/initial', epochs=120, patience=12,
                           ensemble_size=1, seeds=[42], cpu_threads=2, flush_denormal=True)
    cfg['finetuning']['output_dir'] = 'runs/finetuned'
    cfg['model_family'] = 'hindcast_forecast_lstm_30day_scratch'
    cfg['evaluation'] = {'output_dir': 'reports/initial', 'flood_percentile': .95,
                         'comparison_dir': '../../../../evaluation comparison/model_30_days/hindcast_forecast_lstm_scratch',
                         'report_leads': [1, 10, 15, 20, 30]}
    if not (root / 'config.yaml').exists():
        (root / 'config.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False), encoding='utf-8')
    (data.parent / 'preparation_report.json').write_text(json.dumps({
        'source': str(source), 'source_sha256': sha(source), 'local_sha256': sha(data),
        'byte_identical': True, 'no_discharge_imputation': True,
        'code_sources': records,
    }, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared six family folders. First model: {root}')


if __name__ == '__main__':
    main()
