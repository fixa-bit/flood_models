"""QRF of out-of-sample additive errors, preserving the forecast's peak scale."""
import numpy as np
import pandas as pd
from sklearn.impute import SimpleImputer
from quantile_forest import RandomForestQuantileRegressor
from .data import feature_columns


def assert_oof(frame):
    if "base_fitted_until" not in frame: raise ValueError("OOF fit-end provenance is required")
    fitted = pd.to_datetime(frame.base_fitted_until)
    if fitted.isna().any() or not (fitted < pd.to_datetime(frame.issue_date)).all():
        raise ValueError("In-sample/future-fitted predictions cannot train post-processing or blending")


class EnsemblePostprocessor:
    def __init__(self, options, seed=42, threads=2, minimum=40):
        self.options, self.seed, self.threads, self.minimum = options, seed, threads, minimum
        self.models = {}

    def fit(self, oof):
        assert_oof(oof)
        self.features = feature_columns(oof) + ["corrected_point"]
        selected = oof[np.isfinite(oof.observed) & np.isfinite(oof.corrected_point)]
        self.fitted_until = selected.valid_date.max() if len(selected) else pd.NaT
        for horizon, group in selected.groupby("horizon"):
            if len(group) < self.minimum: continue
            imputer = SimpleImputer(strategy="median", add_indicator=True, keep_empty_features=True)
            x = imputer.fit_transform(group[self.features])
            model = RandomForestQuantileRegressor(
                n_estimators=self.options["n_estimators"], min_samples_leaf=self.options["min_samples_leaf"],
                max_depth=self.options["max_depth"], max_samples_leaf=self.options.get("max_samples_leaf"),
                random_state=self.seed, n_jobs=self.threads, bootstrap=True)
            # Predict errors around an UNBOUNDED raw-flow-plus-residual anchor.
            # Fitting Q directly in a forest would cap extremes at training flows.
            model.fit(x, group.observed.to_numpy()-group.corrected_point.to_numpy())
            self.models[horizon] = (imputer, model)
        return self

    def quantiles(self, frame, levels=(.1, .5, .9)):
        levels = np.asarray(levels)
        output = np.empty((len(frame), len(levels)))
        positions = pd.Series(np.arange(len(frame)), index=frame.index)
        for horizon, group in frame.groupby("horizon"):
            ix = positions.loc[group.index].to_numpy()
            if horizon in self.models:
                imputer, model = self.models[horizon]
                x = imputer.transform(group[self.features])
                error = np.asarray(model.predict(x, quantiles=levels.tolist())).reshape(len(group), -1)
                output[ix] = group.corrected_point.to_numpy()[:, None]+error
            else:
                for position, (_, row) in zip(ix, group.iterrows()):
                    members = np.asarray(row.raw_members)
                    output[position] = row.corrected_point + np.quantile(members, levels) - np.median(members)
        return np.maximum(0., output)

    def exceedance(self, frame, threshold):
        probability = np.empty(len(frame))
        positions = pd.Series(np.arange(len(frame)), index=frame.index)
        for horizon, group in frame.groupby("horizon"):
            ix = positions.loc[group.index].to_numpy()
            if horizon in self.models:
                imputer, model = self.models[horizon]
                x = imputer.transform(group[self.features])
                rank = model.quantile_ranks(x, threshold-group.corrected_point.to_numpy(), kind="strict")
                probability[ix] = 1-np.asarray(rank).ravel()
            else:
                for position, (_, row) in zip(ix, group.iterrows()):
                    members = row.corrected_point + np.asarray(row.raw_members)-np.median(row.raw_members)
                    probability[position] = float((np.maximum(0., members) >= threshold).mean())
        return np.clip(probability, 0., 1.)
