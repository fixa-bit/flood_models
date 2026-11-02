"""Offline checks for topology, calendars, chunk resumption and merged-data QA."""
import contextlib
import csv
import importlib.util
import io
import json
import math
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location("precip", Path(__file__).with_name("extract_precipitation.py"))
precip = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(precip)


class PrecipitationTests(unittest.TestCase):
    def test_existing_project_catchment(self):
        feature, digest = precip.read_catchment(precip.DEFAULT_CATCHMENT)
        self.assertEqual(feature["geometry"]["type"], "Polygon")
        self.assertEqual(feature["properties"]["station"], "Marala")
        self.assertAlmostEqual(feature["properties"]["area_km2_geodesic"], 28780.646, places=3)
        self.assertEqual(len(digest), 64)

    def test_upstream_network_not_downstream_or_disconnected(self):
        self.assertEqual(precip.upstream_ids([(1, 9), (2, 1), (3, 1), (4, 2), (8, 9), (9, 0)], 1), [1, 2, 3, 4])
        self.assertEqual(precip.upstream_ids([(1, 2), (2, 1)], 1), [1, 2])

    def test_calendar_and_nonfinite(self):
        dates = list(precip.days())
        self.assertEqual(len(dates), 16437)
        self.assertIn(precip.date(2000, 2, 29), dates)
        self.assertEqual(str(dates[-1]), "2024-12-31")
        self.assertTrue(math.isnan(precip.number("NaN")))
        with self.assertRaises(ValueError):
            precip.number("inf")

    def write_fixture(self, root):
        for key, (_, _, available, _) in precip.PRODUCTS.items():
            folder = root / "chunks" / key
            folder.mkdir(parents=True)
            with (folder / "fixture.csv").open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=precip.FIELDS)
                writer.writeheader()
                for day in precip.days():
                    if day.isoformat() >= available:
                        writer.writerow(dict(date=day.isoformat(), value_mm=1,
                                             raw_min_mm=0, negative_area_fraction=0,
                                             coverage_fraction=1, n_images=48 if key == "imerg_mm" else 1))

    def test_merge_full_calendar_units_and_partial_years(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_fixture(root)
            with contextlib.redirect_stdout(io.StringIO()):
                precip.merge(SimpleNamespace(output=root, min_coverage=.999))
            with (root / "marala_daily_precipitation_1980_2024.csv").open() as stream:
                rows = list(csv.DictReader(stream))
            self.assertEqual(len(rows), 16437)
            self.assertEqual(list(rows[0]), ["date", *precip.PRODUCTS])
            self.assertEqual(rows[0]["chirps_mm"], "NaN")
            self.assertEqual(rows[-1]["imerg_mm"], "1.0")
            with (root / "annual_totals.csv").open() as stream:
                totals = {(r["product"], r["year"]): r for r in csv.DictReader(stream)}
            self.assertEqual(float(totals["era5land_mm", "1980"]["annual_total_mm"]), 366)
            self.assertEqual(totals["imerg_mm", "2000"]["annual_total_mm"], "NaN")
            self.assertEqual(float(totals["imerg_mm", "2000"]["observed_partial_total_mm"]), 214)
            self.assertTrue(json.loads((root / "quality_report.json").read_text())["qa_passed"])

    def test_missing_negative_and_partial_days_fail_qa(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_fixture(root)
            path = root / "chunks" / "imerg_mm" / "fixture.csv"
            with path.open() as stream:
                rows = list(csv.DictReader(stream))
            rows[0]["n_images"] = 47
            rows[1]["value_mm"] = -2
            rows[2]["coverage_fraction"] = .8
            rows.pop(3)
            with path.open("w", newline="") as stream:
                writer = csv.DictWriter(stream, fieldnames=precip.FIELDS)
                writer.writeheader()
                writer.writerows(rows)
            with contextlib.redirect_stdout(io.StringIO()), self.assertRaises(ValueError):
                precip.merge(SimpleNamespace(output=root, min_coverage=.999))
            qa = json.loads((root / "quality_report.json").read_text())
            self.assertFalse(qa["qa_passed"])
            self.assertEqual(len(qa["products"]["imerg_mm"]["unexpected_missing_days"]), 4)
            self.assertEqual(len(qa["products"]["imerg_mm"]["rejected_negative_days"]), 1)

    def test_duplicate_chunks_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            self.write_fixture(root)
            folder = root / "chunks" / "era5land_mm"
            (folder / "duplicate.csv").write_bytes((folder / "fixture.csv").read_bytes())
            with self.assertRaisesRegex(ValueError, "Overlapping chunks"):
                precip.merge(SimpleNamespace(output=root, min_coverage=.999))

    def test_resume_split_chunk_does_not_download_overlapping_parent(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            folder = root / "chunks" / "imerg_mm"
            folder.mkdir(parents=True)
            (folder / "2000-06-01_2000-06-16.csv").touch()
            (folder / "2000-06-16_2000-07-01.csv").touch()
            with patch.object(precip, "daily_features", side_effect=AssertionError("Unexpected download")):
                precip.download_chunk("imerg_mm", precip.date(2000, 6, 1), precip.date(2000, 7, 1),
                                      None, None, SimpleNamespace(output=root))


if __name__ == "__main__":
    unittest.main()
