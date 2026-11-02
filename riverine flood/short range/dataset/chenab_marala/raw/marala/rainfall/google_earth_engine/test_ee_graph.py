"""Compile actual Earth Engine graphs against the API's offline test catalog.

Run with .venv/Scripts/python.exe test_ee_graph.py after installing requirements.
This checks graph construction and export calls; it does not evaluate real data.
"""
from datetime import date
from types import SimpleNamespace
import unittest

import ee
from ee import apitestcase
import extract_precipitation as precipitation


class GraphTests(apitestcase.ApiTestCase):
    def test_daily_graphs_and_csv_exports(self):
        precipitation.ee = ee
        geometry = ee.Geometry.Rectangle([74, 32, 78, 35])
        projection = {'crs': 'EPSG:4326', 'transform': [.1, 0, -180, 0, -.1, 90]}
        for key in precipitation.PRODUCTS:
            with self.subTest(product=key):
                table = precipitation.daily_features(key, date(2024, 1, 1), date(2024, 1, 3),
                                                     geometry, projection, SimpleNamespace(min_coverage=.999))
                self.assertIn('Reducer.splitWeights', table.serialize())
                url = table.getDownloadURL(filetype='CSV', selectors=precipitation.FIELDS)
                self.assertTrue(url)


if __name__ == '__main__':
    unittest.main()
