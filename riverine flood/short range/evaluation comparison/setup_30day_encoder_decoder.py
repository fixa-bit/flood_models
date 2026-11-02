"""Prepare a separate, auditable 15-to-30-day encoder-decoder fine-tuning run."""
import hashlib
import json
import shutil
from pathlib import Path

import numpy as np
import pandas as pd
import torch
import yaml

SHORT = Path(__file__).resolve().parent.parent
GROUP = SHORT / 'model/model_30_days'
NEW = GROUP / 'Encoder-decoder LSTM/finetuned_15_to_30'
PARENT = SHORT / 'model/model_15 days/encoder_decoder_lstm_finetuned'
PREVIOUS = GROUP / 'Hindcast-forecast LSTM/climatology_residual_ensemble'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if NEW.exists():
        raise FileExistsError('Preserve the existing encoder-decoder experiment')
    NEW.mkdir()
    protected = []
    for folder in (PARENT, GROUP / 'Hindcast-forecast LSTM'):
        for path in folder.rglob('*'):
            if path.is_file() and '__pycache__' not in path.parts:
                protected.append({'path': str(path), 'sha256': sha(path)})
    (NEW / 'reference_artifacts_before.json').write_text(json.dumps(protected, indent=2) + '\n', encoding='utf-8')
    (NEW / 'data').mkdir()
    shutil.copy2(PARENT / 'data/marala_daily.csv', NEW / 'data/marala_daily.csv')
    reference = NEW / 'reference/parent_15day'
    reference.mkdir(parents=True)
    for name in ('best.pt', 'config.yaml', 'normalization.json', 'years.json'):
        source = PARENT / 'runs/initial/seed_42' / name
        if source.exists():
            shutil.copy2(source, reference / name)
    (NEW / 'source_reference').mkdir()
    for name in ('_core_data.py', 'data.py', 'metrics.py', 'postprocess.py', 'requirements.txt'):
        shutil.copy2(PREVIOUS / name, NEW / name)
        if name.endswith('.py'):
            shutil.copy2(PREVIOUS / name, NEW / 'source_reference' / name)
    # The parent uses the project's ordinary quantile encoder/decoder class.
    shutil.copy2(GROUP / 'Hindcast-forecast LSTM/past_discharge/model.py', NEW / '_parent_model.py')
    shutil.copy2(PARENT / 'model.py', NEW / 'source_reference/parent_transfer_code.py')
    cfg = yaml.safe_load((PREVIOUS / 'config.yaml').read_text(encoding='utf-8'))
    source_cfg = yaml.safe_load((PARENT / 'config.yaml').read_text(encoding='utf-8'))
    cfg['data'] = source_cfg['data']
    cfg['data']['daily_file'] = 'data/marala_daily.csv'
    cfg['data']['forecast_horizon'] = 30
    cfg['model'] = source_cfg['model']
    cfg['model']['smooth_climatology_window'] = 31
    cfg['model']['parent_checkpoint'] = 'reference/parent_15day/best.pt'
    cfg['model']['new_lead_initialization'] = 'repeat day-15 vector for days 16-30; all embeddings trainable'
    cfg['model_family'] = 'encoder_decoder_lstm_30day_finetuned_15_to_30'
    cfg['training'].update(learning_rate=.0003, batch_size=128)
    cfg['evaluation']['comparison_dir'] = '../../../../evaluation comparison/model_30_days/encoder_decoder_finetuned_15_to_30'
    cfg['evaluation']['weather_only_predictions'] = '../../Hindcast-forecast LSTM/scratch/reports/initial/predictions.csv'
    cfg['evaluation']['past_discharge_predictions'] = '../../Hindcast-forecast LSTM/past_discharge/reports/initial/predictions.csv'
    cfg['evaluation']['best_ensemble_predictions'] = '../../Hindcast-forecast LSTM/climatology_residual_ensemble/reports/initial/predictions.csv'
    (NEW / 'config.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False), encoding='utf-8')
    checkpoint = torch.load(reference / 'best.pt', map_location='cpu', weights_only=True)
    assert checkpoint['config']['data']['forecast_horizon'] == 15
    assert not (set(checkpoint['training_years'] + checkpoint['selection_years']) & {2022, 2023, 2024})
    local = pd.read_csv(NEW / 'data/marala_daily.csv')
    canonical_path = SHORT / 'evaluation comparison/common/data/marala_daily.csv'
    canonical = pd.read_csv(canonical_path)
    merged = local.merge(canonical[['date', 'basin_id', 'q_cumecs', 'rain_era5_mm']], on=['date', 'basin_id'], suffixes=('_local', '_canonical'), validate='one_to_one')
    assert len(merged) == len(local)
    np.testing.assert_array_equal(merged.q_cumecs_local.isna(), merged.q_cumecs_canonical.isna())
    np.testing.assert_allclose(merged.q_cumecs_local, merged.q_cumecs_canonical, rtol=0, atol=1e-10, equal_nan=True)
    np.testing.assert_allclose(merged.precipitation_mm, merged.rain_era5_mm, rtol=0, atol=1e-10)
    receipt = {'source': str(PARENT / 'data/marala_daily.csv'),
               'source_sha256': sha(PARENT / 'data/marala_daily.csv'),
               'local_sha256': sha(NEW / 'data/marala_daily.csv'), 'byte_identical_copy': True,
               'canonical_source': str(canonical_path), 'canonical_sha256': sha(canonical_path),
               'observed_values_and_missing_positions_preserved': True,
               'rows': len(local), 'observed_targets': int(local.q_cumecs.notna().sum()),
               'missing_targets': int(local.q_cumecs.isna().sum()),
               'first_date': local.date.min(), 'last_date': local.date.max(),
               'parent_checkpoint_sha256': sha(reference / 'best.pt'),
               'parent_pretraining_basins': checkpoint.get('pretraining_basins', []),
               'parent_training_years': checkpoint['training_years'],
               'parent_selection_years': checkpoint['selection_years']}
    (NEW / 'data/preparation_report.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    trainer = (PREVIOUS / 'train.py').read_text(encoding='utf-8').replace('ResidualLSTM', 'EncoderDecoderLSTM')
    trainer = trainer.replace('Sequential three-seed fitting with all choices fixed before test evaluation.', 'Fine-tune the saved 15-day encoder-decoder for 30 days, one seed at a time.')
    trainer = trainer.replace("'training_years': years(cfg['splits']['train']),", "'training_years': sorted(set(parent['training_years'] + years(cfg['splits']['train']))),")
    trainer = trainer.replace("'selection_years': years(cfg['splits']['validation']),", "'selection_years': sorted(set(parent['selection_years'] + years(cfg['splits']['validation']))),\n                    'pretraining_basins': parent.get('pretraining_basins', []),\n                    'source_horizon': 15, 'new_horizon': 30,")
    trainer = trainer.replace("queue[0].update(completed_variants=['scratch', 'past_discharge', 'climatology_residual_ensemble'],\n                        completed_variant='climatology_residual_ensemble', status='trained and evaluated; awaiting user feedback')", "queue[1].update(completed_variants=['finetuned_15_to_30'], completed_variant='finetuned_15_to_30',\n                        status='trained and evaluated; awaiting user feedback')")
    trainer = trainer.replace('Residual ensemble complete; all other model families remain pending feedback.', 'Thirty-day encoder-decoder complete; later model families remain pending feedback.')
    (NEW / 'train.py').write_text(trainer, encoding='utf-8')
    print(f'Prepared {NEW}; copied parent and discharge data unchanged.')


if __name__ == '__main__':
    main()
