"""Check conservation, boundary-cell selection and missing-data behavior."""
import unittest

from shapely.geometry import box

from collect_marala_rainfall import aggregate_day, select_cells


class CatchmentRainfallTests(unittest.TestCase):
    def test_constant_rainfall_is_conserved(self):
        cells, _, gap = select_cells(box(74.1, 32.1, 75.1, 33.1))
        mean, fraction, count = aggregate_day(cells, {c["cell_id"]: 17.25 for c in cells})
        self.assertAlmostEqual(mean, 17.25, places=9)
        self.assertAlmostEqual(fraction, 1, places=9)
        self.assertEqual(count, len(cells))
        self.assertLess(gap, 1e-9)

    def test_cell_center_outside_basin_still_contributes(self):
        # This tiny basin crosses a cell edge; neither center is in the basin.
        basin = box(74.06, 32.95, 74.07, 33.05)
        cells, _, _ = select_cells(basin)
        self.assertEqual({c["longitude"] for c in cells}, {73.75, 74.375})
        self.assertTrue(all(c["area_weight"] > 0 for c in cells))
        self.assertAlmostEqual(sum(c["area_weight"] for c in cells), 1, places=9)

    def test_missing_small_cell_cannot_be_silently_ignored(self):
        cells = [{"cell_id": "large", "area_weight": .999}, {"cell_id": "small", "area_weight": .001}]
        mean, fraction, count = aggregate_day(cells, {"large": 10, "small": None})
        self.assertIsNone(mean)
        self.assertEqual(fraction, .999)
        self.assertEqual(count, 1)

    def test_area_weights_control_mean_and_outside_values_do_not(self):
        cells = [{"cell_id": "a", "area_weight": .25}, {"cell_id": "b", "area_weight": .75}]
        mean, fraction, count = aggregate_day(cells, {"a": 4, "b": 20, "outside": 999})
        self.assertEqual(mean, 16)
        self.assertEqual(fraction, 1)
        self.assertEqual(count, 2)


if __name__ == "__main__":
    unittest.main()
