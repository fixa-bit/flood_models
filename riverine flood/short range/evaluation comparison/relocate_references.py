"""Update active references after moving comparisons beside model/."""
from pathlib import Path
import json

COMPARISON = Path(__file__).resolve().parent
SHORT_RANGE = COMPARISON.parent
MODEL = SHORT_RANGE / 'model'
changed = []


def update(path, transform):
    original = path.read_text(encoding='utf-8-sig')
    revised = transform(original)
    if revised != original:
        path.write_text(revised, encoding='utf-8')
        changed.append(str(path.relative_to(SHORT_RANGE)))


# Active configs live directly inside their model folder.
for folder in MODEL.iterdir():
    if not folder.is_dir():
        continue
    for path in folder.iterdir():
        if path.is_file() and path.suffix in ('.yaml', '.yml', '.json'):
            update(path, lambda s: s.replace('../evaluation comparison/', '../../evaluation comparison/'))
        if path.is_file() and path.suffix.lower() == '.md':
            update(path, lambda s: s.replace('../evaluation%20comparison/', '../../evaluation%20comparison/'))
update(MODEL / 'README.md', lambda s: s.replace('(evaluation%20comparison/', '(../evaluation%20comparison/'))

# The nearest ancestor containing the comparison folder is now short range/.
for base in (MODEL, COMPARISON / 'common'):
    for path in base.rglob('*.py'):
        if any(part in ('archive', 'source_reference', 'pretrained') for part in path.relative_to(base).parts):
            continue
        update(path, lambda s: s.replace(
            '_layout_sys.path.insert(0, str(_layout_parent))',
            "_layout_sys.path.insert(0, str(_layout_parent / 'model'))"))

common_config = COMPARISON / 'common/config.yaml'
update(common_config, lambda s: s.replace('../../lstm/', '../../model/lstm/')
       .replace('../../gradient_boosting/', '../../model/gradient_boosting/')
       .replace('../../persistence/', '../../model/persistence/')
       .replace('../../climatology/', '../../model/climatology/')
       .replace('../../ensemble/', '../../model/ensemble/'))

update(COMPARISON / 'compare_flood_nonflood.py', lambda s: s.replace(
    'ROOT = Path(__file__).resolve().parents[1]',
    "ROOT = Path(__file__).resolve().parent.parent / 'model'").replace(
    "ROOT / 'evaluation comparison/", "ROOT.parent / 'evaluation comparison/"))
update(COMPARISON / 'verify_layout.py', lambda s: s.replace(
    'root = Path(__file__).resolve().parents[1]',
    "root = Path(__file__).resolve().parent.parent / 'model'").replace(
    "root / \"evaluation comparison/", "root.parent / \"evaluation comparison/").replace(
    "scan_roots = (root, root.parent /", "scan_roots = (root, root.parent / 'evaluation comparison', root.parent /"))

(COMPARISON / 'relocation_manifest.json').write_text(json.dumps({
    'old': str(MODEL / 'evaluation comparison'),
    'new': str(COMPARISON),
    'updated_files': changed,
}, indent=2) + '\n', encoding='utf-8')
print(f'Updated {len(changed)} active files.')
