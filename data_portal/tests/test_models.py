"""Model scoring and version-ledger tests.

Run from data_portal: python -m unittest discover -s tests -v
"""
import csv
import json
import math
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_models as models

HEADER = ("basin_id", "issue_date", "target_date", "lead_day", "season", "observed_cumecs", "Model", "q0.05", "q0.95")
START = date(2022, 1, 1)


def observed(day):
    return round(1000 + 400 * math.sin(day.toordinal() / 9), 1)


def prediction_rows(error, days=40, leads=(1, 2, 3), basin="marala", column_value=None):
    rows = []
    for offset in range(days):
        issue = START + timedelta(days=offset)
        for lead in leads:
            target = issue + timedelta(days=lead)
            truth = observed(target)
            value = round(truth + error(offset, lead), 1)
            rows.append([basin, issue.isoformat(), target.isoformat(), lead, "Oct-Mar", truth, value, value - 150, value + 150])
    return rows


def write_csv(path, rows, header=HEADER):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def bump_mtime(path):
    stamp = path.stat().st_mtime + 5
    os.utime(path, (stamp, stamp))


class MetricTests(unittest.TestCase):
    def test_single_pass_scores_match_textbook_formulas(self):
        obs = [120.0, 340.5, 910.2, 455.0, 610.7, 220.1]
        sim = [150.0, 300.0, 980.4, 400.2, 650.0, 260.9]
        acc = models.Acc()
        for o, s in zip(obs, sim):
            acc.add(o, s)
        result = acc.result()
        n = len(obs)
        mean_o, mean_s = sum(obs) / n, sum(sim) / n
        sse = sum((s - o) ** 2 for o, s in zip(obs, sim))
        sst = sum((o - mean_o) ** 2 for o in obs)
        sd_o = math.sqrt(sst / n)
        sd_s = math.sqrt(sum((s - mean_s) ** 2 for s in sim) / n)
        r = sum((o - mean_o) * (s - mean_s) for o, s in zip(obs, sim)) / n / (sd_o * sd_s)
        kge = 1 - math.sqrt((r - 1) ** 2 + (sd_s / sd_o - 1) ** 2 + (mean_s / mean_o - 1) ** 2)
        self.assertAlmostEqual(result["rmse"], math.sqrt(sse / n), places=3)
        self.assertAlmostEqual(result["mae"], sum(abs(s - o) for o, s in zip(obs, sim)) / n, places=3)
        self.assertAlmostEqual(result["nse"], 1 - sse / sst, places=5)
        self.assertAlmostEqual(result["kge"], kge, places=5)
        self.assertAlmostEqual(result["pbias"], 100 * (sum(sim) - sum(obs)) / sum(obs), places=3)

    def test_skill_compares_only_cells_both_models_predict(self):
        def view(rows):
            extractor = models.Extractor("x", {"point": "Model"}, {}, None, "daily")
            for row in rows:
                extractor.cells[date.fromisoformat(row[1]).toordinal() * models.LEAD_FACTOR + row[3]] = (row[6], None, None, row[5], None)
            return models.View(extractor.compact()[0])
        model = view(prediction_rows(lambda offset, lead: 50))
        baseline = view(prediction_rows(lambda offset, lead: 100, days=20))
        comparison = models.compare_views(model, baseline)
        self.assertEqual(comparison["pooled"]["n"], 20 * 3)
        self.assertAlmostEqual(comparison["pooled"]["skill"], 0.5, places=3)
        self.assertEqual(comparison["leads_better"], 3)


class SharedSampleTests(unittest.TestCase):
    @staticmethod
    def view(days, error):
        extractor = models.Extractor("x", {"point": "Model"}, {}, None, "daily")
        for row in prediction_rows(lambda offset, lead: error, days=days):
            extractor.cells[date.fromisoformat(row[1]).toordinal() * models.LEAD_FACTOR + row[3]] = (row[6], None, None, row[5], None)
        return models.View(extractor.compact()[0])

    def test_reference_rows_never_shrink_the_shared_sample(self):
        members = {"model": self.view(40, 30), "baseline": self.view(40, 90), "reference": self.view(25, 10)}
        table = models.same_sample(members, "baseline", roles={"model": "model", "baseline": "baseline", "reference": "reference"})
        self.assertEqual(table["cells"], 40 * 3)
        self.assertEqual([item["model"] for item in table["excluded"]], ["reference"])
        skill = next(row for row in table["rows"] if row["model"] == "model")["pooled"]["skill"]
        self.assertAlmostEqual(skill, 1 - 30 / 90, places=3)

    def test_member_covering_little_of_the_sample_is_scored_separately(self):
        members = {"model": self.view(40, 30), "baseline": self.view(40, 90), "partial": self.view(10, 5)}
        table = models.same_sample(members, "baseline", roles={"model": "model", "baseline": "baseline", "partial": "model"})
        self.assertEqual(table["cells"], 40 * 3)
        self.assertEqual(table["excluded"][0]["model"], "partial")


class BuildTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.workspace = self.root / "workspace"
        self.dist = self.root / "dist"
        self.reports = self.workspace / "models/model_10 days/good_lstm/reports"
        write_csv(self.reports / "initial/predictions.csv", prediction_rows(lambda offset, lead: 40 * lead))
        self.fixed = self.workspace / "models/climatology/predictions.csv"
        write_csv(self.fixed, prediction_rows(lambda offset, lead: 160))
        self.catalog = self.root / "catalog.json"
        self.catalog.write_text(json.dumps({
            "schema_version": 1,
            "ranges": {"short": {"label": "Short range"}},
            "cohorts": [{"id": "c10", "range": "short", "station": "marala", "title": "10-day", "default_baseline": "clim",
                         "baselines": ["clim"], "headline_lead": 3, "flood_threshold": {"value": 1300, "label": "test"}}],
            "models": [
                {"id": "lstm", "name": "Good LSTM", "cohorts": ["c10"], "role": "model",
                 "source": {"runs": "models/model_10 days/good_lstm/reports", "file": "predictions.csv"},
                 "columns": {"point": "Model", "low": "q0.05", "high": "q0.95"}, "interval": [0.05, 0.95]},
                {"id": "clim", "name": "Climatology", "cohorts": ["c10"], "role": "baseline",
                 "source": {"file": "models/climatology/predictions.csv"}, "columns": {"point": "Model"}}],
            "discovery": [{"range": "short", "root": "models", "default_station": "marala",
                           "files": ["predictions.csv"], "horizon_pattern": "model_(\\d+)[ _]days", "cohort_by_horizon": {"10": "c10"}}],
        }), encoding="utf-8")
        self.stations = {"marala": "Chenab · Marala", "khanki": "Chenab · Khanki"}

    def tearDown(self):
        self.temp.cleanup()

    def build(self, **extra):
        return models.build_models(dist=self.dist, catalog_path=self.catalog, workspace=self.workspace,
                                   stations=self.stations, log=lambda message: None, **extra)

    def output(self):
        data = json.loads((self.dist / "data/models.json").read_text(encoding="utf-8"))
        return data, {model["id"]: model for model in data["models"]}

    def test_scores_skill_shared_sample_and_reuse(self):
        summary = self.build()
        self.assertFalse(summary["reused"])
        data, by_id = self.output()
        lstm = by_id["lstm"]
        self.assertEqual(lstm["current"], 1)
        self.assertEqual(lstm["scores"]["pooled"]["n"], 40 * 3)
        self.assertAlmostEqual(lstm["scores"]["skill"]["clim"]["pooled"]["skill"], 1 - math.sqrt((40 ** 2 + 80 ** 2 + 120 ** 2) / 3) / 160, places=3)
        self.assertEqual(lstm["scores"]["pooled"]["cov"], 1.0)
        cohort = data["cohorts"][0]
        self.assertEqual(cohort["same_sample"]["cells"], 120)
        self.assertTrue((self.dist / lstm["versions"][0]["detail"]).is_file())
        self.assertTrue(self.build()["reused"])

    def test_new_run_folder_becomes_the_next_version(self):
        self.build()
        newer = self.reports / "2026-12-01/predictions.csv"
        write_csv(newer, prediction_rows(lambda offset, lead: 10 * lead))
        summary = self.build()
        self.assertEqual([(change["model"], change["version"]) for change in summary["changes"]], [("lstm", 2)])
        _, by_id = self.output()
        lstm = by_id["lstm"]
        self.assertEqual(lstm["current"], 2)
        self.assertEqual([version["run"] for version in lstm["versions"]], ["initial", "2026-12-01"])
        delta = lstm["versions"][1]["delta_vs_previous"]
        self.assertEqual(delta["verdict"], "improved")
        self.assertLess(delta["rmse_change_pct"], -50)
        self.assertGreater(lstm["versions"][1]["summary"]["skill"], lstm["versions"][0]["summary"]["skill"])

    def test_overwritten_predictions_keep_the_old_version(self):
        self.build()
        _, before = self.output()
        old_detail = self.dist / before["clim"]["versions"][0]["detail"]
        write_csv(self.fixed, prediction_rows(lambda offset, lead: 300))
        bump_mtime(self.fixed)
        self.build()
        _, after = self.output()
        clim = after["clim"]
        self.assertEqual(len(clim["versions"]), 2)
        self.assertEqual(clim["versions"][1]["delta_vs_previous"]["verdict"], "regressed")
        self.assertTrue(old_detail.is_file(), "the replaced version's predictions must stay plottable")
        ledger = json.loads((self.dist / "data/model_versions.json").read_text(encoding="utf-8"))
        self.assertEqual(len(ledger["models"]["clim"]["versions"]), 2)
        self.assertLess(after["lstm"]["scores"]["skill"]["clim"]["pooled"]["rmse_base"], 301)

    def test_rebuilding_unchanged_content_does_not_add_a_version(self):
        self.build()
        bump_mtime(self.fixed)
        summary = self.build()
        self.assertFalse(summary["reused"])
        self.assertEqual(summary["changes"], [])
        _, by_id = self.output()
        self.assertEqual(len(by_id["clim"]["versions"]), 1)

    def test_new_model_folder_is_discovered(self):
        folder = self.workspace / "models/model_10 days/new_model"
        (folder).mkdir(parents=True)
        (folder / "README.md").write_text("# Brand new model\n\nText.\n", encoding="utf-8")
        write_csv(folder / "reports/initial/predictions.csv", prediction_rows(lambda offset, lead: 25))
        self.build()
        _, by_id = self.output()
        found = [model for model in by_id.values() if model["origin"] == "discovered"]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["name"], "Brand new model")
        self.assertEqual(found[0]["cohorts"], ["c10"])
        self.assertIsNotNone(found[0]["scores"]["skill"]["clim"]["pooled"]["skill"])

    def test_discovered_model_for_another_station_gets_its_own_group(self):
        write_csv(self.workspace / "models/model_10 days/khanki_lstm/reports/initial/predictions.csv",
                  prediction_rows(lambda offset, lead: 25, basin="khanki"))
        self.build()
        data, by_id = self.output()
        found = next(model for model in by_id.values() if model["origin"] == "discovered")
        self.assertEqual(found["station"], "khanki")
        self.assertTrue(found["cohorts"][0].startswith("auto.khanki"))
        self.assertIn("khanki", {station["id"] for station in data["stations"] if station["models"]})

    def test_unreadable_model_is_reported_without_stopping_the_others(self):
        catalog = json.loads(self.catalog.read_text(encoding="utf-8"))
        catalog["models"].append({"id": "broken", "name": "Broken", "cohorts": ["c10"], "role": "model",
                                  "source": {"file": "models/climatology/predictions.csv"}, "columns": {"point": "missing_column"}})
        self.catalog.write_text(json.dumps(catalog), encoding="utf-8")
        self.build()
        data, by_id = self.output()
        self.assertEqual(by_id["broken"]["status"], "error")
        self.assertIn("missing_column", by_id["broken"]["message"])
        self.assertEqual(by_id["lstm"]["status"], "ok")
        self.assertTrue(any("broken" in warning for warning in data["warnings"]))

    def test_watch_fingerprint_sees_a_new_run_folder(self):
        before = models.watch_fingerprint(self.catalog, self.workspace)
        write_csv(self.reports / "2026-12-01/predictions.csv", prediction_rows(lambda offset, lead: 5))
        self.assertNotEqual(before, models.watch_fingerprint(self.catalog, self.workspace))


if __name__ == "__main__":
    unittest.main()
