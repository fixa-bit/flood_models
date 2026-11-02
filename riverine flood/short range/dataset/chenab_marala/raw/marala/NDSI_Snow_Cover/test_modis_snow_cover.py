import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import ee
from ee import apitestcase
import extract_modis_snow_cover as modis


class GraphTests(apitestcase.ApiTestCase):
    def test_whole_catchment_validity_and_native_grid(self):
        modis.ee = ee
        table = modis.daily_table(modis.START, modis.START + modis.timedelta(days=2),
                                  ee.Geometry.Rectangle([74, 32, 78, 35]), ee.Projection('SR-ORG:6974'))
        graph = table.serialize()
        for expected in ('NDSI_Snow_Cover', 'Image.unmask', 'sameFootprint', 'Reducer.mean', '500', '10000000000000', 'SR-ORG:6974'):
            self.assertIn(expected, graph)
        self.assertTrue(table.getDownloadURL(filetype='CSV', selectors=modis.COLUMNS))


class MergeTests(unittest.TestCase):
    def test_cached_seven_day_request_is_reused_when_finishing_year(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / 'chunks').mkdir()
            start, stop = modis.date(2001, 1, 1), modis.date(2001, 1, 8)
            saved = [{'date': day, 'snow_cover_pct': 0, 'valid_frac': 1} for day in modis.dates(start, stop)]
            modis.write_csv(root / 'chunks/2001-01-01_2001-01-08.csv', saved)
            requested = []
            def fake_download(begin, end, polygon, projection):
                requested.append(begin)
                return [{'date': day, 'snow_cover_pct': 20, 'valid_frac': .5} for day in modis.dates(begin, end)]
            with patch.object(modis, 'download', side_effect=fake_download), contextlib.redirect_stdout(io.StringIO()):
                modis.download_year(2001, None, None, root)
            self.assertNotIn(start, requested)
            with (root / '2001.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 365)
            self.assertEqual(rows[0]['snow_cover_pct'], '0')
            self.assertEqual(rows[-1]['date'], '2001-12-31')

    def test_valid_zero_cloud_day_and_absent_export(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            modis.write_csv(root / '2000.csv', [{'date': '2000-03-01', 'snow_cover_pct': 0, 'valid_frac': .4},
                                               {'date': '2000-03-02', 'snow_cover_pct': '', 'valid_frac': 0}])
            with contextlib.redirect_stdout(io.StringIO()):
                modis.merge(root, modis.START, modis.START + modis.timedelta(days=3))
            with (root / 'marala_daily_modis_snow_cover_2000_2024.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(rows[0]['snow_cover_pct'], '0.0')
            self.assertEqual(rows[0]['valid_frac'], '0.4')
            self.assertEqual(rows[1]['snow_cover_pct'], 'NaN')
            self.assertEqual(rows[1]['valid_frac'], '0.0')
            self.assertEqual(rows[2]['valid_frac'], 'NaN')
            report = json.loads((root / 'quality_report.json').read_text())
            self.assertEqual(report['valid_frac']['missing_days'], ['2000-03-03'])
            self.assertEqual(report['snow_cover_pct']['missing_days'], ['2000-03-02', '2000-03-03'])


if __name__ == '__main__':
    unittest.main()
