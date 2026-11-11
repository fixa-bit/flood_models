"""Marala catchment-mean daily precipitation and temperature from NEX-GDDP-CMIP6.

Source: NASA/GDDP-CMIP6 on Google Earth Engine (0.25 deg, daily, BCSD-downscaled
CMIP6; Thrasher et al. 2022). Catchment = the short-range processed Marala
catchment; Reducer.mean() at the native 27 830 m scale (fractional boundary
weights). Bias correction to ERA5-Land is NOT done here; it is done at run time
in the projection step so the raw GCM series stays untouched.

Conversions: pr kg m-2 s-1 * 86400 -> mm/day; tas K - 273.15 -> deg C.
Where a model has several dataset versions for a day, the highest version is kept.

Output: one CSV per model and experiment: <model>_<experiment>.csv (date, pr_mm, tas_c, version).

    ../../.venv/Scripts/python.exe extract_nex_gddp_cmip6.py --project <ee-project>
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

HERE = Path(__file__).resolve().parent
CATCHMENT = HERE.parents[2] / "short range/dataset/chenab_marala/processed/marala/catchment/marala_upstream_catchment.geojson"
COLLECTION = "NASA/GDDP-CMIP6"
MODELS = ["ACCESS-CM2", "CNRM-CM6-1", "EC-Earth3", "GFDL-ESM4", "MIROC6", "MPI-ESM1-2-HR", "MRI-ESM2-0", "NorESM2-MM"]
EXPERIMENTS = {"historical": (1985, 2014), "ssp245": (2024, 2040), "ssp585": (2024, 2040)}
ee = None


def year_rows(model, scenario, year, polygon):
    col = (ee.ImageCollection(COLLECTION).filter(ee.Filter.eq("model", model)).filter(ee.Filter.eq("scenario", scenario))
           .filterDate(f"{year}-01-01", f"{year + 1}-01-01").select(["pr", "tas"]))

    def reduce(im):
        im = ee.Image(im)
        m = im.reduceRegion(ee.Reducer.mean(), polygon, scale=27830, maxPixels=100_000_000, tileScale=4)
        return ee.Feature(None, m).set({"date": im.date().format("YYYY-MM-dd", "UTC"), "version": im.get("version")})

    fc = ee.FeatureCollection(col.toList(2000).map(reduce))
    for attempt in range(4):
        try:
            url = fc.getDownloadURL(filetype="CSV", selectors=["date", "pr", "tas", "version"])
            with urlopen(url, timeout=300) as r:
                rows = list(csv.DictReader(io.StringIO(r.read().decode("utf-8-sig"))))
            break
        except Exception as error:
            print(f"{model} {scenario} {year} attempt {attempt + 1}: {str(error)[:150]}", flush=True)
            time.sleep(5 * (attempt + 1))
    else:
        raise RuntimeError(f"failed {model} {scenario} {year}")
    best = {}
    for r in rows:
        if r["pr"] == "" or r["tas"] == "":
            continue
        if r["date"] not in best or str(r["version"]) > str(best[r["date"]]["version"]):
            best[r["date"]] = r
    return [{"date": d, "pr_mm": float(r["pr"]) * 86400.0, "tas_c": float(r["tas"]) - 273.15, "version": r["version"]}
            for d, r in sorted(best.items())]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--project", required=True)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    global ee
    import ee as _ee
    ee = _ee
    ee.Initialize(project=args.project)
    polygon = ee.FeatureCollection(json.loads(CATCHMENT.read_text(encoding="utf-8"))).geometry()
    receipt_path = HERE / "source_receipt.json"
    receipt = json.loads(receipt_path.read_text()) if receipt_path.exists() else {"files": {}}
    for model in MODELS:
        for exp, (y0, y1) in EXPERIMENTS.items():
            out = HERE / f"{model}_{exp}.csv"
            if out.exists() and out.name in receipt["files"]:
                continue
            with ThreadPoolExecutor(args.workers) as pool:
                years = list(pool.map(lambda y: year_rows(model, exp, y, polygon), range(y0, y1 + 1)))
            rows = [r for y in years for r in y]
            with out.open("w", newline="", encoding="utf-8") as s:
                w = csv.DictWriter(s, fieldnames=["date", "pr_mm", "tas_c", "version"])
                w.writeheader()
                w.writerows(rows)
            receipt["files"][out.name] = {"model": model, "experiment": exp, "years": [y0, y1], "days": len(rows),
                                          "versions": sorted({r["version"] for r in rows}),
                                          "sha256": hashlib.sha256(out.read_bytes()).hexdigest()}
            receipt.update({"collection": COLLECTION, "catchment": "short range/dataset/chenab_marala/processed/marala/catchment/marala_upstream_catchment.geojson",
                            "catchment_sha256": hashlib.sha256(CATCHMENT.read_bytes()).hexdigest(),
                            "reducer": "Reducer.mean() at 27830 m", "conversions": {"pr_mm": "kg m-2 s-1 * 86400", "tas_c": "K - 273.15"},
                            "retrieved_at_utc": datetime.now(timezone.utc).isoformat()})
            receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
            print(f"saved {out.name}: {len(rows)} days", flush=True)


if __name__ == "__main__":
    main()
