import unittest
import ee
from ee import apitestcase
import extract_static_attributes as static


class StaticGraphTests(apitestcase.ApiTestCase):
    def setUp(self):
        super().setUp()
        static.ee = ee

    def test_area_weighted_mean_requested_scale(self):
        graph = static.area_means(ee.Image.constant([10, 20]).rename(['sand_pct', 'clay_pct']),
                                  ee.Geometry.Rectangle([74, 32, 78, 35]), 250, 'EPSG:4326').serialize()
        for value in ('Image.pixelArea', 'Reducer.sum', '250', '10000000000000', 'weight_area'):
            self.assertIn(value, graph)

    def test_depth_integration_and_exhaustive_bands(self):
        soil = ee.Image.constant([10, 20, 40]).rename(['b0', 'b10', 'b30'])
        self.assertIn('Image.divide', static.soil_0_30(soil).serialize())
        graph = static.elevation_masks(ee.Image.constant(4500)).serialize()
        for expected in ('frac_band1', 'frac_band2', 'frac_band3', 'frac_band4', 'Image.lte', 'Image.gt'):
            self.assertIn(expected, graph)


if __name__ == '__main__':
    unittest.main()
