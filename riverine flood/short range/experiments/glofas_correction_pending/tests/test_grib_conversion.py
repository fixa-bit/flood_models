import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from glofas_correction.common import save_json
from glofas_correction.data import convert_dataset, validate_archive


class ConversionTests(unittest.TestCase):
    def test_initialization_end_stamp_members_and_units(self):
        with tempfile.TemporaryDirectory() as directory:
            cfg = {"_root": Path(directory), "download": {"grid_report": "grid.json", "system_version": "version_4_0", "max_lead_days": 30}}
            save_json(Path(directory)/"grid.json", {"passed": True, "selected": {"latitude": 32.675, "longitude": 74.475}})
            dates = pd.to_datetime(["2020-06-01", "2020-06-04"])
            ds = xr.Dataset({"dis24": (("time", "number", "step", "latitude", "longitude"), np.full((2,3,30,1,1), 500.))},
                coords={"time": dates, "number": [0,1,2], "step": pd.to_timedelta(np.arange(1,31), unit="D"),
                        "latitude": [32.675], "longitude": [74.475]})
            ds.dis24.attrs["units"] = "m**3 s**-1"
            result = convert_dataset(ds, cfg, "reforecast", "a"*64)
            result = validate_archive(result, cfg)
            self.assertEqual(len(result), 180)
            self.assertEqual(set(result.member), {"0","1","2"})
            self.assertTrue((result.valid_date-result.issue_date == pd.to_timedelta(result.lead_day,unit="D")).all())
            ds.dis24.attrs["units"] = "mm/day"
            with self.assertRaises(ValueError): convert_dataset(ds,cfg,"reforecast","a"*64)


if __name__ == "__main__": unittest.main()
