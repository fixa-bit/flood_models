"""Repair standalone tests and legacy preparation paths after horizon grouping."""
import ast
import json
from pathlib import Path

import yaml

SHORT = Path(__file__).resolve().parents[2]
MODEL = SHORT / 'model'
CHANGED = []


def write(path, text):
    original = path.read_text(encoding='utf-8-sig')
    if original != text:
        path.write_text(text, encoding='utf-8')
        CHANGED.append(str(path.relative_to(SHORT)))


def add_test_bootstrap(path):
    text = path.read_text(encoding='utf-8-sig')
    if '# Horizon-group test imports.' in text:
        return
    tree = ast.parse(text)
    position = 0
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            position = node.end_lineno
        elif isinstance(node, ast.ImportFrom) and node.module == '__future__':
            position = node.end_lineno
        else:
            break
    lines = text.splitlines(keepends=True)
    block = ("# Horizon-group test imports.\n"
             "import sys as _test_sys\nfrom pathlib import Path as _TestPath\n"
             "for _test_parent in _TestPath(__file__).resolve().parents:\n"
             "    if (_test_parent / 'evaluation comparison' / 'common').is_dir():\n"
             "        _test_sys.path.insert(0, str(_test_parent / 'model' / 'model_15 days'))\n"
             "        _test_sys.path.insert(0, str(_test_parent / 'model' / 'model_10 days'))\n"
             "        _test_sys.path.insert(0, str(_test_parent / 'evaluation comparison' / 'common'))\n"
             "        break\n\n")
    write(path, ''.join(lines[:position]) + block + ''.join(lines[position:]))


for name, group in [('encoder_decoder_lstm', 'model_15 days'),
                    ('fine_tuned_global_pretrained_lstm', 'model_10 days'),
                    ('spatially_distributed_model', 'model_10 days'),
                    ('hybrid_physics_ml', 'model_10 days')]:
    for path in (MODEL / group / name / 'tests').glob('test_*.py'):
        add_test_bootstrap(path)


def paths(obj, base):
    if isinstance(obj, dict):
        return {k: paths(v, base) for k, v in obj.items()}
    if isinstance(obj, list):
        return [paths(v, base) for v in obj]
    if not isinstance(obj, str) or '://' in obj or not obj.startswith(('../', './')):
        return obj
    resolved = (base / obj).resolve()
    replacements = [(MODEL / 'dataset', SHORT / 'dataset'),
                    (SHORT / 'evaluation comparison/dataset', SHORT / 'dataset'),
                    (MODEL / 'data', SHORT / 'evaluation comparison/common/data')]
    import os
    for old, new in replacements:
        try:
            target = new / resolved.relative_to(old)
        except ValueError:
            continue
        return Path(os.path.relpath(target, base)).as_posix()
    return obj


for group in ('model_10 days', 'model_15 days'):
    for folder in (MODEL / group).iterdir():
        if not folder.is_dir():
            continue
        for path in folder.glob('*.yaml'):
            cfg = yaml.safe_load(path.read_text(encoding='utf-8-sig'))
            write(path, yaml.safe_dump(paths(cfg, folder), sort_keys=False))
path = SHORT / 'evaluation comparison/common/config.yaml'
write(path, yaml.safe_dump(paths(yaml.safe_load(path.read_text(encoding='utf-8-sig')), path.parent), sort_keys=False))

# Keep the original artifact verifier useful with the new two-level grouping.
path = SHORT / 'evaluation comparison/verify_layout.py'
text = path.read_text(encoding='utf-8').replace(
    "len([p for p in root.iterdir() if p.is_dir() and p.name != \"evaluation comparison\"])",
    "sum(len([p for p in group.iterdir() if p.is_dir()]) for group in root.iterdir() if group.is_dir() and group.name in ('model_10 days', 'model_15 days'))")
write(path, text)
path = SHORT / 'evaluation comparison/README.md'
text = path.read_text(encoding='utf-8')
note = '\nModels are now indexed in `model/model_10 days/` and `model/model_15 days/`; this comparison folder remains outside `model/`.\n'
if note.strip() not in text:
    write(path, text + note)
Path(__file__).with_name('additional_updated_files.json').write_text(json.dumps(CHANGED, indent=2) + '\n', encoding='utf-8')
print(f'Repaired {len(CHANGED)} standalone test/preparation references.')
