import contextlib
import csv
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import ee
from ee import apitestcase
import extract_temperature as temperature


class TemperatureGraphTests(apitestcase.ApiTestCase):
    def test_native_weighted_daily_graph_and_kelvin_conversion(self):
        temperature.ee = ee
        table = temperature.daily_table(temperature.shared.date(2024, 1, 1), temperature.shared.date(2024, 1, 3),
                                        ee.Geometry.Rectangle([74, 32, 78, 35]),
                                        {'crs': 'EPSG:4326', 'transform': [.1, 0, -180.05, 0, -.1, 90.05]}, .999)
        graph = table.serialize()
        self.assertIn('Reducer.splitWeights', graph)
        self.assertIn('273.15', graph)
        self.assertTrue(table.getDownloadURL(filetype='CSV', selectors=temperature.FIELDS))


class TemperatureMergeTests(unittest.TestCase):
    def test_negative_celsius_and_leap_day_preserved(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / 'chunks/era5land_temperature_2m'
            folder.mkdir(parents=True)
            with (folder / 'fixture.csv').open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=temperature.FIELDS)
                writer.writeheader()
                for day in temperature.shared.days():
                    writer.writerow({'date': str(day), temperature.VALUE: -5, 'coverage_fraction': 1, 'n_images': 1})
            with contextlib.redirect_stdout(io.StringIO()):
                temperature.merge(SimpleNamespace(output=root, min_coverage=.999))
            report = json.loads((root / 'quality_report.json').read_text())
            self.assertTrue(report['qa_passed'])
            self.assertEqual(report['valid_days'], 16437)
            self.assertEqual(report['min_c'], -5)
            with (root / 'marala_daily_temperature_1980_2024.csv').open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(next(row for row in rows if row['date'] == '2000-02-29')[temperature.VALUE], '-5.0')


if __name__ == '__main__':
    unittest.main()
