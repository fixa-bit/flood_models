import tempfile
import unittest
from pathlib import Path
import pandas as pd
from glofas_correction.existing_model import existing_oof, attach


class ExistingModelTests(unittest.TestCase):
    def test_lineage_and_realized_weather_are_screened(self):
        with tempfile.TemporaryDirectory() as temp:
            data = pd.DataFrame({"issue_date": ["2020-06-01"]*3, "horizon": ["day_01", "day_02", "day_03"],
                "p10": 50., "p50": 100., "p90": 200., "fitted_until": "2018-12-31",
                "selected_until": ["2019-12-31", "2020-12-31", "2019-12-31"],
                "forcing_mode": ["archived_forecast", "archived_forecast", "reanalysis_hindcast"]})
            data.to_csv(Path(temp)/"existing.csv", index=False)
            cfg = {"_root": Path(temp), "blending": {"imported_oof_file": "existing.csv", "allow_reanalysis_existing": False}}
            accepted, audit = existing_oof(cfg)
            self.assertEqual(accepted.horizon.tolist(), ["day_01"])
            self.assertEqual(audit["leakage_rows_excluded"], 1)
            self.assertEqual(audit["reanalysis_rows_excluded"], 1)

    def test_missing_existing_predictions_remain_missing(self):
        frame = pd.DataFrame({"issue_date": pd.to_datetime(["2020-06-01"]), "horizon": ["week_4"]})
        output = attach(frame, pd.DataFrame())
        self.assertTrue(output.existing_p50.isna().all())


if __name__ == "__main__": unittest.main()
