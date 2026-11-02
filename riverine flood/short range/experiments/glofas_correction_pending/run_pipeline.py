"""Check access, download, ingest, train, and apply the separate GloFAS module."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import joblib
import pandas as pd
from .common import load_config, resolve, observations, save_json, sha
from .download import auxiliary, snapshot_catalogue, plan, credentials, retrieve
from .data import convert_files, validate_archive, feature_table
from .existing_model import existing_oof, attach


def status(cfg):
    credential = credentials(cfg)
    reforecasts = resolve(cfg, cfg["download"]["reforecast_file"])
    raw = resolve(cfg, cfg["download"]["raw_dir"])
    _, audit = existing_oof(cfg)
    root = resolve(cfg, cfg["experiment"]["output_dir"])
    state = {"credential_file_present": credential["file_exists"], "environment_key_present": credential["environment_key_present"],
        "raw_reforecast_files": len(list(raw.glob("reforecast_*.grib"))), "raw_forecast_files": len(list(raw.glob("forecast_*.grib"))),
        "processed_reforecasts_present": reforecasts.exists(), "training_complete": (root / "complete.json").exists(),
        "existing_model": audit, "grid_check_present": resolve(cfg, cfg["download"]["grid_report"]).exists(),
        "api_setup": "https://ewds.climate.copernicus.eu/how-to-api",
        "login": "https://ewds.climate.copernicus.eu/profile"}
    if state["training_complete"]: state["state"] = "trained_and_evaluated"
    elif not credential["file_exists"] and not credential["environment_key_present"]: state["state"] = "awaiting_personal_ewds_login_and_token"
    elif not reforecasts.exists(): state["state"] = "ready_for_authenticated_reforecast_retrieval"
    else: state["state"] = "ready_to_train_on_reforecasts"
    save_json(resolve(cfg, "STATUS.json"), state)
    return state


def forecast(cfg):
    from .backtest import forecast_rows
    root = resolve(cfg, cfg["experiment"]["output_dir"])
    path = root / "final/models.joblib"
    if not path.exists(): raise FileNotFoundError("Train on genuine reforecasts before operational post-processing")
    archive = validate_archive(pd.read_csv(resolve(cfg, cfg["download"]["forecast_file"])), cfg, "forecast")
    models = joblib.load(path)  # local, trusted project artifact only
    obs, _ = observations(cfg)
    frame = feature_table(archive, obs, cfg, models["mapper"])
    frame["corrected_point"] = models["residual"].predict(frame)
    frame = frame[frame.corrected_point.notna()].copy()
    if frame.empty: raise ValueError("No complete forecast horizons with a fitted residual model")
    if frame.issue_date.min() <= models["residual"].fitted_until: raise ValueError("Operational forecast overlaps model training")
    frame["base_fitted_until"] = models["residual"].fitted_until
    frame["post_fitted_until"] = models["postprocessor"].fitted_until
    existing, _ = existing_oof(cfg)
    frame = attach(frame, existing)
    values = json.loads((root / "final/thresholds.json").read_text())
    output = root / "forecasts"
    output.mkdir(exist_ok=True)
    table = forecast_rows(frame, obs, cfg, models["postprocessor"], models["blender"], models["training_years"], values)
    # Discard verifying observations from issued products even during a historical replay.
    table = table.drop(columns=["observed", "observed_peak_date", "fold_year"])
    table.to_csv(output / "corrected_products.csv.gz", index=False)
    native = archive.copy()
    native["seasonal_qm_cumecs"] = models["mapper"].transform(native)
    native.to_csv(output / "raw_and_qm_daily_members_30days.csv.gz", index=False)
    save_json(output / "forecast_manifest.json", {"source_sha256": sha(resolve(cfg, cfg["download"]["forecast_file"])),
        "issue_dates": [str(d) for d in sorted(archive.issue_date.unique())], "rows": len(table),
        "native_max_lead_day": int(archive.lead_day.max()), "corrected_products": "days 1-10 and weekly maxima for days 8-14,15-21,22-28",
        "days29_30": "Raw and seasonal-QM daily members only; no untrained residual horizon invented",
        "availability_assumption": "Configured nominal publication lag, not independently verified receipt timestamps"})
    return output


def run(cfg, action="status", limit=None, resume=False):
    if action == "status": return status(cfg)
    if action in ["bootstrap", "download", "all"]:
        snapshot_catalogue(cfg)
        grid = auxiliary(cfg)
        jobs = plan(cfg, grid)
        if action == "bootstrap": return status(cfg)
        retrieve(cfg, jobs, "reforecast", limit)
        retrieve(cfg, jobs, "forecast", 1)
        if action == "download": return status(cfg)
    if action in ["prepare", "all"]:
        for kind in ["reforecast", "forecast"]:
            output = resolve(cfg, cfg["download"][f"{kind}_file"])
            if not output.exists(): convert_files(cfg, kind)
        if action == "prepare": return status(cfg)
    if action in ["train", "all"]:
        from .backtest import train
        root = train(cfg, resume)
        (root / "requirements-lock.txt").write_text(subprocess.check_output([sys.executable, "-m", "pip", "freeze"], text=True))
    if action in ["forecast", "all"]: forecast(cfg)
    return status(cfg)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.yaml")))
    parser.add_argument("--action", choices=["status", "bootstrap", "download", "prepare", "train", "forecast", "all"], default="status")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    try:
        result = run(cfg, args.action, args.limit, args.resume)
        print(json.dumps(result, indent=2, default=str))
    except Exception as error:
        status(cfg)
        save_json(resolve(cfg, "LAST_ERROR.json"), {"action": args.action, "error_type": type(error).__name__, "message": str(error)[:1000]})
        raise
