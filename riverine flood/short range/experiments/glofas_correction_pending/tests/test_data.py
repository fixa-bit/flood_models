import copy
import tempfile
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
from glofas_correction.common import save_json
from glofas_correction.data import validate_archive, feature_table, causal_gauge_features


def example(cfg, years=(2018, 2019, 2020), step=3):
    rows = []
    dates = pd.date_range(f"{min(years)-1}-01-01", f"{max(years)+1}-12-31")
    t = np.arange(len(dates))
    obs = pd.DataFrame({"q_cumecs": 500+200*np.sin(t/30)+100*np.cos(t/7)}, index=dates)
    for year in years:
        for issue in pd.date_range(f"{year}-06-01", f"{year}-07-20", freq=f"{step}D"):
            for member in range(3):
                for lead in range(1, 31):
                    valid = issue+pd.Timedelta(days=lead)
                    rows.append({"issue_date": issue, "valid_date": valid, "lead_day": lead, "member": str(member),
                        "q_cumecs": float(obs.q_cumecs.loc[valid]-50+(member-1)*30), "product_kind": "reforecast",
                        "system_version": "version_4_0", "cell_latitude": 32.675, "cell_longitude": 74.475, "source_sha256": "a"*64})
    return pd.DataFrame(rows), obs


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.cfg = {"_root": Path(self.temp.name), "download": {"system_version": "version_4_0", "max_lead_days": 30,
            "grid_report": "grid.json", "expected_reforecast_members": 3, "publication_lag_hours": 12},
            "experiment": {"observation_lag_days": 1, "monsoon_months": [6,7,8,9]}}
        save_json(Path(self.temp.name)/"grid.json", {"passed": True, "selected": {"latitude": 32.675, "longitude": 74.475}})

    def test_schema_forbids_historical_substitution_and_duplicate_members(self):
        f, _ = example(self.cfg, years=(2018,))
        self.assertEqual(len(validate_archive(f, self.cfg)), len(f))
        wrong = f.copy()
        wrong["product_kind"] = "historical"
        with self.assertRaises(ValueError): validate_archive(wrong, self.cfg)
        with self.assertRaises(ValueError): validate_archive(pd.concat([f, f.iloc[:1]]), self.cfg)

    def test_weekly_maximum_and_missing_observations(self):
        f, obs = example(self.cfg, years=(2018,))
        table = feature_table(f, obs, self.cfg)
        row = table[table.horizon == "week_3"].iloc[0]
        dates = pd.date_range(row.valid_start, row.valid_date)
        self.assertAlmostEqual(row.observed, obs.q_cumecs.loc[dates].max())
        obs.loc[dates[0], "q_cumecs"] = np.nan
        after = feature_table(f, obs, self.cfg)
        selected = after[(after.issue_date == row.issue_date) & (after.horizon == row.horizon)].iloc[0]
        self.assertTrue(np.isnan(selected.observed))

    def test_future_observations_do_not_change_issue_features(self):
        f, obs = example(self.cfg, years=(2018,))
        issue = pd.Timestamp("2018-06-10")
        before = causal_gauge_features(obs, [issue], self.cfg, f)
        obs.loc[issue:, "q_cumecs"] = 999999
        after = causal_gauge_features(obs, [issue], self.cfg, f)
        pd.testing.assert_frame_equal(before, after)


if __name__ == "__main__": unittest.main()
