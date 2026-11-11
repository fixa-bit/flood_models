"""Download GloFAS historical (reanalysis) river discharge at Marala and extract the station cell.

SIMULATED DATA: LISFLOOD model output forced by ERA5. It is stored under
raw/marala/discharge/simulated/ and processed/marala/discharge/simulated/, apart from
observed discharge, and must never be evaluated as ground truth.

Requires ecmwf-datastores-client, xarray, cfgrib (eccodes), pandas and numpy, an EWDS
account key in ~/.cdsapirc (url: https://ewds.climate.copernicus.eu/api) and the accepted
CEMS-FLOODS datasets licence.

    python -I collect_marala_glofas_historical.py cell --uparea <upstream-area.nc> --version version_5_0 --source-url <url>
    python -I collect_marala_glofas_historical.py download
    python -I collect_marala_glofas_historical.py extract
"""

import argparse
import hashlib
import json
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

MODEL_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = MODEL_DIR / "raw" / "marala" / "discharge" / "simulated" / "glofas_historical"
PROCESSED_DIR = MODEL_DIR / "processed" / "marala" / "discharge" / "simulated"
OBSERVED_CSV = MODEL_DIR / "processed" / "marala" / "discharge" / "marala_daily_inflow_clean.csv"
SINDH_CSV = MODEL_DIR / "processed" / "marala" / "discharge" / "marala_sindh_rimstation_discharge.csv"
RECEIPT = RAW_DIR / "source_receipt.json"
DATASET = "cems-glofas-historical"
LANDING_PAGE = "https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical"
AREA = [32.80, 74.30, 32.55, 74.65]  # N, W, S, E: station cell plus neighbours
CELL = {"latitude": 32.675, "longitude": 74.475}
OUTLET = {"latitude": 32.67, "longitude": 74.46}  # processed/marala/catchment/marala_outlet.geojson
CATCHMENT_KM2 = 28780.646  # processed/marala/catchment/marala_upstream_catchment.geojson
FIRST_YEAR = {"version_4_0": 1979, "version_5_0": 1980}
LAST_YEAR = 2026
CUSEC_M3_S = 0.028316846592
LOCK = threading.Lock()
CLAIMED: set[str] = set()


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def credentials() -> tuple[str, str]:
    text = (Path.home() / ".cdsapirc").read_text(encoding="utf-8")
    url = re.search(r"^url:\s*(\S+)", text, re.M).group(1)
    key = re.search(r"^key:\s*(\S+)", text, re.M).group(1)
    if "ewds" not in url:
        raise SystemExit(f"~/.cdsapirc points to {url}; GloFAS is served by https://ewds.climate.copernicus.eu/api")
    return url, key


def client():
    from ecmwf.datastores import Client

    url, key = credentials()
    return Client(url=url, key=key, progress=False, sleep_max=60)


def load_receipt() -> dict:
    if RECEIPT.exists():
        return json.loads(RECEIPT.read_text(encoding="utf-8"))
    return {
        "content": "SIMULATED river discharge (model output), not observations",
        "dataset": DATASET,
        "landing_page": LANDING_PAGE,
        "provider": "Copernicus Emergency Management Service (CEMS) / ECMWF / JRC",
        "licence": "CEMS-FLOODS datasets licence (accepted on the user's EWDS account)",
        "model": "LISFLOOD forced with ERA5 (consolidated product)",
        "variable": "average_river_discharge_in_the_last_24_hours (m3 s-1)",
        "area_N_W_S_E": AREA,
        "station_cell": CELL,
        "cell_checks": {},
        "files": {},
    }


def save_receipt(receipt: dict) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    temporary = RECEIPT.with_suffix(".json.part")
    temporary.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    temporary.replace(RECEIPT)


def check_cell(uparea_path: Path, version: str, source_url: str) -> None:
    """Record the upstream-area match of the station cell on this version's river network."""
    import numpy as np
    import xarray as xr

    with xr.open_dataset(uparea_path) as ds:
        name = next(v for v in ds.data_vars if ds[v].ndim == 2)
        grid = ds[name]
        lat_name, lon_name = grid.dims
        lats, lons = ds[lat_name].values, ds[lon_name].values
        rows = np.where((lats > OUTLET["latitude"] - 0.25) & (lats < OUTLET["latitude"] + 0.25))[0]
        cols = np.where((lons > OUTLET["longitude"] - 0.30) & (lons < OUTLET["longitude"] + 0.30))[0]
        table = grid.isel({lat_name: rows, lon_name: cols}).to_dataframe(name="m2").reset_index()
    table["upstream_area_km2"] = table.m2 / 1e6
    table["distance_km"] = np.hypot((table[lat_name] - OUTLET["latitude"]) * 111.0,
                                    (table[lon_name] - OUTLET["longitude"]) * 111.0 * np.cos(np.radians(OUTLET["latitude"])))
    table["relative_area_error"] = table.upstream_area_km2 / CATCHMENT_KM2 - 1
    river = table[table.upstream_area_km2 > 0.5 * CATCHMENT_KM2].sort_values("distance_km").head(6)
    cells = [{"latitude": round(float(r[lat_name]), 4), "longitude": round(float(r[lon_name]), 4),
              "upstream_area_km2": round(float(r.upstream_area_km2), 1), "distance_km": round(float(r.distance_km), 2),
              "relative_area_error": round(float(r.relative_area_error), 4)} for _, r in river.iterrows()]
    chosen = cells[0]
    if (chosen["latitude"], chosen["longitude"]) != (CELL["latitude"], CELL["longitude"]) or abs(chosen["relative_area_error"]) > 0.05:
        raise SystemExit(f"Nearest large-river cell {chosen} differs from the configured station cell {CELL}")
    receipt = load_receipt()
    receipt["cell_checks"][version] = {
        "checked_utc": utc_now(), "upstream_area_source_url": source_url,
        "upstream_area_file": source_url.split("?")[0].rsplit("/", 1)[-1], "upstream_area_sha256": sha256(uparea_path),
        "reference_outlet": OUTLET, "reference_catchment_km2": CATCHMENT_KM2,
        "selected": chosen, "nearest_large_river_cells": cells,
        "note": "Area agreement and proximity do not by themselves prove river-network identity.",
    }
    save_receipt(receipt)
    print(json.dumps(receipt["cell_checks"][version], indent=2))


def build_request(api, version: str, year: int) -> dict | None:
    base = {"system_version": [version], "hydrological_model": ["lisflood"], "product_type": ["consolidated"],
            "timespan": ["time_mean"], "variable": ["average_river_discharge_in_the_last_24_hours"], "year": [str(year)]}
    months = sorted(api.apply_constraints(DATASET, base).get("month", []))
    if not months:
        return None
    days = sorted(api.apply_constraints(DATASET, {**base, "month": months}).get("day", []))
    return {**base, "month": months, "day": days, "data_format": "grib2", "download_format": "unarchived", "area": AREA}


def earlier_job(api, request: dict):
    """An identical request already queued, running or finished on EWDS, e.g. from an interrupted run."""
    recent = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    with LOCK:  # two workers must not claim the same job
        for status in ("running", "accepted", "successful"):
            for job in api.get_jobs(limit=50, sortby="-created", status=status).json["jobs"]:
                if job["jobID"] in CLAIMED or (status == "successful" and (job.get("finished") or "") < recent):
                    continue  # finished results expire, so only reuse ones from the last day
                remote = api.get_remote(job["jobID"])
                if remote.request == request:
                    CLAIMED.add(job["jobID"])
                    return remote
    return None


def fetch_year(version: str, year: int) -> str:
    target = RAW_DIR / version / f"{year}.grib2"
    if target.exists():
        return f"{version} {year}: present"
    api = client()
    request = build_request(api, version, year)
    if request is None:
        return f"{version} {year}: not available"
    part = target.with_suffix(".grib2.part")
    part.parent.mkdir(parents=True, exist_ok=True)
    remote = earlier_job(api, request)
    if remote is not None:
        try:
            remote.download(str(part))
        except Exception:  # finished results expire after a few days; request again
            remote = None
    if remote is None:
        for attempt in range(120):  # EWDS rejects a request when the user's queue for this dataset is full
            remote = api.submit(DATASET, request)
            try:
                remote.download(str(part))
                break
            except Exception as error:
                if "queued requests" not in str(error) and remote.status != "rejected":
                    raise
                time.sleep(90)
        else:
            raise RuntimeError(f"{version} {year}: still rejected after repeated queue-full retries")
    data = part.read_bytes()
    if not (data[:4] == b"GRIB" and data.rstrip()[-4:] == b"7777"):
        raise ValueError(f"{version} {year}: response is not a complete GRIB file")
    part.replace(target)
    with LOCK:
        receipt = load_receipt()
        receipt["files"][f"{version}/{year}.grib2"] = {
            "request": request, "request_id": remote.request_id, "retrieved_utc": utc_now(),
            "bytes": target.stat().st_size, "sha256": sha256(target)}
        save_receipt(receipt)
    return f"{version} {year}: {target.stat().st_size} bytes"


def download(workers: int, versions: list[str], years: list[int] | None) -> None:
    jobs = [(version, year) for version in versions for year in range(FIRST_YEAR[version], LAST_YEAR + 1)
            if years is None or year in years]
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(fetch_year, version, year): (version, year) for version, year in jobs}
        for future in as_completed(futures):
            try:
                print(future.result(), flush=True)
            except Exception as error:  # keep the other years going; rerun to resume
                print(f"{futures[future]}: FAILED {type(error).__name__}: {error}", flush=True)


def read_version(version: str):
    import pandas as pd
    import xarray as xr

    frames = []
    for path in sorted((RAW_DIR / version).glob("*.grib2")):
        with xr.open_dataset(path, engine="cfgrib", backend_kwargs={"indexpath": ""}) as ds:
            name = next(iter(ds.data_vars))
            point = ds[name].sel(latitude=CELL["latitude"], longitude=CELL["longitude"], method="nearest", tolerance=1e-3)
            start = pd.to_datetime(point["time"].values)
            step = pd.to_timedelta(point["step"].values) if "step" in point.coords else pd.Timedelta(0)
            end = pd.to_datetime(point["valid_time"].values)
            frames.append(pd.DataFrame({"period_start_utc": start, "period_end_utc": end, version: point.values.ravel(),
                                        "step_hours": step / pd.Timedelta(hours=1)}))
    table = pd.concat(frames, ignore_index=True)
    if (table.period_end_utc - table.period_start_utc != pd.Timedelta(hours=24)).any():
        raise ValueError(f"{version}: unexpected averaging period; inspect GRIB time/step keys")
    if table.period_end_utc.duplicated().any():
        raise ValueError(f"{version}: duplicate valid times")
    return table.drop(columns="step_hours")


def scores(sim, obs) -> dict:
    import numpy as np

    sim, obs = np.asarray(sim, float), np.asarray(obs, float)
    r = float(np.corrcoef(sim, obs)[0, 1])
    alpha, beta = sim.std() / obs.std(), sim.mean() / obs.mean()
    return {"n_days": int(len(obs)), "nse": round(float(1 - ((sim - obs) ** 2).sum() / ((obs - obs.mean()) ** 2).sum()), 3),
            "kge": round(float(1 - np.sqrt((r - 1) ** 2 + (alpha - 1) ** 2 + (beta - 1) ** 2)), 3),
            "pearson_r": round(r, 3), "bias_pct": round(float(100 * (beta - 1)), 1),
            "variability_ratio": round(float(alpha), 3)}


def extract() -> None:
    import pandas as pd

    versions = [v for v in FIRST_YEAR if any((RAW_DIR / v).glob("*.grib2"))]
    merged = None
    for version in versions:
        table = read_version(version)
        merged = table if merged is None else merged.merge(table, on=["period_start_utc", "period_end_utc"], how="outer")
    merged = merged.sort_values("period_start_utc").reset_index(drop=True)
    merged.insert(0, "date_utc_day_averaged", merged.period_start_utc.dt.strftime("%Y-%m-%d"))
    columns = {v: f"glofas_{v.replace('version_', 'v')}_m3_s" for v in versions}
    out = merged.rename(columns=columns)
    for column in columns.values():
        out[column] = out[column].round(3)
    out["period_start_utc"] = merged.period_start_utc.dt.strftime("%Y-%m-%dT%H:%MZ")
    out["period_end_utc"] = merged.period_end_utc.dt.strftime("%Y-%m-%dT%H:%MZ")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = PROCESSED_DIR / "marala_glofas_historical_daily.csv"
    out.to_csv(csv_path, index=False, lineterminator="\n")

    observed = pd.read_csv(OBSERVED_CSV, parse_dates=["date"])
    observed = observed[observed.eligible_daily_training == 1][["date", "inflow_m3_s"]]
    sindh = pd.read_csv(SINDH_CSV, parse_dates=["date"])
    sindh = sindh[(sindh.value_revised == 0) & ~sindh.inflow_check_vs_wapda_ffd.str.startswith("conflict")
                  & (sindh.date > observed.date.max())][["date", "inflow_m3_s"]]
    observed = pd.concat([observed, sindh], ignore_index=True)
    comparison = {}
    for version, column in columns.items():
        sim = pd.DataFrame({"end_date": merged.period_end_utc.dt.normalize(), "start_date": merged.period_start_utc.dt.normalize(),
                            "sim": merged[version]})
        result = {}
        for label, key in [("24h_mean_ending_00UTC_on_observation_date", "end_date"),
                           ("24h_mean_of_observation_date_UTC", "start_date")]:
            pairs = observed.merge(sim[[key, "sim"]].dropna(), left_on="date", right_on=key)
            monsoon = pairs[pairs.date.dt.month.isin([6, 7, 8, 9])]
            result[label] = {"all_days": scores(pairs.sim, pairs.inflow_m3_s),
                             "jun_sep": scores(monsoon.sim, monsoon.inflow_m3_s)}
        comparison[column] = result
    coverage = {column: {"first": out.loc[out[column].notna(), "date_utc_day_averaged"].min(),
                         "last": out.loc[out[column].notna(), "date_utc_day_averaged"].max(),
                         "days": int(out[column].notna().sum())} for column in columns.values()}
    report = {
        "created_utc": utc_now(), "content": "SIMULATED discharge at the GloFAS station cell; not observations",
        "output": csv_path.name, "station_cell": CELL, "coverage": coverage,
        "time_convention": "Each value is the mean discharge over the 24 h from period_start_utc to period_end_utc "
                           "(00 UTC to 00 UTC = 05:00 to 05:00 Pakistan time). date_utc_day_averaged is the UTC day averaged.",
        "comparison_with_observed_inflow": comparison,
        "comparison_note": "Observed: eligible WAPDA rows of marala_daily_inflow_clean.csv (2016-03 to 2024-12) plus "
                           "unflagged Sindh Irrigation rows after that (2024-12 to 2026-11); reading time ~06:00 PKT. "
                           "Scores describe agreement only; GloFAS is not calibrated at Marala (no GloFAS v5 "
                           "calibration outlet within 170 km).",
    }
    (PROCESSED_DIR / "marala_glofas_historical_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="action", required=True)
    cell = sub.add_parser("cell", help="record the upstream-area check of the station cell")
    cell.add_argument("--uparea", type=Path, required=True)
    cell.add_argument("--version", choices=list(FIRST_YEAR), required=True)
    cell.add_argument("--source-url", required=True, help="where the upstream-area file was downloaded from")
    get = sub.add_parser("download", help="download yearly GRIB2 files (resumable)")
    get.add_argument("--workers", type=int, default=2, help="EWDS queues about two requests per user and dataset")
    get.add_argument("--versions", nargs="+", choices=list(FIRST_YEAR), default=["version_5_0"],
                     help="version_5_0 matched observed Marala flow better (see source_receipt.json version_choice)")
    get.add_argument("--years", nargs="+", type=int, help="default: every available year")
    sub.add_parser("extract", help="write the processed station-cell series and comparison report")
    args = parser.parse_args()
    if args.action == "cell":
        check_cell(args.uparea, args.version, args.source_url)
    elif args.action == "download":
        download(args.workers, args.versions, args.years)
    else:
        extract()


if __name__ == "__main__":
    main()
