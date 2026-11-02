import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import ee
from ee import apitestcase
import extract_dewpoint_ssrd as extraction


class GraphTests(apitestcase.ApiTestCase):
    def test_requested_bands_conversions_and_scale(self):
        extraction.ee = ee
        table = extraction.yearly_table(extraction.date(1980, 1, 1), extraction.date(1980, 1, 3),
                                         ee.Geometry.Rectangle([74, 32, 78, 35]))
        graph = table.serialize()
        for expected in ('dewpoint_temperature_2m', 'surface_solar_radiation_downwards_sum', '273.15', '86400', '11132', 'Reducer.mean'):
            self.assertIn(expected, graph)
        self.assertTrue(table.getDownloadURL(filetype='CSV', selectors=['date', *extraction.FOLDERS]))


class MergeTests(unittest.TestCase):
    def test_negative_dewpoint_zero_radiation_and_missing_day(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for column, folder in extraction.FOLDERS.items():
                (root / folder).mkdir()
                rows = [{'date': '1980-01-01', column: -5 if column == 'dewpoint_c' else 0},
                        {'date': '1980-01-03', column: 2 if column == 'dewpoint_c' else 100}]
                extraction.write_csv(root / folder / '1980.csv', ['date', column], rows)
            with contextlib.redirect_stdout(io.StringIO()):
                extraction.merge(root, extraction.date(1980, 1, 1), extraction.date(1980, 1, 4))
            with (root / 'marala_daily_dewpoint_ssrd_1980_2024.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(list(rows[0]), ['date', 'dewpoint_c', 'ssrd_wm2'])
            self.assertEqual(rows[0]['dewpoint_c'], '-5.0')
            self.assertEqual(rows[0]['ssrd_wm2'], '0.0')
            self.assertEqual(rows[1]['dewpoint_c'], 'NaN')
            report = json.loads((root / 'dewpoint_ssrd_quality_report.json').read_text())
            self.assertEqual(report['ssrd_wm2']['missing_days'], ['1980-01-02'])
            self.assertEqual(report['dewpoint_c']['min'], -5)


if __name__ == '__main__':
    unittest.main()
