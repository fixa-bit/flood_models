"""Nested expanding-year OOF training; complete monsoons are the test partitions."""
import argparse
import json
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from .common import load_config, resolve, observations, climatology, daily_climate, save_json, sha
from .data import validate_archive, feature_table, verify_source_archive
from .bias_correction import SeasonalQuantileMapper
from .residual import DirectResidualModel
from .ensemble import EnsemblePostprocessor
from .blending import OOFBlender
from .existing_model import existing_oof, attach


LEVELS = np.linspace(.005, .995, 199)


def fit_base(archive, obs, cfg, prediction_year):
    years = list(range(cfg["experiment"]["first_training_year"], prediction_year))
    mapper = SeasonalQuantileMapper(**cfg["bias"]).fit(archive, obs, years)
    # Only look at data through this held-out year; all gauge covariates are
    # additionally cut off at each issue's own observation-availability date.
    subset = archive[archive.issue_date.dt.year <= prediction_year]
    frame = feature_table(subset, obs, cfg, mapper)
    training = frame[frame.year.isin(years)].copy()
    model = DirectResidualModel(cfg["residual"], cfg["experiment"]["seed"], cfg["experiment"]["threads"],
                                cfg["experiment"]["min_samples_per_horizon"]).fit(training)
    cutoff = max(mapper.fitted_until, model.fitted_until)
    predicted = frame[(frame.year == prediction_year) & (frame.issue_date > cutoff)].copy()
    predicted["corrected_point"] = model.predict(predicted)
    predicted = predicted[np.isfinite(predicted.corrected_point)].copy()
    predicted["base_fitted_until"] = cutoff
    if predicted.empty: raise ValueError(f"No OOF horizons for {prediction_year}")
    return mapper, model, training, predicted


def thresholds(obs, years, cfg):
    q = obs.loc[obs.index.year.isin(years), "q_cumecs"].dropna()
    result = {f"train_q{int(level*100)}": float(q.quantile(level)) for level in cfg["experiment"]["statistical_threshold_quantiles"]}
    for name, value in cfg["experiment"]["thresholds_cumecs"].items():
        if not str(name).replace("_", "").isalnum() or value <= 0: raise ValueError("Threshold names/values invalid")
        result[str(name)] = float(value)
    return result


def historical_window_climatology(obs, dates, years):
    """Calendar-conditioned historical weekly maxima, not daily-mean surrogates."""
    values = []
    for year in years:
        for shift in range(-15, 16):
            try: start = pd.Timestamp(year=year, month=dates[0].month, day=dates[0].day)+pd.Timedelta(days=shift)
            except ValueError: continue
            window = pd.date_range(start, periods=len(dates))
            if not window.year.isin(years).all(): continue
            observed = obs.q_cumecs.reindex(window)
            if observed.notna().all(): values.append(float(observed.max()))
    return np.asarray(values)


def forecast_rows(frame, obs, cfg, post, blender, years, threshold_values):
    frame = frame.copy().reset_index(drop=True)
    corrected = post.quantiles(frame, LEVELS)
    corrected_probs = {name: post.exceedance(frame, threshold) for name, threshold in threshold_values.items()}
    climate = climatology(cfg, obs, years)
    rows = []
    for index, row in frame.iterrows():
        raw = np.asarray(row.raw_members)
        qm = np.asarray(row.qm_members)
        direct = np.maximum(0., raw+row.corrected_point-row.raw_p50)
        raw_curve, qm_curve, direct_curve = [np.quantile(v, LEVELS) for v in [raw, qm, direct]]
        existing_curve = np.interp(LEVELS, [.1, .5, .9], [row.existing_p10, row.existing_p50, row.existing_p90]) if np.isfinite(row.existing_p50) else None
        blend_curve, used_weights = blender.combine(row.horizon, {"raw": raw_curve, "corrected": corrected[index], "existing": existing_curve})
        dates = pd.date_range(row.valid_start, row.valid_date)
        deterministic_climate = float(daily_climate(climate, dates).max())
        climate_samples = historical_window_climatology(obs, dates, years)
        curves = {"raw_GloFAS": raw_curve, "seasonal_QM": qm_curve, "LightGBM_residual": direct_curve,
                  "GloFAS_corrected": corrected[index], "OOF_blend": blend_curve,
                  "persistence": np.full(len(LEVELS), row.q_asof),
                  "climatology": np.full(len(LEVELS), deterministic_climate)}
        if len(climate_samples): curves["probabilistic_climatology"] = np.quantile(climate_samples, LEVELS)
        if existing_curve is not None: curves["existing_model"] = existing_curve
        for name, curve in curves.items():
            q = np.interp([.1, .5, .9], LEVELS, curve)
            record = {"fold_year": int(row.year), "issue_date": row.issue_date, "valid_date": row.valid_date,
                "valid_start": row.valid_start, "horizon": row.horizon, "lead_start": int(row.lead_start), "lead_end": int(row.lead_end),
                "monsoon": bool(row.monsoon), "model": name, "observed": row.observed,
                "observed_peak_date": row.observed_peak_date,
                "predicted_peak_date": row.corrected_peak_date if name == "seasonal_QM" else row.raw_peak_date,
                "p10": q[0], "p50": q[1], "p90": q[2], "member_count": int(row.member_count),
                "base_fitted_until": row.base_fitted_until, "post_fitted_until": row.post_fitted_until,
                "statistic": "daily_flow" if row.lead_start == row.lead_end else "weekly_maximum",
                "uncertainty_method": "OOF_QRF" if name == "GloFAS_corrected" and row.horizon in post.models else
                                      "common_rank_quantile_pool" if name == "OOF_blend" else "empirical_or_point",
                "blend_weights": json.dumps(used_weights) if name == "OOF_blend" else ""}
            if row.lead_start != row.lead_end and name in ["persistence", "climatology", "probabilistic_climatology"]:
                record["predicted_peak_date"] = pd.NaT  # no invented timing from a weekly scalar baseline
            for threshold_name, threshold in threshold_values.items():
                if name == "GloFAS_corrected": probability = corrected_probs[threshold_name][index]
                elif name in ["raw_GloFAS", "seasonal_QM", "LightGBM_residual"]:
                    probability = float((({"raw_GloFAS": raw, "seasonal_QM": qm, "LightGBM_residual": direct}[name]) >= threshold).mean())
                elif name == "probabilistic_climatology": probability = float((climate_samples >= threshold).mean())
                else: probability = float((curve >= threshold).mean()) if np.isfinite(curve).all() else np.nan
                record[f"threshold_{threshold_name}_cumecs"] = threshold
                record[f"probability_{threshold_name}"] = probability
            rows.append(record)
    return pd.DataFrame(rows)


def train(cfg, resume=False):
    root = resolve(cfg, cfg["experiment"]["output_dir"])
    archive_path = resolve(cfg, cfg["download"]["reforecast_file"])
    if not archive_path.exists(): raise FileNotFoundError("Genuine processed GloFAS reforecasts are required; no training on reanalysis or fabricated data")
    verify_source_archive(cfg, archive_path)
    if (root / "complete.json").exists() and not resume: raise FileExistsError("Choose a new output_dir to preserve the existing run")
    archive = validate_archive(pd.read_csv(archive_path), cfg, "reforecast")
    obs, project = observations(cfg)
    source_path = Path(project["_root"]) / project["data"]["daily_file"]
    hashes = {str(archive_path): sha(archive_path), str(source_path.resolve()): sha(source_path)}
    root.mkdir(parents=True, exist_ok=True)
    existing, existing_audit = existing_oof(cfg)
    save_json(root / "existing_model_audit.json", existing_audit)
    save_json(root / "config.json", {k: v for k, v in cfg.items() if not k.startswith("_")})
    base_history, stacked_history, reports = [], [], []
    for year in range(cfg["experiment"]["first_oof_year"], max(cfg["experiment"]["test_years"])+1):
        print(f"Expanding OOF year {year}: fit on whole years before {year}", flush=True)
        mapper, model, training, predicted = fit_base(archive, obs, cfg, year)
        post = EnsemblePostprocessor(cfg["postprocessing"], cfg["experiment"]["seed"], cfg["experiment"]["threads"], cfg["experiment"]["min_qrf_samples"])
        post.fitted_until = pd.NaT
        if base_history: post.fit(pd.concat(base_history, ignore_index=True))
        predicted = attach(predicted, existing)
        predicted["post_fitted_until"] = post.fitted_until
        predicted["corrected_p50"] = post.quantiles(predicted, [.5])[:, 0]
        if pd.notna(post.fitted_until) and not (predicted.issue_date > post.fitted_until).all(): raise ValueError("QRF temporal leakage")
        blender = OOFBlender(cfg["blending"]["min_samples"], cfg["blending"]["peak_weight"])
        if stacked_history: blender.fit(pd.concat(stacked_history, ignore_index=True))
        fold = root / "folds" / str(year)
        fold.mkdir(parents=True, exist_ok=True)
        joblib.dump({"mapper": mapper, "residual": model, "postprocessor": post, "blender": blender,
                     "training_years": list(range(cfg["experiment"]["first_training_year"], year))}, fold / "models.joblib")
        save_json(fold / "bias_mapping.json", mapper.to_dict())
        save_json(fold / "blend_weights.json", {"weights": blender.weights, "audit": blender.audit})
        for name, estimator in model.models.items(): estimator.booster_.save_model(str(fold / f"lightgbm_{name}.txt"))
        # Arrays stay in a trusted local pickle; scalar audits are separately readable CSV.
        predicted.to_pickle(fold / "oof_features.pkl")
        predicted.drop(columns=["raw_members", "qm_members"]).to_csv(fold / "oof_audit.csv", index=False)
        years = list(range(cfg["experiment"]["first_training_year"], year))
        if year in cfg["experiment"]["test_years"]:
            selected = predicted[predicted.monsoon].copy()
            if selected.empty: raise ValueError(f"No monsoon test data for {year}")
            if not post.models: raise ValueError("No genuinely OOF QRF training data available")
            values = thresholds(obs, years, cfg)
            output = forecast_rows(selected, obs, cfg, post, blender, years, values)
            output.to_csv(fold / "predictions.csv.gz", index=False)
            reports.append(output)
        base_history.append(predicted)
        stacked_history.append(predicted)
        save_json(fold / "complete.json", {"year": year, "training_rows": len(training), "oof_rows": len(predicted),
            "base_fitted_until": str(predicted.base_fitted_until.iloc[0]), "post_fitted_until": str(post.fitted_until),
            "training_years": years, "qrf_horizons": list(post.models), "base_horizons": list(model.models)})
    if not all(sha(path) == h for path, h in hashes.items()): raise RuntimeError("An input archive or observed table changed")
    save_json(root / "source_hashes.json", hashes)
    predictions = pd.concat(reports, ignore_index=True)
    predictions.to_csv(root / "rolling_predictions.csv.gz", index=False)
    from .evaluate import evaluate
    evaluate(predictions, root / "reports")
    # All-data deployment refit is explicitly separate from the OOF evaluation.
    last_year = int(archive.issue_date.dt.year.max())
    full_years = list(range(cfg["experiment"]["first_training_year"], last_year+1))
    mapper = SeasonalQuantileMapper(**cfg["bias"]).fit(archive, obs, full_years)
    full = feature_table(archive, obs, cfg, mapper)
    full = full[full.year.isin(full_years)].copy()
    model = DirectResidualModel(cfg["residual"], cfg["experiment"]["seed"], cfg["experiment"]["threads"], cfg["experiment"]["min_samples_per_horizon"]).fit(full)
    post = EnsemblePostprocessor(cfg["postprocessing"], cfg["experiment"]["seed"], cfg["experiment"]["threads"], cfg["experiment"]["min_qrf_samples"]).fit(pd.concat(base_history, ignore_index=True))
    blend = OOFBlender(cfg["blending"]["min_samples"], cfg["blending"]["peak_weight"]).fit(pd.concat(stacked_history, ignore_index=True))
    final = root / "final"
    final.mkdir(exist_ok=True)
    joblib.dump({"mapper": mapper, "residual": model, "postprocessor": post, "blender": blend, "training_years": full_years}, final / "models.joblib")
    save_json(final / "thresholds.json", thresholds(obs, full_years, cfg))
    save_json(root / "complete.json", {"status": "complete", "reforecast_training": True, "test_years": cfg["experiment"]["test_years"],
              "prediction_rows": len(predictions), "all_data_refit_years": full_years,
              "existing_model_audit": existing_audit, "no_claim_of_peak_timing_correction_beyond_daily_leads": True})
    return root


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.yaml")))
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    print(train(load_config(args.config), args.resume))
