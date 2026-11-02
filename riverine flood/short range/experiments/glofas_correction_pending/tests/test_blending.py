import unittest
import numpy as np
import pandas as pd
from glofas_correction.blending import OOFBlender


class BlendTests(unittest.TestCase):
    def data(self):
        dates = pd.date_range("2020-06-01", periods=80)
        y = np.arange(80.)+100
        return pd.DataFrame({"issue_date": dates, "valid_date": dates+pd.Timedelta(days=1), "horizon": "day_01",
            "raw_p50": y-50, "corrected_p50": y, "existing_p50": y+20, "observed": y,
            "base_fitted_until": pd.Timestamp("2019-12-31"), "post_fitted_until": pd.Timestamp("2019-12-31"),
            "existing_fitted_until": pd.Timestamp("2018-12-31"), "existing_selected_until": pd.Timestamp("2019-12-31")})

    def test_oof_selection_convex_weights_and_peak_preservation(self):
        model = OOFBlender().fit(self.data())
        weights = model.weights["day_01"]
        self.assertAlmostEqual(sum(weights.values()), 1.)
        self.assertTrue(all(value >= 0 for value in weights.values()))
        # Several combinations can fit this example perfectly; require the fitted
        # forecast, not one arbitrary parameterization, to reproduce observations.
        self.assertLess(model.audit["day_01"]["weighted_oof_mae"], 1e-4)
        q, used = model.combine("day_01", {"raw": np.array([1000., 2000., 3000.]),
                                           "corrected": np.array([1050., 2050., 3050.]), "existing": None})
        self.assertTrue((np.diff(q) > 0).all())
        self.assertAlmostEqual(q[2]-q[1], 1000.)
        self.assertAlmostEqual(sum(used.values()), 1.)

    def test_future_selected_existing_model_is_rejected(self):
        f = self.data()
        f.loc[0, "existing_selected_until"] = f.issue_date.iloc[0]
        with self.assertRaises(ValueError): OOFBlender().fit(f)

    def test_in_sample_postprocessor_is_rejected(self):
        f = self.data()
        f.loc[0, "post_fitted_until"] = f.issue_date.iloc[0]
        with self.assertRaises(ValueError): OOFBlender().fit(f)


if __name__ == "__main__": unittest.main()
