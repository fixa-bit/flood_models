"""Seasonal, lead-specific empirical QM with uncapped additive upper tails."""
import numpy as np
import pandas as pd


def season(month):
    return "winter" if month in [12, 1, 2] else "pre_monsoon" if month in [3, 4, 5] else "monsoon" if month in [6, 7, 8, 9] else "post_monsoon"


class SeasonalQuantileMapper:
    def __init__(self, min_pairs=25, n_quantiles=101, tail_slope=1.):
        self.min_pairs, self.n_quantiles, self.tail_slope = min_pairs, n_quantiles, tail_slope
        if tail_slope < 1: raise ValueError("Upper-tail increments must not be artificially damped")
        self.maps = {}

    def fit(self, archive, obs, training_years):
        if set(archive.product_kind) != {"reforecast"}: raise ValueError("QM may only fit reforecasts")
        paired = archive.groupby(["issue_date", "valid_date", "lead_day"], as_index=False).q_cumecs.median()
        paired = paired[paired.valid_date.dt.year.isin(training_years)].copy()
        paired["observed"] = obs.q_cumecs.reindex(paired.valid_date).to_numpy()
        paired = paired.dropna(subset=["observed", "q_cumecs"])
        paired["season"] = paired.valid_date.dt.month.map(season)
        if paired.empty: raise ValueError("No paired discharge observations for bias mapping")
        self.fitted_until = paired.valid_date.max()
        self.training_years = sorted(training_years)
        for lead, lead_frame in paired.groupby("lead_day"):
            self.maps[f"{lead}:all"] = self._grid(lead_frame)
            for name, frame in lead_frame.groupby("season"):
                if len(frame) >= self.min_pairs: self.maps[f"{lead}:{name}"] = self._grid(frame)
        return self

    def _grid(self, frame):
        if len(frame) < self.min_pairs: raise ValueError("Insufficient train-only QM pairs for a lead")
        probabilities = np.linspace(0, 1, self.n_quantiles)
        x, y = np.quantile(frame.q_cumecs, probabilities), np.quantile(frame.observed, probabilities)
        unique = np.unique(x)
        ref = y[np.searchsorted(x, unique, side="right")-1]
        return {"source": unique.tolist(), "reference": ref.tolist(), "pairs": len(frame)}

    def transform(self, frame):
        result = np.empty(len(frame))
        for i, row in enumerate(frame.itertuples()):
            key = f"{row.lead_day}:{season(row.valid_date.month)}"
            if key not in self.maps: key = f"{row.lead_day}:all"
            grid = self.maps[key]
            x, y = grid["source"], grid["reference"]
            mapped = np.interp(row.q_cumecs, x, y)
            if row.q_cumecs > x[-1]: mapped = y[-1] + self.tail_slope*(row.q_cumecs-x[-1])
            elif row.q_cumecs < x[0]: mapped = y[0] + (row.q_cumecs-x[0])
            result[i] = max(0., mapped)
        return result

    def to_dict(self):
        return {"maps": self.maps, "training_years": self.training_years, "fitted_until": str(self.fitted_until),
                "min_pairs": self.min_pairs, "n_quantiles": self.n_quantiles, "tail_slope": self.tail_slope}
