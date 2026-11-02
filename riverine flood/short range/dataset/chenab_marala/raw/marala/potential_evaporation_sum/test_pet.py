import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
import unittest

import ee
from ee import apitestcase
import extract_pet as pet


class GraphTests(apitestcase.ApiTestCase):
    def test_source_sign_conversion_and_requested_scale(self):
        pet.ee = ee
        table = pet.daily_table(1980, ee.Geometry.Rectangle([74, 32, 78, 35]))
        graph = table.serialize()
        for expected in ('potential_evaporation_sum', '1000', '-1', '11132', 'Reducer.mean'):
            self.assertIn(expected, graph)
        self.assertTrue(table.getDownloadURL(filetype='CSV', selectors=['date', 'pet_mm']))


class MergeTests(unittest.TestCase):
    def test_zero_missing_and_negative_result_are_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            pet.write_csv(root / '1980.csv', [{'date': '1980-01-01', 'pet_mm': 0},
                                              {'date': '1980-01-03', 'pet_mm': -.01}])
            with contextlib.redirect_stdout(io.StringIO()):
                pet.merge(root, pet.date(1980, 1, 1), pet.date(1980, 1, 4))
            with (root / 'marala_daily_pet_1980_2024.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(list(rows[0]), ['date', 'pet_mm'])
            self.assertEqual(rows[0]['pet_mm'], '0.0')
            self.assertEqual(rows[1]['pet_mm'], 'NaN')
            self.assertEqual(rows[2]['pet_mm'], '-0.01')
            report = json.loads((root / 'quality_report.json').read_text())
            self.assertEqual(report['missing_days'], ['1980-01-02'])
            self.assertEqual(report['negative_after_sign_reversal'], 1)


if __name__ == '__main__':
    unittest.main()
