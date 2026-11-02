"""One small direct LightGBM per daily lead/weekly-maximum product."""
import numpy as np
import pandas as pd
import lightgbm as lgb
from .data import feature_columns


class DirectResidualModel:
    def __init__(self, options, seed=42, threads=2, minimum=40):
        self.options, self.seed, self.threads, self.minimum = options, seed, threads, minimum
        self.models = {}

    def fit(self, frame):
        self.features = feature_columns(frame)
        train = frame[np.isfinite(frame.observed)].copy()
        if train.empty: raise ValueError("No observed residual targets")
        self.fitted_until = train.valid_date.max()
        for horizon, group in train.groupby("horizon"):
            if len(group) < self.minimum: continue
            model = lgb.LGBMRegressor(objective="regression", n_estimators=self.options["n_estimators"],
                learning_rate=self.options["learning_rate"], num_leaves=self.options["num_leaves"],
                min_child_samples=self.options["min_child_samples"], reg_lambda=self.options["reg_lambda"],
                n_jobs=self.threads, random_state=self.seed, deterministic=True, force_col_wise=True, verbosity=-1)
            # Requested residual target is OBSERVED MINUS RAW GLOFAS. No log(Q),
            # target winsorization or quantile clipping that would erase extremes.
            model.fit(group[self.features], group.observed-group.raw_p50)
            self.models[horizon] = model
        if not self.models: raise ValueError("No horizon has enough reforecast residual samples")
        return self

    def predict(self, frame):
        result = pd.Series(np.nan, index=frame.index, dtype=float)
        for horizon, group in frame.groupby("horizon"):
            if horizon not in self.models: continue
            residual = self.models[horizon].predict(group[self.features])
            result.loc[group.index] = np.maximum(0., group.raw_p50.to_numpy()+residual)
        return result
