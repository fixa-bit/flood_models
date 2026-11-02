"""Verify the reorganization preserved saved binary and data artifacts."""
import hashlib
import json
from collections import defaultdict
from pathlib import Path

root = Path(__file__).resolve().parent.parent / 'model'
saved = json.loads((root.parent / "evaluation comparison/organization_artifacts_before.json").read_text(encoding="utf-8-sig"))
expected = defaultdict(list)
for item in saved:
    expected[item["bytes"]].append(item)
found = {}
scan_roots = (root, root.parent / 'evaluation comparison', root.parent / "experiments/glofas_correction_pending")
for scan_root in scan_roots:
    if not scan_root.exists():
        continue
    for path in scan_root.rglob("*"):
        if not path.is_file() or path.stat().st_size not in expected:
            continue
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if any(item["sha256"] == digest for item in expected[path.stat().st_size]):
            found.setdefault(digest, str(path))
missing = [item for item in saved if item["sha256"] not in found]
result = {
    "original_artifacts": len(saved),
    "preserved_artifacts": len(saved) - len(missing),
    "missing": missing,
    "model_folders": sum(len([p for p in group.iterdir() if p.is_dir()]) for group in root.iterdir() if group.is_dir() and group.name in ('model_10 days', 'model_15 days')),
    "source_daily_sha256": hashlib.sha256((root.parent / "evaluation comparison/common/data/marala_daily.csv").read_bytes()).hexdigest(),
}
target = root.parent / "evaluation comparison/organization_verification.json"
target.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps({key: value for key, value in result.items() if key != "missing"}, indent=2))
if missing:
    print("Missing paths:", [item["path"] for item in missing])
    raise SystemExit(1)
