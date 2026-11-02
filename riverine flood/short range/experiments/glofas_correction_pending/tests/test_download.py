import unittest
import numpy as np
import xarray as xr
from glofas_correction.download import select_cell, request_for


class DownloadTests(unittest.TestCase):
    def station(self):
        return {"latitude": 32.67, "longitude": 74.46, "search_radius_km": 15,
                "relative_area_tolerance": .2, "selection": "nearest_area_match",
                "area_source": "synthetic test", "cell_override": None}

    def grid(self):
        ds = xr.Dataset({"uparea": (("latitude", "longitude"), np.array([[100., 28000.], [8000., 29000.]])*1e6)},
                        coords={"latitude": [32.675, 32.625], "longitude": [74.475, 74.525]})
        ds.uparea.attrs["units"] = "m2"
        return ds

    def test_area_match_reports_nearest_cell_mismatch(self):
        report = select_cell(self.grid(), self.station(), 28794.)
        self.assertTrue(report["passed"])
        self.assertEqual(report["geographically_nearest"]["upstream_area_km2"], 100.)
        self.assertAlmostEqual(report["selected"]["upstream_area_km2"], 28000.)

    def test_nearest_cell_mode_fails_instead_of_silent_snap(self):
        station = self.station()
        station["selection"] = "nearest_cell"
        self.assertFalse(select_cell(self.grid(), station, 28794.)["passed"])

    def test_no_area_match_fails_and_unknown_units_rejected(self):
        self.assertFalse(select_cell(self.grid(), self.station(), 100000.)["passed"])
        ds = self.grid()
        ds.uparea.attrs["units"] = "unknown"
        with self.assertRaises(ValueError): select_cell(ds, self.station(), 28794.)

    def test_forecast_and_reforecast_request_schemas(self):
        cfg = {"download": {"system_version": "version_4_0", "hydrological_model": "lisflood", "max_lead_days": 30}}
        cell = {"latitude": 32.675, "longitude": 74.475}
        forecast = request_for(cfg, "forecast", 2026, 10, [29], cell)
        hindcast = request_for(cfg, "reforecast", 2020, 6, [1, 2], cell)
        self.assertEqual(forecast["leadtime_hour"][-1], "720")
        self.assertEqual(forecast["year"], "2026")
        self.assertEqual(hindcast["hyear"], "2020")
        self.assertEqual(hindcast["hday"], ["01", "02"])
        self.assertNotIn("year", hindcast)
        self.assertIn("ensemble_perturbed_reforecast", hindcast["product_type"])
        self.assertEqual(forecast["system_version"], "operational")


if __name__ == "__main__": unittest.main()
