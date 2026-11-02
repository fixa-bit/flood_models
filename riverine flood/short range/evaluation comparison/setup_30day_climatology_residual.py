"""Prepare an NSE-focused residual LSTM ensemble without editing previous runs."""
import hashlib
import json
import shutil
from pathlib import Path

import yaml

SHORT = Path(__file__).resolve().parent.parent
FAMILY = SHORT / 'model/model_30_days/Hindcast-forecast LSTM'
NEW = FAMILY / 'climatology_residual_ensemble'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if NEW.exists():
        raise FileExistsError('Preserve the existing residual ensemble experiment')
    NEW.mkdir()
    reference = FAMILY / 'past_discharge'
    protected = []
    for name in ('scratch', 'past_discharge'):
        for path in (FAMILY / name).rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                protected.append({'path': str(path), 'sha256': sha(path)})
    (NEW / 'reference_artifacts_before.json').write_text(json.dumps(protected, indent=2) + '\n', encoding='utf-8')
    (NEW / 'data').mkdir()
    shutil.copy2(reference / 'data/marala_daily.csv', NEW / 'data/marala_daily.csv')
    shutil.copy2(reference / 'data.py', NEW / '_core_data.py')
    (NEW / 'source_reference').mkdir()
    for filename in ('data.py', 'model.py', '_training.py'):
        shutil.copy2(reference / filename, NEW / 'source_reference' / filename)
    cfg = yaml.safe_load((reference / 'config.yaml').read_text())
    cfg['model_family'] = 'climatology_residual_lstm_ensemble_30day'
    cfg['training'].update(ensemble_size=3, seeds=[42, 43, 44], epochs=100,
                           learning_rate=.0005, patience=12, min_delta=.0001)
    cfg['model']['smooth_climatology_window'] = 31
    cfg['model']['parent_checkpoint'] = '../past_discharge/runs/initial/seed_42/best.pt'
    cfg['training'].update(point_mse_weight=1., quantile_loss_weight=.15,
                           residual_penalty=.02, late_lead_weight=2., selection_leads=[21, 30])
    cfg['postprocessing'] = {'lead_groups': [[1, 10], [11, 20], [21, 30]],
                             'fit_climatology_blend': True, 'calibrate_quantiles': True}
    cfg['evaluation']['comparison_dir'] = '../../../../evaluation comparison/model_30_days/climatology_residual_ensemble'
    cfg['evaluation']['weather_only_predictions'] = '../scratch/reports/initial/predictions.csv'
    cfg['evaluation']['past_discharge_predictions'] = '../past_discharge/reports/initial/predictions.csv'
    cfg['evaluation'].pop('reference_predictions', None)
    cfg['evaluation'].pop('reference_config', None)
    (NEW / 'config.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False), encoding='utf-8')
    (NEW / 'data/preparation_report.json').write_text(json.dumps({
        'source': str(reference / 'data/marala_daily.csv'),
        'source_sha256': sha(reference / 'data/marala_daily.csv'),
        'local_sha256': sha(NEW / 'data/marala_daily.csv'),
        'byte_identical': True, 'target_filling': False,
        'baseline_statistics_use_training_years_only': True,
    }, indent=2) + '\n', encoding='utf-8')
    print(NEW)


if __name__ == '__main__':
    main()
