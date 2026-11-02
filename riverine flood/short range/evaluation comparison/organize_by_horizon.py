"""Audit saved horizons and repair references after native filesystem moves."""
import argparse
import ast
import hashlib
import json
import os
import re
from pathlib import Path

import yaml

SHORT_RANGE = Path(__file__).resolve().parent.parent
MODEL = SHORT_RANGE / 'model'
RECORDS = SHORT_RANGE / 'evaluation comparison/horizon_organization'
TEN = ['catchment_mean_lstm', 'climatology', 'delta_hbv', 'ensemble',
       'fine_tuned_global_pretrained_lstm', 'gradient_boosting', 'hbv_lightgbm',
       'hbv_lstm', 'hbv_residual', 'hybrid_physics_ml', 'lstm',
       'lstm_past_discharge_weather', 'lstm_two_input_scratch', 'N-BEATSx',
       'N-HiTS', 'persistence', 'pretrained_multibasin_lstm',
       'pretrained_multibasin_lstm_finetuned', 'spatially_distributed_model']
FIFTEEN = ['discharge_history_lstm', 'encoder_decoder_lstm',
           'encoder_decoder_lstm_finetuned', 'grrr_lstm',
           'grrr_lstm_weighted_fills_rejected']
GROUPS = {name: 'model_10 days' for name in TEN} | {name: 'model_15 days' for name in FIFTEEN}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def mapped(path):
    path = Path(path).resolve()
    original = path
    for name, group in GROUPS.items():
        old = MODEL / name
        try:
            target = MODEL / group / name / path.relative_to(old)
            if original.exists() or target.exists():
                return target
            break
        except ValueError:
            continue
    else:
        return path
    # Repair saved stage manifests that still name pre-split family run folders.
    historical = []
    for filename in ('organization_moves.json', 'organization_variant_moves.json'):
        ledger = SHORT_RANGE / 'evaluation comparison' / filename
        if ledger.exists():
            historical.extend(json.loads(ledger.read_text(encoding='utf-8-sig')))
    for move in sorted(historical, key=lambda item: -len(item['old'])):
        try:
            revised = Path(move['new']) / original.relative_to(Path(move['old']))
        except ValueError:
            continue
        if revised != original:
            return mapped(revised)
    return target


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2) + '\n', encoding='utf-8')


def prepare():
    if (RECORDS / 'move_plan.json').exists():
        raise FileExistsError('An audit already exists; do not overwrite its original hashes')
    import torch
    entries, artifacts = [], []
    actual = {p.name for p in MODEL.iterdir() if p.is_dir()}
    if actual != set(GROUPS):
        raise ValueError(f'Unclassified directories: {actual.symmetric_difference(GROUPS)}')
    for name, group in GROUPS.items():
        folder = MODEL / name
        expected = 10 if name in TEN else 15
        if (folder / 'config.yaml').exists():
            cfg = yaml.safe_load((folder / 'config.yaml').read_text(encoding='utf-8-sig'))
            found = cfg['data']['forecast_horizon']
            evidence = 'config.yaml: data.forecast_horizon'
        elif (folder / 'config.json').exists():
            cfg = json.loads((folder / 'config.json').read_text(encoding='utf-8-sig'))
            found = cfg['horizon']
            evidence = 'config.json: horizon'
        elif name.startswith('grrr_lstm'):
            cfg = json.loads((folder / 'protocol.json').read_text(encoding='utf-8-sig'))
            found = cfg['architecture']['horizon']
            evidence = 'protocol.json: architecture.horizon'
        else:
            source = (folder / 'train.py').read_text(encoding='utf-8-sig')
            match = re.search(r'LOOKBACK, HORIZON, EPOCHS, SEED = (\d+), (\d+),', source)
            found = int(match.group(2))
            evidence = 'train.py: HORIZON'
        if found != expected:
            raise ValueError(f'Mixed/incorrect classification for {name}: {found}')
        checkpoint_evidence = []
        primary = folder / 'runs/initial/seed_42/best.pt'
        if name == 'discharge_history_lstm':
            primary = folder / 'observed_only/model.pt'
        elif name == 'grrr_lstm':
            primary = folder / 'runs/initial/nan_gaps.pt'
        if primary.exists():
            checkpoint = torch.load(primary, map_location='cpu', weights_only=False)
            if 'config' in checkpoint and 'data' in checkpoint['config']:
                saved_horizon = checkpoint['config']['data']['forecast_horizon']
            elif 'head.weight' in checkpoint:
                saved_horizon = checkpoint['head.weight'].shape[0]
            else:
                saved_horizon = None
            if saved_horizon is not None:
                assert saved_horizon == expected, (name, saved_horizon)
                checkpoint_evidence.append(f'{primary.relative_to(folder).as_posix()}: {saved_horizon}')
        entries.append({'name': name, 'horizon': expected, 'evidence': evidence,
                        'checkpoint_evidence': checkpoint_evidence,
                        'old': str(folder), 'new': str(MODEL / group / name),
                        'status': 'rejected; checkpoint not retained' if name.endswith('_rejected') else 'saved run',
                        'reference_checkpoints_are_not_separate_forecast_variants': name.startswith('encoder_decoder')})
        for path in folder.rglob('*'):
            if not path.is_file() or '__pycache__' in path.parts:
                continue
            # Checkpoints, original data, figures, upstream code and LightGBM weights.
            protect = path.suffix.lower() in ('.pt', '.pkl', '.csv', '.gz', '.png', '.nc', '.grib', '.zip')
            protect |= 'source_reference' in path.parts or '_vendor' in path.parts
            protect |= 'lightgbm' in path.parts and path.suffix == '.txt'
            if protect:
                artifacts.append({'old': str(path), 'new': str(mapped(path)),
                                  'sha256': digest(path), 'bytes': path.stat().st_size})
    write_json(RECORDS / 'move_plan.json', entries)
    write_json(RECORDS / 'protected_artifacts_before.json', artifacts)
    print(f'Audited {len(TEN)} ten-day and {len(FIFTEEN)} fifteen-day variants; {len(artifacts)} protected files.')


PATH_KEYS = {'path', 'checkpoint', 'config', 'manifest', 'directory', 'file', 'source_daily_file',
             'original_checkpoint', 'original_config', 'pretrained_checkpoint', 'adapted_checkpoint'}


def rebase_value(value, key, old_base, new_base):
    if isinstance(value, dict):
        result = {}
        for k, v in value.items():
            new_key = str(mapped(k)) if isinstance(k, str) and (k.startswith(str(MODEL)) or k.startswith(MODEL.as_posix())) else k
            result[new_key] = rebase_value(v, k, old_base, new_base)
        return result
    if isinstance(value, list):
        return [rebase_value(v, key, old_base, new_base) for v in value]
    if not isinstance(value, str) or not value or '://' in value or '\n' in value:
        return value
    is_path = key in PATH_KEYS or str(key).endswith(('_file', '_dir', '_directory', '_config', '_checkpoint', '_path'))
    is_path |= value.startswith(('../', './', str(MODEL), MODEL.as_posix()))
    is_path |= '/' in value and not any(c.isspace() for c in value.replace('evaluation comparison', '').replace('model_10 days', '').replace('model_15 days', ''))
    if not is_path:
        return value
    old_target = (old_base / value).resolve()
    new_target = mapped(old_target)
    if Path(value).is_absolute():
        return str(new_target)
    return Path(os.path.relpath(new_target, new_base)).as_posix()


def repair_markdown(text, old_base, new_base):
    def replace(match):
        target = match.group(1)
        if '://' in target or target.startswith('#') or target.startswith('mailto:'):
            return match.group(0)
        # Existing generated readmes use encoded spaces and relative file targets.
        plain = target.replace('%20', ' ').strip('<>')
        if ' ' in plain and not any(x in plain for x in ('evaluation comparison', 'model_10 days', 'model_15 days')):
            return match.group(0)
        tail = ''
        if '#' in plain:
            plain, tail = plain.split('#', 1)
            tail = '#' + tail
        resolved = mapped(old_base / plain)
        replacement = Path(os.path.relpath(resolved, new_base)).as_posix().replace(' ', '%20') + tail
        return '](' + replacement + ')'
    return re.sub(r'\]\(([^)]+)\)', replace, text)


def update():
    plan = json.loads((RECORDS / 'move_plan.json').read_text())
    edits = []

    def save(path, text):
        original = path.read_text(encoding='utf-8-sig')
        if original != text:
            path.write_text(text, encoding='utf-8')
            edits.append(str(path.relative_to(SHORT_RANGE)))

    for entry in plan:
        old, new = Path(entry['old']), Path(entry['new'])
        if old.exists() or not new.is_dir():
            raise RuntimeError(f'Native move not complete: {old} -> {new}')
        for path in new.iterdir():
            if path.is_file() and (path.suffix in ('.yaml', '.yml') or path.name == 'config.json'):
                obj = yaml.safe_load(path.read_text(encoding='utf-8-sig')) if path.suffix != '.json' else json.loads(path.read_text(encoding='utf-8-sig'))
                revised = rebase_value(obj, '', old, new)
                save(path, yaml.safe_dump(revised, sort_keys=False) if path.suffix != '.json' else json.dumps(revised, indent=2) + '\n')
            if path.is_file() and path.suffix.lower() == '.md':
                save(path, repair_markdown(path.read_text(encoding='utf-8-sig'), old, new))
        # Mutable orchestration manifests, not original checkpoint/config snapshots.
        for pattern in ('runs/**/ensemble.json', 'runs/stages.json', 'runs/selected_model.json', 'runs/**/selected_model.json', 'runs/source_hashes.json'):
            for path in new.glob(pattern):
                obj = json.loads(path.read_text(encoding='utf-8-sig'))
                old_base = old / path.parent.relative_to(new)
                save(path, json.dumps(rebase_value(obj, 'path', old_base, path.parent), indent=2) + '\n')

    common_config = SHORT_RANGE / 'evaluation comparison/common/config.yaml'
    cfg = yaml.safe_load(common_config.read_text(encoding='utf-8-sig'))
    save(common_config, yaml.safe_dump(rebase_value(cfg, '', common_config.parent, common_config.parent), sort_keys=False))

    # Keep original module names importable from both horizon groups.
    bootstrap_old = "_layout_sys.path.insert(0, str(_layout_parent / 'model'))"
    bootstrap_new = ("_layout_sys.path.insert(0, str(_layout_parent / 'model' / 'model_15 days'))\n"
                     "        _layout_sys.path.insert(0, str(_layout_parent / 'model' / 'model_10 days'))")
    for base in (MODEL, SHORT_RANGE / 'evaluation comparison/common'):
        for path in base.rglob('*.py'):
            if any(p in path.parts for p in ('source_reference', '_vendor', 'archive', 'pretrained')):
                continue
            source = path.read_text(encoding='utf-8-sig')
            save(path, source.replace(bootstrap_old, bootstrap_new))

    compare = SHORT_RANGE / 'evaluation comparison/compare_flood_nonflood.py'
    source = compare.read_text(encoding='utf-8')
    for name, group in GROUPS.items():
        source = source.replace("'" + name + '/', "'" + group + '/' + name + '/')
    save(compare, source)

    for name in ('grrr_lstm', 'grrr_lstm_weighted_fills_rejected'):
        path = MODEL / GROUPS[name] / name / 'compare.py'
        save(path, path.read_text(encoding='utf-8').replace("HERE.parent / 'marala_observed/data/daily_observed_priority.csv'", "HERE.parent / 'discharge_history_lstm/data/daily_observed_priority.csv'"))
    path = MODEL / 'model_15 days/discharge_history_lstm/prepare.py'
    save(path, path.read_text(encoding='utf-8').replace("HERE.parents[1] / 'dataset/", "HERE.parents[2] / 'dataset/"))

    delta = MODEL / 'model_10 days/delta_hbv'
    for relative in ('prepare.py', 'verify.py', 'tests/test_delta_hbv.py'):
        path = delta / relative
        save(path, path.read_text(encoding='utf-8').replace('ROOT.parents[1]', 'ROOT.parents[2]'))
    path = delta / 'evaluate.py'
    source = path.read_text(encoding='utf-8').replace(
        "if cfg[key] != checkpoint['config'][key]:",
        "ignored_paths = {'daily_file', 'static_file', 'forecast_file', 'area_metadata'}\n        current_schema = {k: v for k, v in cfg[key].items() if k not in ignored_paths}\n        saved_schema = {k: v for k, v in checkpoint['config'][key].items() if k not in ignored_paths}\n        if current_schema != saved_schema:")
    save(path, source)
    path = delta / 'README.md'
    source = path.read_text(encoding='utf-8')
    for relative in ('setup_sources.py', 'prepare.py', 'train.py', 'evaluate.py', 'config.yaml'):
        source = source.replace(' delta_hbv/' + relative, " 'model_10 days/delta_hbv/" + relative + "'")
    source = source.replace('-s delta_hbv/tests', "-s 'model_10 days/delta_hbv/tests'")
    save(path, source)

    # Replace the obsolete top index with an explicit, linked horizon index.
    lines = ['# Marala short-range models by saved forecast horizon', '',
             'Models are grouped by the maximum forecast lead in their saved run. A 15-day model includes leads 1-15, including the first ten days.', '',
             '- [10-day models](model_10%20days/README.md): 19 model/run folders.',
             '- [15-day models](model_15%20days/README.md): 5 model/run folders.',
             '- [Evaluation comparisons](../evaluation%20comparison/README.md).', '',
             'There are no combined 10/15-day trained variants. Donor/reference checkpoints remain with the model that uses them. The rejected GRRR-filled run has no retained checkpoint.', '']
    save(MODEL / 'README.md', '\n'.join(lines))
    for group, names, horizon in (('model_10 days', TEN, 10), ('model_15 days', FIFTEEN, 15)):
        lines = [f'# {horizon}-day forecast models', '',
                 '| Model folder | Saved horizon |', '|---|---:|']
        lines += [f'| [{name}]({name}/README.md) | {horizon} days |' for name in names]
        lines += ['', '[All models](../README.md) | [Evaluation comparisons](../../evaluation%20comparison/README.md)', '']
        (MODEL / group / 'README.md').write_text('\n'.join(lines), encoding='utf-8')
    write_json(RECORDS / 'updated_files.json', edits)
    print(f'Updated {len(edits)} files; generated both group indexes.')


def verify():
    protected = json.loads((RECORDS / 'protected_artifacts_before.json').read_text())
    failed = [x['new'] for x in protected if not Path(x['new']).exists() or digest(Path(x['new'])) != x['sha256']]
    if failed:
        raise RuntimeError(f'Protected files changed or missing: {failed}')
    directories = {p.name for p in MODEL.iterdir() if p.is_dir()}
    assert {'model_10 days', 'model_15 days'}.issubset(directories), directories
    assert directories.issubset({'model_10 days', 'model_15 days', 'model_30_days'}), directories
    missing = []
    for name, group in GROUPS.items():
        folder = MODEL / group / name
        if not folder.is_dir():
            missing.append(str(folder))
        path = folder / 'config.yaml'
        if path.exists():
            cfg = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
            target = folder / cfg['data']['daily_file']
            if not target.exists():
                missing.append(str(target))
    assert not missing, missing
    syntax_files = []
    for base in (MODEL, SHORT_RANGE / 'evaluation comparison/common'):
        for path in base.rglob('*.py'):
            if any(p in path.parts for p in ('source_reference', '_vendor', 'archive', 'pretrained')):
                continue
            ast.parse(path.read_text(encoding='utf-8-sig'), filename=str(path))
            syntax_files.append(str(path))
    result = {'ten_day_folders': len(TEN), 'fifteen_day_folders': len(FIFTEEN),
              'mixed_trained_horizons': False, 'protected_files_unchanged': len(protected),
              'all_active_daily_files_exist': True, 'python_files_parse': len(syntax_files)}
    write_json(RECORDS / 'verification.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'update', 'verify'])
    {'prepare': prepare, 'update': update, 'verify': verify}[parser.parse_args().action]()
