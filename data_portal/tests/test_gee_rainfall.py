import csv
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_dashboard as dashboard


class EarthEngineAdapterTests(unittest.TestCase):
    def fixture(self, folder):
        path = folder / 'marala_daily_precipitation_1980_2024.csv'
        with path.open('w', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['date', *dashboard.GEE_PRODUCTS])
            start = dashboard.date(1980, 1, 1)
            for offset in range((dashboard.date(2025, 1, 1) - start).days):
                day = str(start + dashboard.timedelta(days=offset))
                writer.writerow([day, *[1 if day >= available else 'NaN'
                                        for _, available in dashboard.GEE_PRODUCTS.values()]])
        qa = {'qa_passed': True, 'merged_csv_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
              'products': {key: {'units': 'mm/day'} for key in dashboard.GEE_PRODUCTS}}
        (folder / 'quality_report.json').write_text(json.dumps(qa))
        return path, qa

    def test_no_exports_produce_no_traces(self):
        with tempfile.TemporaryDirectory() as temp:
            sources, status = dashboard.load_gee_rainfall(Path(temp))
            self.assertEqual(sources, [])
            self.assertEqual(status['state'], 'not_collected')

    def test_checked_exports_keep_expected_nan_and_zero(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, qa = self.fixture(root)
            path.write_text(path.read_text().replace('1980-01-01,1,', '1980-01-01,0,', 1))
            qa['merged_csv_sha256'] = hashlib.sha256(path.read_bytes()).hexdigest()
            (root / 'quality_report.json').write_text(json.dumps(qa))
            sources, status = dashboard.load_gee_rainfall(root)
            self.assertEqual(status['state'], 'ready')
            self.assertEqual(len(sources), 4)
            self.assertEqual(len(sources[0]['rows']), 16437)
            self.assertEqual(sources[0]['rows'][0]['value'], 0)
            self.assertIsNone(sources[3]['rows'][0]['value'])

    def test_changed_export_is_withheld(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path, _ = self.fixture(root)
            with path.open('a') as stream:
                stream.write('\n')
            sources, status = dashboard.load_gee_rainfall(root)
            self.assertEqual(sources, [])
            self.assertEqual(status['state'], 'withheld')

    def test_failed_qa_is_withheld(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            _, qa = self.fixture(root)
            qa['qa_passed'] = False
            (root / 'quality_report.json').write_text(json.dumps(qa))
            self.assertEqual(dashboard.load_gee_rainfall(root)[1]['state'], 'withheld')


if __name__ == '__main__':
    unittest.main()
