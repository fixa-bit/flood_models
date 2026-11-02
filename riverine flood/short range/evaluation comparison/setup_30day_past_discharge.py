"""Prepare one matched 30-day LSTM experiment with causal discharge inputs."""
import hashlib
import json
import shutil
from pathlib import Path

import yaml

SHORT = Path(__file__).resolve().parent.parent
FAMILY = SHORT / 'model/model_30_days/Hindcast-forecast LSTM'
REFERENCE = FAMILY / 'scratch'
NEW = FAMILY / 'past_discharge'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    if NEW.exists():
        raise FileExistsError('The past_discharge variant already exists; preserve it')
    NEW.mkdir()
    protected = [{'path': str(p), 'sha256': sha(p)} for p in REFERENCE.rglob('*')
                 if p.is_file() and '__pycache__' not in p.parts]
    (NEW / 'reference_artifacts_before.json').write_text(json.dumps(protected, indent=2) + '\n', encoding='utf-8')
    (NEW / 'source_reference').mkdir()
    for name in ('data.py', 'model.py', '_training.py', 'baselines.py', 'finetune.py', 'requirements.txt'):
        shutil.copy2(REFERENCE / name, NEW / name)
        if name.endswith('.py'):
            shutil.copy2(REFERENCE / name, NEW / 'source_reference' / name)
    (NEW / 'data').mkdir()
    shutil.copy2(REFERENCE / 'data/marala_daily.csv', NEW / 'data/marala_daily.csv')
    cfg = yaml.safe_load((REFERENCE / 'config.yaml').read_text(encoding='utf-8'))
    cfg['data']['past_discharge'] = True
    cfg['model_family'] = 'hindcast_forecast_lstm_30day_past_discharge'
    cfg['evaluation']['comparison_dir'] = '../../../../evaluation comparison/model_30_days/hindcast_forecast_lstm_past_discharge'
    cfg['evaluation']['reference_predictions'] = '../scratch/reports/initial/predictions.csv'
    cfg['evaluation']['reference_config'] = '../scratch/config.yaml'
    (NEW / 'config.yaml').write_text(yaml.safe_dump(cfg, sort_keys=False), encoding='utf-8')
    evaluator = (REFERENCE / 'evaluate.py').read_text(encoding='utf-8')
    evaluator = evaluator.replace('LSTM_30d', 'LSTM_30d_pastQ').replace('hindcast_forecast_lstm_scratch', 'hindcast_forecast_lstm_past_discharge')
    evaluator = evaluator.replace('Thirty-day hindcast-forecast LSTM: first experiment', 'Thirty-day LSTM with past discharge: matched input experiment')
    evaluator = evaluator.replace('Only the scratch LSTM was trained. All other 30-day model families remain pending feedback.',
                                  'This step trains only the past-discharge variant from scratch. The weather-only reference is retained unchanged; other model families remain pending feedback.')
    evaluator = evaluator.replace('No observed past or future discharge is supplied to the LSTM.',
                                  'Observed discharge through issue day t is supplied with a missing indicator. Future observed discharge is never supplied. Missing past discharge uses the training log-flow mean inside model samples only; the source discharge series is unchanged.')
    (NEW / 'evaluate.py').write_text(evaluator, encoding='utf-8')
    trainer = (REFERENCE / 'train.py').read_text(encoding='utf-8')
    trainer = trainer.replace('Fit one 30-day LSTM, evaluate it, then stop for user feedback.', 'Fit one matched past-discharge LSTM, compare it, then stop for feedback.')
    trainer = trainer.replace('from evaluate import evaluate, save_json, sha256', 'from evaluate import evaluate, save_json, sha256\nfrom compare_variants import compare')
    trainer = trainer.replace("'one_real_model_only': True", "'one_real_model_in_this_step': True, 'past_discharge_input': True")
    trainer = trainer.replace('result = evaluate(cfg)', 'result = evaluate(cfg)\n        compare(cfg)')
    trainer = trainer.replace("queue[0]['completed_variant'] = 'scratch'", "queue[0]['completed_variants'] = ['scratch', 'past_discharge']\n        queue[0]['completed_variant'] = 'past_discharge'")
    trainer = trainer.replace('First model complete. No other 30-day model was trained. Awaiting user feedback.', 'Past-discharge variant complete. No other model family was trained. Awaiting user feedback.')
    (NEW / 'train.py').write_text(trainer, encoding='utf-8')
    (NEW / 'tests').mkdir()
    tests = (REFERENCE / 'tests/test_pipeline.py').read_text(encoding='utf-8').replace('(365, 18)', '(365, 20)')
    (NEW / 'tests/test_pipeline.py').write_text(tests, encoding='utf-8')
    (NEW / 'data/preparation_report.json').write_text(json.dumps({
        'source': str(REFERENCE / 'data/marala_daily.csv'),
        'source_sha256': sha(REFERENCE / 'data/marala_daily.csv'),
        'local_sha256': sha(NEW / 'data/marala_daily.csv'), 'byte_identical': True,
        'source_values_never_filled': True,
        'past_discharge_handling': 'training-normalized log flow plus missing indicator, inside samples only',
        'other_training_settings_unchanged': True,
    }, indent=2) + '\n', encoding='utf-8')
    print(f'Prepared {NEW}; original weather-only variant protected.')


if __name__ == '__main__':
    main()
