import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import ee
from ee import apitestcase
import extract_snow as snow


class GraphTests(apitestcase.ApiTestCase):
    def test_bands_units_and_requested_scale(self):
        snow.ee = ee
        table = snow.daily_table(snow.date(1980, 1, 1), snow.date(1980, 1, 3),
                                  ee.Geometry.Rectangle([74, 32, 78, 35]))
        graph = table.serialize()
        for expected in ('snow_depth_water_equivalent', 'snow_depth', 'snowmelt_sum', '1000', '11132', 'Reducer.mean'):
            self.assertIn(expected, graph)
        self.assertTrue(table.getDownloadURL(filetype='CSV', selectors=['date', *snow.FEATURES]))


class MergeTests(unittest.TestCase):
    def test_zero_snow_missing_and_column_units(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for column, (folder, _) in snow.FEATURES.items():
                (root / folder).mkdir()
                snow.write_csv(root / folder / '1980.csv', ['date', column],
                               [{'date': '1980-01-01', column: 0}, {'date': '1980-01-03', column: 2}])
            with contextlib.redirect_stdout(io.StringIO()):
                snow.merge(root, snow.date(1980, 1, 1), snow.date(1980, 1, 4))
            with (root / 'marala_daily_snow_1980_2024.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(list(rows[0]), ['date', 'swe_mm', 'snow_depth_m', 'snowmelt_mm'])
            self.assertEqual(rows[0]['swe_mm'], '0.0')
            self.assertEqual(rows[1]['snow_depth_m'], 'NaN')
            report = json.loads((root / 'snow_quality_report.json').read_text())
            self.assertEqual(report['snowmelt_mm']['units'], 'mm/day')
            self.assertEqual(report['swe_mm']['missing_days'], ['1980-01-02'])
            self.assertEqual(report['snow_depth_m']['max'], 2)


if __name__ == '__main__':
    unittest.main()
