"""Reuse existing flow/threshold/event metrics, including weekly-maximum targets."""
from pathlib import Path
import numpy as np
import pandas as pd
from .common import flow_metrics, threshold_metrics, peak_events, save_json


def evaluate(predictions, output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    scores, threshold_scores, peaks = [], [], []
    names = sorted(c[len("probability_"):] for c in predictions if c.startswith("probability_"))
    for (year, horizon, model), group in predictions.groupby(["fold_year", "horizon", "model"]):
        group = group.copy().reset_index(drop=True)
        meta = {"fold_year": int(year), "horizon": horizon, "model": model,
                "lead_start": int(group.lead_start.iloc[0]), "lead_end": int(group.lead_end.iloc[0])}
        score = {**meta, **flow_metrics(group.observed.to_numpy(), group.p50.to_numpy())}
        event_name = "train_q95" if "train_q95" in names else names[0]
        threshold = float(group[f"threshold_{event_name}_cumecs"].iloc[0])
        if meta["lead_start"] == meta["lead_end"]:
            found = peak_events(group, threshold)
            score["peak_metric_basis"] = "event_windows_on_available_forecast_dates"
        else:
            found = []
            high = group[(group.observed >= threshold) & group.p50.notna()]
            for _, row in high.iterrows():
                timing = ((pd.Timestamp(row.predicted_peak_date)-pd.Timestamp(row.observed_peak_date)).days
                          if pd.notna(row.predicted_peak_date) and pd.notna(row.observed_peak_date) else np.nan)
                found.append({"event_start": str(row.valid_start), "event_end": str(row.valid_date),
                    "observed_peak_date": str(row.observed_peak_date), "predicted_peak_date": str(row.predicted_peak_date),
                    "observed_peak_cumecs": row.observed, "predicted_peak_cumecs": row.p50,
                    "peak_magnitude_error_cumecs": row.p50-row.observed, "peak_timing_error_days": timing})
            score["peak_metric_basis"] = "overlapping_weekly_flood_maximum_windows"
        peaks.extend([{**meta, **event} for event in found])
        magnitude = [abs(event["peak_magnitude_error_cumecs"]) for event in found]
        timing = [abs(event["peak_timing_error_days"]) for event in found if np.isfinite(event["peak_timing_error_days"])]
        score.update({"n_peak_events_or_windows": len(found), "peak_magnitude_mae_cumecs": np.mean(magnitude) if magnitude else np.nan,
                      "peak_timing_mae_days": np.mean(timing) if timing else np.nan,
                      "coverage80": float(((group.observed >= group.p10) & (group.observed <= group.p90))[group.observed.notna()].mean())})
        scores.append(score)
        for name in names:
            values = group[f"threshold_{name}_cumecs"].to_numpy()
            threshold_scores.append({**meta, "threshold": name, "threshold_cumecs": values[0],
                **threshold_metrics(group.observed.to_numpy(), group[f"probability_{name}"].to_numpy(), values)})
    scores, threshold_scores, peaks = pd.DataFrame(scores), pd.DataFrame(threshold_scores), pd.DataFrame(peaks)
    scores.to_csv(output / "scores_by_season_and_horizon.csv", index=False)
    threshold_scores.to_csv(output / "threshold_scores_by_season_and_horizon.csv", index=False)
    peaks.to_csv(output / "peak_errors.csv", index=False)
    pooled, pooled_thresholds = [], []
    for (horizon, model), group in predictions.groupby(["horizon", "model"]):
        events = peaks[(peaks.horizon == horizon) & (peaks.model == model)] if not peaks.empty else pd.DataFrame()
        pooled.append({"horizon": horizon, "model": model, "lead_start": int(group.lead_start.iloc[0]), "lead_end": int(group.lead_end.iloc[0]),
            **flow_metrics(group.observed.to_numpy(), group.p50.to_numpy()),
            "peak_magnitude_mae_cumecs": events.peak_magnitude_error_cumecs.abs().mean() if len(events) else np.nan,
            "peak_timing_mae_days": events.peak_timing_error_days.abs().mean() if len(events) else np.nan})
        for name in names:
            pooled_thresholds.append({"horizon": horizon, "model": model, "threshold": name,
                **threshold_metrics(group.observed.to_numpy(), group[f"probability_{name}"].to_numpy(), group[f"threshold_{name}_cumecs"].to_numpy())})
    pooled, pooled_thresholds = pd.DataFrame(pooled), pd.DataFrame(pooled_thresholds)
    pooled.to_csv(output / "scores_by_horizon.csv", index=False)
    pooled_thresholds.to_csv(output / "threshold_scores_by_horizon.csv", index=False)
    comparisons = []
    for name in ["seasonal_QM", "LightGBM_residual", "GloFAS_corrected", "OOF_blend"]:
        for baseline in ["raw_GloFAS", "persistence", "climatology", "probabilistic_climatology"]:
            for horizon, group in pooled.groupby("horizon"):
                h, b = group[group.model == name], group[group.model == baseline]
                if h.empty or b.empty: continue
                h, b = h.iloc[0], b.iloc[0]
                comparisons.append({"model": name, "baseline": baseline, "horizon": horizon,
                    "lead_start": h.lead_start, "lead_end": h.lead_end, "starts_after_day10": h.lead_start > 10,
                    "kge_improvement": h.kge-b.kge, "mae_reduction_cumecs": b.mae_cumecs-h.mae_cumecs,
                    "peak_magnitude_mae_reduction_cumecs": b.peak_magnitude_mae_cumecs-h.peak_magnitude_mae_cumecs,
                    "peak_timing_mae_reduction_days": b.peak_timing_mae_days-h.peak_timing_mae_days})
    comparisons = pd.DataFrame(comparisons)
    comparisons.to_csv(output / "baseline_comparison.csv", index=False)
    long_range = comparisons[(comparisons.lead_end > 10) & comparisons.baseline.isin(["climatology", "probabilistic_climatology"])].copy()
    long_range["beats_climatology_on_kge_and_mae"] = (long_range.kge_improvement > 0) & (long_range.mae_reduction_cumecs > 0)
    long_range.to_csv(output / "beyond_day10_climatology_test.csv", index=False)
    save_json(output / "evaluation_manifest.json", {"evaluated_years": sorted(predictions.fold_year.unique().tolist()),
        "rows": len(predictions), "metrics_reused_from": "hbv_residual.evaluation: flow_metrics, threshold_metrics, peak_events",
        "weekly_target": "maximum, not mean; overlapping windows are not independent events",
        "weekly_timing": "Corrections inherit the raw daily-ensemble peak date; no independent weekly retiming model",
        "probabilistic_climatology": "Prior-year calendar windows +/-15 days, using complete observed weekly maxima",
        "daily_event_timing": "Available reforecast verification dates only; sparse cadence can miss inter-issue peaks"})
    lines = ["# GloFAS correction: rolling monsoon results", "",
        "Only genuinely held-out reforecast predictions enter these metrics. Base fits use previous whole years; "
        "QRF uses previous OOF base errors; blend weights use previous OOF full-stack forecasts. No days are assigned randomly.", "",
        "## Long-range skill against climatology", "",
        "See `beyond_day10_climatology_test.csv`: both higher KGE and lower MAE are required. Week 2 (days 8-14) "
        "overlaps daily leads 8-10; weeks 3-4 start strictly after day 10. Weekly labels are maxima, with a matching "
        "historical-window probabilistic climatology benchmark.", ""]
    for name, group in long_range.groupby("model"):
        lines.append(f"- {name}: beats its climatology benchmarks on both measures for {int(group.beats_climatology_on_kge_and_mae.sum())}/{len(group)} horizon/benchmark comparisons.")
    lines += ["", "All metrics and counts are saved as CSV. Small samples, overlapping windows, sparse reforecast issue dates, "
              "model-version changes, unverified gauge reading times, and uncertain operational publication latency limit interpretation. "
              "Bias-mapping upper tails and additive residual anchors are not capped at the largest training flow. "
              "This avoids an artificial ceiling but cannot guarantee that a model will never underpredict a flood peak.", ""]
    (output / "REPORT.md").write_text("\n".join(lines), encoding="utf-8")
    return pooled
