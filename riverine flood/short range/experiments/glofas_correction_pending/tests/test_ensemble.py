import unittest
import numpy as np
import pandas as pd
from glofas_correction.ensemble import EnsemblePostprocessor
from test_residual import fixture


class EnsembleTests(unittest.TestCase):
    def data(self):
        f = fixture()
        f["issue_date"] = f.valid_date-pd.Timedelta(days=1)
        f["base_fitted_until"] = pd.Timestamp("2017-12-30")
        f["corrected_point"] = f.raw_p50+20
        f["raw_members"] = [np.array([q-10, q, q+10]) for q in f.raw_p50]
        return f

    def model(self):
        return EnsemblePostprocessor({"n_estimators": 15, "min_samples_leaf": 5, "max_depth": 4, "max_samples_leaf": None}, minimum=20)

    def test_qrf_intervals_order_probabilities_and_unseen_peaks(self):
        f = self.data()
        model = self.model().fit(f)
        test = f.iloc[:2].copy()
        test["corrected_point"] = [1000., 2000.]
        q = model.quantiles(test)
        self.assertTrue((np.diff(q, axis=-1) >= 0).all())
        self.assertGreater(q[1, 1], f.observed.max())
        np.testing.assert_allclose(model.exceedance(test, 1500), [0., 1.])

    def test_in_sample_rows_are_rejected(self):
        f = self.data()
        f.loc[0, "base_fitted_until"] = f.issue_date.iloc[0]
        with self.assertRaises(ValueError): self.model().fit(f)


if __name__ == "__main__": unittest.main()
