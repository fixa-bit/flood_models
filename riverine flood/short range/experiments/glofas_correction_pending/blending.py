"""Lead-dependent convex weights fitted only to chronologically OOF forecasts."""
import numpy as np
import pandas as pd
from scipy.optimize import minimize
from .ensemble import assert_oof


class OOFBlender:
    members = ["raw", "corrected", "existing"]

    def __init__(self, minimum=40, peak_weight=2.):
        self.minimum, self.peak_weight = minimum, peak_weight
        self.weights, self.audit = {}, {}

    def fit(self, frame):
        assert_oof(frame)
        if "post_fitted_until" in frame:
            known = frame.post_fitted_until.notna()
            if not (pd.to_datetime(frame.loc[known, "post_fitted_until"]) < pd.to_datetime(frame.loc[known, "issue_date"])).all():
                raise ValueError("Postprocessor was fitted on future/in-sample blend targets")
        self.fitted_until = frame.valid_date.max()
        for horizon, group in frame.groupby("horizon"):
            active = ["raw", "corrected"]
            if group.existing_p50.notna().sum() >= self.minimum:
                active.append("existing")
                known = group.existing_p50.notna()
                if not (pd.to_datetime(group.loc[known, "existing_selected_until"]) < pd.to_datetime(group.loc[known, "issue_date"])).all():
                    raise ValueError("Existing model selection overlaps OOF blend season")
                if not (pd.to_datetime(group.loc[known, "existing_fitted_until"]) < pd.to_datetime(group.loc[known, "issue_date"])).all():
                    raise ValueError("Existing model fitting overlaps OOF blend season")
            columns = [f"{name}_p50" for name in active]
            group = group.dropna(subset=columns+["observed"])
            if len(group) < self.minimum:
                self.weights[horizon] = {"raw": 1., "corrected": 0., "existing": 0.}
                self.audit[horizon] = {"samples": len(group), "status": "insufficient_oof_raw_fallback"}
                continue
            x, y = group[columns].to_numpy(), group.observed.to_numpy()
            threshold = np.quantile(y, .95)
            importance = np.where(y >= threshold, self.peak_weight, 1.)
            objective = lambda w: float(np.average(np.abs(x@w-y), weights=importance))
            initial = [np.eye(len(active))[j] for j in range(len(active))] + [np.full(len(active), 1/len(active))]
            candidates = list(initial)
            for start in initial:
                result = minimize(objective, start, method="SLSQP", bounds=[(0., 1.)]*len(active),
                                  constraints=[{"type": "eq", "fun": lambda w: w.sum()-1}],
                                  options={"maxiter": 200, "ftol": 1e-8})
                if result.success:
                    weights = np.maximum(result.x, 0)
                    candidates.append(weights/weights.sum())
            chosen = min(candidates, key=objective)
            self.weights[horizon] = {name: float(chosen[active.index(name)]) if name in active else 0. for name in self.members}
            self.audit[horizon] = {"samples": len(group), "active_members": active, "weighted_oof_mae": objective(chosen),
                                    "last_verifying_date": str(group.valid_date.max()), "status": "oof_fitted"}
        return self

    def combine(self, horizon, quantile_curves):
        available = [name for name, curve in quantile_curves.items() if curve is not None and np.isfinite(curve).all()]
        if not available: raise ValueError("No component forecast available")
        weights = self.weights.get(horizon, {"raw": 1., "corrected": 0., "existing": 0.})
        active = np.array([weights.get(name, 0.) for name in available])
        if active.sum() <= 0: active = np.array([1. if name == "raw" else 0. for name in available])
        if active.sum() <= 0: active = np.ones(len(available))
        active /= active.sum()
        # Common-rank coupling of component quantile functions. This gives a
        # coherent monotone quantile curve with the same P50 as the point blend.
        curve = np.sum([weight*np.asarray(quantile_curves[name]) for name, weight in zip(available, active)], axis=0)
        return curve, dict(zip(available, active.tolist()))
