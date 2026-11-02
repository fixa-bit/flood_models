"""Synthetic checks only; these do not measure real Marala model accuracy."""
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

SCRIPT = Path(__file__).resolve().parents[1] / 'nearby_regression.py'
spec = importlib.util.spec_from_file_location('nearby_regression', SCRIPT)
model = importlib.util.module_from_spec(spec)
spec.loader.exec_module(model)


class RegressionTests(unittest.TestCase):
    def run_case(self, lag=1, unrelated=False, missing_predictor=False):
        rng = np.random.default_rng(8)
        dates = pd.date_range('2015-01-01', periods=365 * 8)
        nearby = rng.lognormal(4, 0.6, len(dates))
        shifted = np.roll(nearby, lag)
        marala = (rng.lognormal(4, 0.6, len(dates)) if unrelated
                  else 2 * shifted ** 1.1)
        gaps = np.arange(70, len(dates), 180)
        marala[gaps] = np.nan
        # An observed zero must survive even though it cannot enter log fitting.
        marala[50] = 0
        if missing_predictor:
            nearby[gaps - lag] = np.nan
        with tempfile.TemporaryDirectory() as directory:
            directory = Path(directory)
            pd.DataFrame({'date': dates, 'q_cumecs': marala}).to_csv(directory / 'marala.csv', index=False)
            pd.DataFrame({'date': dates, 'q_cumecs': nearby}).to_csv(directory / 'nearby.csv', index=False)
            run = subprocess.run([sys.executable, str(SCRIPT)], cwd=directory,
                                 capture_output=True, text=True, check=True)
            output = pd.read_csv(directory / 'marala_discharge_regression.csv')
        observed = np.isfinite(marala)
        np.testing.assert_allclose(output.loc[observed, 'q_cumecs'], marala[observed])
        self.assertTrue(output.loc[observed, 'is_observed'].all())
        self.assertTrue(output.loc[observed, 'q_source'].eq('observed').all())
        self.assertFalse(output.loc[gaps, 'is_observed'].any())
        if unrelated or missing_predictor:
            self.assertTrue(output.loc[gaps, 'q_cumecs'].isna().all())
        else:
            self.assertIn(f'Best lag: {lag} days', run.stdout)
            np.testing.assert_allclose(output.loc[gaps, 'q_cumecs'],
                                       2 * shifted[gaps] ** 1.1, rtol=1e-10)
            self.assertTrue(output.loc[gaps, 'q_source'].eq('nearby_gauge').all())
        if unrelated:
            self.assertEqual(run.stdout.count('not filling.'), 3)

    def test_lags_and_observed_preservation(self):
        for lag in (0, 1, 2):
            with self.subTest(lag=lag):
                self.run_case(lag=lag)

    def test_unrelated_gauge_rejected(self):
        self.run_case(unrelated=True)

    def test_missing_predictor_not_filled(self):
        self.run_case(missing_predictor=True)

    def test_metric_definitions(self):
        np.testing.assert_allclose(model.scores([1, 2, 3], [1, 2, 3], 2.5), [1, 1, 0, 0])
        nse, kge, bias, peak = model.scores([1, 2, 3], [2, 4, 6], 2.5)
        self.assertAlmostEqual(nse, -6)
        self.assertAlmostEqual(kge, 1 - np.sqrt(2))
        self.assertAlmostEqual(bias, 100)
        self.assertAlmostEqual(peak, 100)
        self.assertTrue(np.isnan(model.scores([1, 1], [1, 1], 2)[0]))
        self.assertTrue(np.isnan(model.scores([1, 2], [1, 2], 3)[3]))

    def test_invalid_input_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.csv'
            for values in ('2020-01-01,1\n2020-01-01,2', '2020-01-01,-1', '2020-01-01,inf'):
                path.write_text('date,q_cumecs\n' + values + '\n')
                with self.assertRaises(ValueError):
                    model.load(path)


if __name__ == '__main__':
    unittest.main(verbosity=2)
