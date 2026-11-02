"""Adapt saved repository forecasts; require fit/selection and forcing provenance."""
import json
import numpy as np
import pandas as pd
from .common import resolve, horizons


def existing_oof(cfg):
    options = cfg["blending"]
    audit = {"reanalysis_rows_excluded": 0, "leakage_rows_excluded": 0, "accepted_rows": 0,
             "note": "Missing long-range forecasts are not extrapolated or replaced by observations."}
    if options.get("imported_oof_file"):
        path = resolve(cfg, options["imported_oof_file"])
        f = pd.read_csv(path, parse_dates=["issue_date", "fitted_until", "selected_until"])
        required = {"issue_date", "horizon", "p10", "p50", "p90", "fitted_until", "selected_until", "forcing_mode"}
        if not required.issubset(f): raise ValueError("Imported OOF forecasts lack lineage/schema")
        audit["source"] = str(path)
    else:
        path = resolve(cfg, options["existing_predictions"])
        if not path.exists():
            audit["status"] = "no_existing_oof_archive"
            return pd.DataFrame(), audit
        source = pd.read_csv(path, parse_dates=["issue_date"])
        source = source[source.model == options["existing_model"]]
        rows = []
        for year, subset in source.groupby("fold_year"):
            fold_path = resolve(cfg, options["existing_folds_dir"]) / str(int(year)) / "complete.json"
            if not fold_path.exists(): raise ValueError("Existing fold provenance missing")
            fold = json.loads(fold_path.read_text())
            for issue, group in subset.groupby("issue_date"):
                for name, first, last in horizons():
                    use = group[group.lead_day.between(first, last)].sort_values("lead_day")
                    if use.lead_day.tolist() != list(range(first, last+1)): continue
                    # Weekly maximum of marginal quantiles is only a shape proxy;
                    # do not invent a joint trajectory. Current HBV ends at day 10,
                    # therefore no complete weekly products are available here.
                    if first != last: continue
                    rows.append({"issue_date": issue, "horizon": name, "p10": float(use.p10.iloc[0]),
                                 "p50": float(use.p50.iloc[0]), "p90": float(use.p90.iloc[0]),
                                 "fitted_until": pd.Timestamp(fold["cutoff"]),
                                 "selected_until": pd.Timestamp(f"{int(year)-1}-12-31"),
                                 "forcing_mode": use.forcing_mode.iloc[0]})
        f = pd.DataFrame(rows)
        audit["source"] = str(path)
    if f.empty: return f, audit
    if f.duplicated(["issue_date", "horizon"]).any(): raise ValueError("Duplicate existing-model predictions")
    valid = (f.fitted_until < f.issue_date) & (f.selected_until < f.issue_date)
    audit["leakage_rows_excluded"] = int((~valid).sum())
    f = f[valid]
    if not options["allow_reanalysis_existing"]:
        accepted = f.forcing_mode.isin(["archived_forecast", "issued_forecast"])
        audit["reanalysis_rows_excluded"] = int((~accepted).sum())
        f = f[accepted]
    audit["accepted_rows"] = len(f)
    audit["status"] = "available" if len(f) else "no_operationally_comparable_existing_oof"
    return f, audit


def attach(frame, existing):
    frame = frame.copy()
    if existing.empty:
        for name in ["existing_p10", "existing_p50", "existing_p90"]: frame[name] = np.nan
        frame["existing_fitted_until"], frame["existing_selected_until"] = pd.NaT, pd.NaT
        return frame
    renamed = existing.rename(columns={"p10": "existing_p10", "p50": "existing_p50", "p90": "existing_p90",
                                        "fitted_until": "existing_fitted_until", "selected_until": "existing_selected_until"})
    return frame.merge(renamed[["issue_date", "horizon", "existing_p10", "existing_p50", "existing_p90",
                                "existing_fitted_until", "existing_selected_until"]], on=["issue_date", "horizon"], how="left", validate="one_to_one")
