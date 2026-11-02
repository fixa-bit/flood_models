import unittest
import numpy as np
import pandas as pd
from glofas_correction.residual import DirectResidualModel


def fixture(n=100):
    x = np.linspace(50, 300, n)
    return pd.DataFrame({"horizon": "day_01", "valid_date": pd.date_range("2018-01-01", periods=n),
        "raw_p50": x, "raw_mean": x, "qm_p50": x+20, "q_asof": x+15, "q_age_days": 0.,
        "previous_raw_residual": 20., "doy_sin": 0., "doy_cos": 1., "lead_start": 1, "lead_end": 1,
        "observed": x+20})


class ResidualTests(unittest.TestCase):
    def test_learns_additive_error_without_capping_unseen_peaks(self):
        f = fixture()
        options = {"n_estimators": 15, "learning_rate": .1, "num_leaves": 3, "min_child_samples": 10, "reg_lambda": 2.}
        model = DirectResidualModel(options, minimum=40).fit(f)
        np.testing.assert_allclose(model.predict(f), f.raw_p50+20, atol=1e-5)
        tail = f.iloc[:2].copy()
        tail["raw_p50"] = [1000., 2000.]
        prediction = model.predict(tail).to_numpy()
        self.assertAlmostEqual(prediction[1]-prediction[0], 1000., places=3)
        self.assertGreater(prediction[-1], f.observed.max())

    def test_does_not_train_on_nan_targets_or_other_horizons(self):
        f = fixture()
        f.loc[:10, "observed"] = np.nan
        options = {"n_estimators": 5, "learning_rate": .1, "num_leaves": 3, "min_child_samples": 10, "reg_lambda": 2.}
        model = DirectResidualModel(options).fit(f)
        other = f.iloc[:1].copy()
        other["horizon"] = "week_4"
        self.assertTrue(model.predict(other).isna().all())


if __name__ == "__main__": unittest.main()
