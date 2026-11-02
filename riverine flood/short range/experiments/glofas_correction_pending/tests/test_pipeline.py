"""SYNTHETIC execution/lineage tests, never evidence of actual GloFAS skill."""
import copy
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import joblib
import numpy as np
import pandas as pd
from glofas_correction.common import load_config, save_json
from glofas_correction.backtest import train
from test_data import example


class PipelineTests(unittest.TestCase):
    def test_nested_oof_training_artifacts_and_daily_weekly_evaluation(self):
        cfg = load_config(Path(__file__).parents[1]/"config.yaml")
        with tempfile.TemporaryDirectory(prefix="glofas_SYNTHETIC_TEST_") as directory:
            cfg["_root"] = Path(directory)
            cfg["experiment"].update(first_training_year=2016, first_oof_year=2017, test_years=[2019],
                                     min_samples_per_horizon=5, min_qrf_samples=5, threads=1)
            cfg["download"]["expected_reforecast_members"] = 3
            cfg["bias"].update(min_pairs=5, n_quantiles=11)
            cfg["residual"].update(n_estimators=5, min_child_samples=2, num_leaves=3)
            cfg["postprocessing"].update(n_estimators=5, min_samples_leaf=2, max_depth=3)
            cfg["blending"]["min_samples"] = 5
            save_json(Path(directory)/cfg["download"]["grid_report"], {"passed": True, "selected": {"latitude": 32.675, "longitude": 74.475}})
            archive, obs = example(cfg, years=(2016,2017,2018,2019), step=5)
            archive_path = Path(directory)/cfg["download"]["reforecast_file"]
            archive_path.parent.mkdir(parents=True, exist_ok=True)
            archive.to_csv(archive_path, index=False)
            source = Path(directory)/"SYNTHETIC_observations.csv"
            obs.to_csv(source)
            project = {"_root": directory, "data": {"daily_file": source.name}}
            with patch("glofas_correction.backtest.observations", return_value=(obs,project)), \
                 patch("glofas_correction.backtest.existing_oof", return_value=(pd.DataFrame(),{"status":"synthetic_test_no_existing"})), \
                 patch("glofas_correction.backtest.verify_source_archive", return_value={"TEST_FIXTURE":True}):
                root = train(cfg)
            self.assertTrue((root/"complete.json").exists())
            table = pd.read_csv(root/"rolling_predictions.csv.gz")
            self.assertEqual(set(table.horizon), {f"day_{i:02d}" for i in range(1,11)}|{"week_2","week_3","week_4"})
            self.assertTrue((table.p10 <= table.p50+1e-8).all())
            self.assertTrue((table.p50 <= table.p90+1e-8).all())
            self.assertTrue((pd.to_datetime(table.base_fitted_until) < pd.to_datetime(table.issue_date)).all())
            self.assertTrue((pd.to_datetime(table.post_fitted_until) < pd.to_datetime(table.issue_date)).all())
            results = pd.read_csv(root/"reports/beyond_day10_climatology_test.csv")
            self.assertIn("week_4", set(results.horizon))
            self.assertIn("probabilistic_climatology", set(results.baseline))
            models = joblib.load(root/"final/models.joblib")
            self.assertEqual(len(models["residual"].models), 13)
            audit = pd.read_csv(root/"folds/2019/oof_audit.csv")
            self.assertTrue((pd.to_datetime(audit.base_fitted_until) < pd.to_datetime(audit.issue_date)).all())


if __name__ == "__main__": unittest.main()
