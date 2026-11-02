"""Strict issued-ensemble schema, GRIB extraction and causal gauge features."""
import argparse
import json
from pathlib import Path
import numpy as np
import pandas as pd
import xarray as xr
from .common import load_config, resolve, save_json, sha, horizons


REQUIRED = {"issue_date", "valid_date", "lead_day", "member", "q_cumecs", "product_kind", "system_version",
            "cell_latitude", "cell_longitude", "source_sha256"}


def validate_archive(frame, cfg, kind="reforecast"):
    if not REQUIRED.issubset(frame): raise ValueError(f"GloFAS archive missing {sorted(REQUIRED-set(frame))}")
    f = frame.copy()
    for col in ["issue_date", "valid_date"]:
        f[col] = pd.to_datetime(f[col], utc=True).dt.tz_localize(None)
        if f[col].isna().any() or not (f[col] == f[col].dt.normalize()).all(): raise ValueError("Invalid daily forecast date labels")
    if set(f.product_kind) != {kind}: raise ValueError("Training requires true REFORECASTS, never historical/reanalysis discharge")
    if set(f.system_version) != {cfg["download"]["system_version"]}: raise ValueError("Mixed or incompatible GloFAS versions")
    if not np.isfinite(f.q_cumecs).all() or (f.q_cumecs < 0).any(): raise ValueError("Invalid GloFAS discharge")
    if not f.lead_day.between(1, cfg["download"]["max_lead_days"]).all() or not (f.lead_day % 1 == 0).all(): raise ValueError("Invalid lead day")
    if not ((f.valid_date-f.issue_date).dt.days == f.lead_day).all(): raise ValueError("Valid date/lead mismatch")
    if f.member.isna().any() or f.source_sha256.isna().any(): raise ValueError("Missing member/source provenance")
    if not f.source_sha256.astype(str).str.fullmatch("[0-9a-f]{64}").all(): raise ValueError("Invalid source SHA256")
    f["member"] = f.member.astype(str)
    if f.duplicated(["issue_date", "member", "lead_day"]).any(): raise ValueError("Duplicate issue/member/lead, possibly mixed reforecast reference cycles")
    if f[["cell_latitude", "cell_longitude"]].drop_duplicates().shape[0] != 1: raise ValueError("Mixed grid cells")
    grid_path = resolve(cfg, cfg["download"]["grid_report"])
    if not grid_path.exists(): raise ValueError("Upstream-area check must precede archive ingestion")
    grid = json.loads(grid_path.read_text())
    if not grid["passed"]: raise ValueError("Rejected upstream-area cell")
    for col, key in [("cell_latitude", "latitude"), ("cell_longitude", "longitude")]:
        if not np.allclose(f[col], grid["selected"][key], atol=1e-6, rtol=0): raise ValueError("Archive cell differs from area-checked cell")
    if kind == "forecast":
        if "available_at" not in f: raise ValueError("Operational forecasts need publication/availability timestamps")
        times = pd.to_datetime(f.available_at, utc=True)
        cutoff = pd.to_datetime(f.issue_date, utc=True) + pd.Timedelta(hours=cfg["download"]["publication_lag_hours"])
        if times.isna().any() or (times > cutoff).any(): raise ValueError("Forecast unavailable at configured issue cutoff")
    return f.sort_values(["issue_date", "member", "lead_day"]).reset_index(drop=True)


def convert_dataset(ds, cfg, kind, source_hash):
    grid = json.loads(resolve(cfg, cfg["download"]["grid_report"]).read_text())["selected"]
    variable = next((v for v in ["dis24", "discharge", "q_cumecs"] if v in ds), None)
    if variable is None: raise ValueError("GRIB/NetCDF has no supported discharge variable")
    da = ds[variable]
    units = da.attrs.get("units", "").lower().replace(" ", "")
    if units not in ["m**3s**-1", "m3s-1", "m^3s^-1", "m3/s", "m³s⁻¹"]: raise ValueError(f"Unsupported discharge units: {units}")
    for name, value in [("latitude", grid["latitude"]), ("longitude", grid["longitude"])]:
        if name not in da.coords: raise ValueError(f"Missing forecast grid coordinate {name}")
        if name in da.dims: da = da.sel({name: value}, method="nearest")
        if abs(float(da[name])-value) > 1e-6: raise ValueError("Requested cell missing from forecast field")
    f = da.to_dataframe(name="q_cumecs").reset_index()
    if "time" not in f or "step" not in f: raise ValueError("Expected initialization 'time' and lead 'step' coordinates")
    init = pd.to_datetime(f.time, utc=True)
    steps = pd.to_timedelta(f.step)
    lead = steps / pd.Timedelta(days=1)
    use = lead.between(1, cfg["download"]["max_lead_days"])
    f, init, lead = f[use].copy(), init[use], lead[use]
    if not (lead % 1 == 0).all() or not (init == init.dt.normalize()).all(): raise ValueError("Only daily 00UTC initialization is supported")
    f["issue_date"] = init.dt.tz_localize(None)
    f["lead_day"] = lead.astype(int)
    f["valid_date"] = f.issue_date + pd.to_timedelta(f.lead_day, unit="D")
    if "valid_time" in f and not (pd.to_datetime(f.valid_time, utc=True).dt.tz_localize(None) == f.valid_date).all():
        raise ValueError("GRIB validity-end time disagrees with initialization + lead")
    f["member"] = f["number"].astype(int).astype(str) if "number" in f else "0"
    f["product_kind"], f["system_version"], f["source_sha256"] = kind, cfg["download"]["system_version"], source_hash
    f["cell_latitude"], f["cell_longitude"] = grid["latitude"], grid["longitude"]
    if kind == "forecast":
        f["available_at"] = (f.issue_date + pd.Timedelta(hours=cfg["download"]["publication_lag_hours"])).astype(str)
        f["availability_basis"] = "assumed_provider_lag_not_verified_publication_time"
    return f[list(REQUIRED) + (["available_at", "availability_basis"] if kind == "forecast" else [])]


def convert_files(cfg, kind):
    directory = resolve(cfg, cfg["download"]["raw_dir"])
    files = sorted(directory.glob(f"{kind}_*.grib")) + sorted(directory.glob(f"{kind}_*.nc"))
    if not files: raise FileNotFoundError(f"No genuine {kind} files downloaded in {directory}")
    results, sources = [], []
    for path in files:
        checksum = sha(path)
        receipt = path.with_suffix(".receipt.json")
        if not receipt.exists() or json.loads(receipt.read_text())["sha256"] != checksum:
            raise ValueError("Raw GloFAS file must have a matching downloader receipt")
        if path.suffix == ".grib":
            import cfgrib
            datasets = cfgrib.open_datasets(str(path), backend_kwargs={"indexpath": ""})
        else: datasets = [xr.open_dataset(path)]
        for ds in datasets:
            try:
                if any(v in ds for v in ["dis24", "discharge", "q_cumecs"]):
                    result = convert_dataset(ds, cfg, kind, checksum)
                    request = json.loads(receipt.read_text())["request"]
                    expected = int(request["hyear" if kind == "reforecast" else "year"])
                    if not (result.issue_date.dt.year == expected).all():
                        raise ValueError("GRIB reference year is not the requested historical issue year; inspect hindcast-date encoding")
                    results.append(result)
            finally: ds.close()
        sources.append({"path": str(path), "sha256": checksum})
    f = validate_archive(pd.concat(results, ignore_index=True), cfg, kind)
    output = resolve(cfg, cfg["download"][f"{kind}_file"])
    if output.exists(): raise FileExistsError("Processed archive exists; choose a new configured output path")
    output.parent.mkdir(parents=True, exist_ok=True)
    f.to_csv(output, index=False)
    save_json(output.with_suffix(".manifest.json"), {"product_kind": kind, "rows": len(f), "sources": sources, "sha256": sha(output),
              "issues": int(f.issue_date.nunique()), "year_counts": f.groupby(f.issue_date.dt.year).size().to_dict(),
              "alignment": "Observed date = GloFAS validity-END date, last-24h mean vs gauge-reading mismatch unresolved",
              "note": "Missing days/leads/members are not interpolated; downstream complete-window checks apply."})
    return f


def verify_source_archive(cfg, path):
    metadata_path = Path(path).with_suffix(".manifest.json")
    if not metadata_path.exists(): raise ValueError("Processed archive has no verified retrieval manifest")
    metadata = json.loads(metadata_path.read_text())
    if metadata.get("product_kind") != "reforecast" or metadata.get("sha256") != sha(path):
        raise ValueError("Processed reforecast archive/manifest mismatch")
    for source in metadata["sources"]:
        if not Path(source["path"]).exists() or sha(source["path"]) != source["sha256"]:
            raise ValueError("Original GloFAS reforecast source missing or changed")
    return metadata


def causal_gauge_features(obs, issues, cfg, archive):
    issues = pd.DatetimeIndex(issues)
    lag = cfg["experiment"]["observation_lag_days"]
    if lag < 1: raise ValueError("Gauge availability must lag issue by at least one calendar day")
    out = pd.DataFrame(index=issues)
    for delay in [lag, lag+1, lag+2, lag+6]:
        out[f"q_lag_{delay}"] = obs.q_cumecs.reindex(issues-pd.Timedelta(days=delay)).to_numpy()
    finite_q = obs.q_cumecs.dropna()
    left = pd.DataFrame({"cutoff": issues-pd.Timedelta(days=lag)}).sort_values("cutoff")
    right = finite_q.rename("q_asof").rename_axis("q_date").reset_index()
    asof = pd.merge_asof(left, right, left_on="cutoff", right_on="q_date", tolerance=pd.Timedelta(days=7), direction="backward")
    out["q_asof"] = asof.q_asof.to_numpy()
    out["q_age_days"] = (asof.cutoff-asof.q_date).dt.days.to_numpy()
    # Last completed lead-1 reforecast error, never a future verifying observation.
    lead1 = archive[archive.lead_day == 1].groupby("valid_date").q_cumecs.median().sort_index()
    residual = obs.q_cumecs.reindex(lead1.index)-lead1
    right = residual.dropna().rename("previous_raw_residual").rename_axis("residual_date").reset_index()
    if len(right):
        prior = pd.merge_asof(left, right, left_on="cutoff", right_on="residual_date", tolerance=pd.Timedelta(days=14), direction="backward")
        out["previous_raw_residual"] = prior.previous_raw_residual.to_numpy()
    else: out["previous_raw_residual"] = np.nan
    for column in ["rain_chirps_mm", "temperature_c"]:
        if column in obs and cfg["experiment"].get("use_weather_features", False):
            for window in [3, 7, 14]:
                out[f"past_{column}_{window}d"] = obs[column].rolling(window, min_periods=1).mean().reindex(issues-pd.Timedelta(days=lag)).to_numpy()
    return out


def feature_table(archive, obs, cfg, mapper=None):
    rows = []
    issues = sorted(archive.issue_date.unique())
    gauge = causal_gauge_features(obs, issues, cfg, archive)
    for issue, group in archive.groupby("issue_date", sort=True):
        for name, first, last in horizons():
            selected = group[group.lead_day.between(first, last)].copy()
            if selected.empty: continue
            expected_members = sorted(group.member.unique())
            if any(len(selected[selected.member == member]) != last-first+1 for member in expected_members): continue
            if len(expected_members) < cfg["download"]["expected_reforecast_members"]: continue
            dates = pd.date_range(issue+pd.Timedelta(days=first), issue+pd.Timedelta(days=last))
            if not (dates.year == dates.year[0]).all(): continue
            mapped = selected.q_cumecs.to_numpy() if mapper is None else mapper.transform(selected)
            selected["mapped"] = mapped
            raw_members = selected.groupby("member", sort=True).q_cumecs.max().to_numpy()
            qm_members = selected.groupby("member", sort=True).mapped.max().to_numpy()
            # Peak day of the median daily ensemble trajectory; weekly correction
            # changes magnitude while preserving this underlying temporal shape.
            raw_daily = selected.groupby("valid_date").q_cumecs.median()
            mapped_daily = selected.groupby("valid_date").mapped.median()
            labels = obs.q_cumecs.reindex(dates)
            complete = bool(labels.notna().all())
            target = float(labels.max()) if complete else np.nan
            angle = 2*np.pi*dates[len(dates)//2].day_of_year/365.25
            row = {"issue_date": issue, "horizon": name, "lead_start": first, "lead_end": last,
                   "valid_start": dates[0], "valid_date": dates[-1], "year": int(dates.year[0]),
                   "monsoon": bool(np.isin(dates.month, cfg["experiment"]["monsoon_months"]).all()),
                   "observed": target, "observed_peak_date": labels.idxmax() if complete else pd.NaT,
                   "raw_peak_date": raw_daily.idxmax(), "corrected_peak_date": mapped_daily.idxmax(),
                   "raw_members": raw_members, "qm_members": qm_members, "member_count": len(raw_members),
                   "doy_sin": np.sin(angle), "doy_cos": np.cos(angle)}
            for prefix, values in [("raw", raw_members), ("qm", qm_members)]:
                for label, value in [("min", values.min()), ("p10", np.quantile(values, .1)), ("p50", np.quantile(values, .5)),
                                     ("mean", values.mean()), ("p90", np.quantile(values, .9)), ("max", values.max()), ("std", values.std())]:
                    row[f"{prefix}_{label}"] = float(value)
            row.update(gauge.loc[issue].to_dict())
            rows.append(row)
    if not rows: raise ValueError("No complete ensemble/horizon windows")
    return pd.DataFrame(rows)


def feature_columns(frame):
    names = [name for name in frame if name.startswith(("raw_", "qm_", "q_lag_", "past_")) and not name.endswith(("date", "members"))]
    return names + ["q_asof", "q_age_days", "previous_raw_residual", "doy_sin", "doy_cos", "lead_start", "lead_end"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.yaml")))
    parser.add_argument("--kind", choices=["forecast", "reforecast"], required=True)
    args = parser.parse_args()
    convert_files(load_config(args.config), args.kind)
