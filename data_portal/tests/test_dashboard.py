import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_dashboard as dashboard


class IntegrityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.model = self.root / 'riverine flood/short range/dataset/chenab_marala'
        self.source = self.model / 'raw/marala/discharge/wapda'
        self.source.mkdir(parents=True)
        self.file = self.source / 'sample.xls'
        self.file.write_bytes(b'original')
        self.expected = hashlib.sha256(b'original').hexdigest()
        (self.source / 'source_receipt.json').write_text(json.dumps({'filename': 'sample.xls', 'sha256': self.expected, 'source_url': 'https://example.org/source'}))
        self.patches = [patch.object(dashboard, 'WORKSPACE', self.root), patch.object(dashboard, 'MODEL', self.model), patch.object(dashboard, 'PROCESSED', self.model / 'processed/marala')]
        for item in self.patches:
            item.start()

    def tearDown(self):
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def test_tampered_file_is_not_reported_as_verified(self):
        self.assertEqual(dashboard.collect_integrity()['counts'], {'match': 1})
        self.file.write_bytes(b'tampered')
        self.assertEqual(dashboard.collect_integrity()['counts'], {'mismatch': 1})

    def test_missing_file_remains_in_ledger(self):
        self.file.unlink()
        result = dashboard.collect_integrity()
        self.assertEqual(result['counts'], {'missing': 1})
        self.assertEqual(len(result['files']), 1)

    def test_duplicate_claims_do_not_inflate_checked_count(self):
        (self.source / 'another_receipt.json').write_text(json.dumps({'filename': 'sample.xls', 'sha256': self.expected}))
        self.assertEqual(dashboard.collect_integrity()['counts'], {'match': 1})

    def test_conflicting_claims_cannot_be_silently_chosen(self):
        (self.source / 'another_receipt.json').write_text(json.dumps({'filename': 'sample.xls', 'sha256': '0' * 64}))
        self.assertEqual(dashboard.collect_integrity()['counts'], {'conflicting_claims': 1})

    def test_outside_workspace_claim_is_ignored(self):
        (self.source / 'outside_receipt.json').write_text(json.dumps({'raw_file': '../../outside.txt', 'sha256': self.expected}))
        self.assertEqual(dashboard.collect_integrity()['counts'], {'match': 1})


class AssetRefreshTests(unittest.TestCase):
    def test_changed_script_gets_new_url_without_reusing_cached_script(self):
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder)
            (dist / 'assets').mkdir()
            script = dist / 'assets/app.js'
            script.write_text('old overview-only application', encoding='utf-8')
            index = dist / 'index.html'
            index.write_text('<script src="assets/app.js"></script>', encoding='utf-8')
            with patch.object(dashboard, 'DIST', dist):
                old = dashboard.version_assets()
                script.write_text('application with summary route', encoding='utf-8')
                new = dashboard.version_assets()
            self.assertNotEqual(old['assets/app.js'], new['assets/app.js'])
            self.assertIn('assets/app.js?v=' + new['assets/app.js'], index.read_text())
            self.assertNotIn(old['assets/app.js'], index.read_text())

    def test_unchanged_assets_keep_urls_and_do_not_accumulate_queries(self):
        with tempfile.TemporaryDirectory() as folder:
            dist = Path(folder)
            (dist / 'assets').mkdir()
            (dist / 'assets/summary.js').write_text('summary', encoding='utf-8')
            index = dist / 'index.html'
            index.write_text('<script src="assets/summary.js?v=old"></script>', encoding='utf-8')
            with patch.object(dashboard, 'DIST', dist):
                first = dashboard.version_assets()
                content = index.read_bytes()
                second = dashboard.version_assets()
            self.assertEqual(first, second)
            self.assertEqual(content, index.read_bytes())
            self.assertEqual(content.count(b'?v='), 1)


class CoverageTests(unittest.TestCase):
    def test_missing_and_withheld_days_reduce_coverage(self):
        rows = [{'date': '2024-02-27', 'valid': True}, {'date': '2024-02-29', 'valid': False}]
        february = next(r for r in dashboard.month_coverage(rows, lambda r: r['valid']) if r['month'] == 2)
        self.assertEqual(february['expected'], 3)
        self.assertEqual(february['valid'], 1)
        self.assertAlmostEqual(february['fraction'], 1/3)

    def test_missing_days_break_plot_lines(self):
        rows = [{'date': '2025-06-01', 'value': '1'}, {'date': '2025-06-03', 'value': '3'}]
        result = dashboard.interval_series(rows, 'value')
        self.assertEqual(result[1], {'date': '2025-06-02', 'value': None})


if __name__ == '__main__':
    unittest.main()
