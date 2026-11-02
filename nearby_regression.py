"""Usage: python nearby_regression.py [marala.csv] [nearby.csv]"""
import sys

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression


def load(path):
    df = pd.read_csv(path, parse_dates=['date']).set_index('date').sort_index()
    if df.index.has_duplicates or not (df.index == df.index.normalize()).all():
        raise ValueError(f'{path}: dates must be unique daily dates')
    q = pd.to_numeric(df['q_cumecs'], errors='raise').astype(float)
    if np.isinf(q).any() or (q.dropna() < 0).any():
        raise ValueError(f'{path}: discharge must be finite, nonnegative or NaN')
    return q


def scores(obs, pred, high_threshold):
    if len(obs) < 2:
        return (np.nan,) * 4
    obs, pred = np.asarray(obs), np.asarray(pred)
    denominator = np.sum((obs - obs.mean()) ** 2)
    nse = 1 - np.sum((pred - obs) ** 2) / denominator if denominator > 0 else np.nan
    if obs.std() > 0 and pred.std() > 0 and obs.mean() > 0:
        r = np.corrcoef(obs, pred)[0, 1]
        kge = 1 - np.sqrt((r - 1) ** 2 + (pred.std() / obs.std() - 1) ** 2
                         + (pred.mean() / obs.mean() - 1) ** 2)
    else:
        kge = np.nan
    # Positive bias means overprediction. Peak error is MAPE on high-flow days.
    bias = 100 * np.sum(pred - obs) / obs.sum() if obs.sum() > 0 else np.nan
    high = (obs > high_threshold) & (obs > 0)
    peak = 100 * np.mean(np.abs((pred[high] - obs[high]) / obs[high])) if high.any() else np.nan
    return nse, kge, bias, peak


def main():
    marala = load(sys.argv[1] if len(sys.argv) > 1 else 'marala.csv')
    nearby = load(sys.argv[2] if len(sys.argv) > 2 else 'nearby.csv')
    dates = pd.date_range(marala.index.min(), marala.index.max(), freq='D')
    y = marala.reindex(dates)
    # Positive lag: nearby on day t-lag predicts Marala on day t.
    x = pd.DataFrame({lag: nearby.reindex(dates - pd.Timedelta(days=lag)).to_numpy()
                      for lag in (0, 1, 2)}, index=dates)
    paired = pd.concat([y.rename('marala'), x[0].rename('nearby')], axis=1).dropna()
    print(f'Same-day overlap: {len(paired)} days; correlation: {paired.corr().iloc[0, 1]:.3f}')
    season = pd.Series(np.select([dates.month.isin([10, 11, 12, 1, 2, 3]),
                                 dates.month.isin([4, 5, 6])],
                                ['Oct-Mar', 'Apr-Jun'], default='Jul-Sep'), index=dates)

    # Hide disjoint, fully observed 30-calendar-day blocks; fixed random seed.
    rng = np.random.default_rng(42)
    hidden = pd.Series(False, index=dates)
    starts = np.flatnonzero(y.notna().rolling(30).sum().eq(30).to_numpy()) - 29
    target_blocks = max(1, round(0.20 * y.notna().sum() / 30))
    count = 0
    for start in rng.permutation(starts):
        block = dates[start:start + 30]
        if hidden.loc[block].any():
            continue
        hidden.loc[block] = True
        count += 1
        if count == target_blocks:
            break
    print(f'Hidden: {hidden.sum()} days in {count} blocks '
          f'({100 * hidden.sum() / max(1, y.notna().sum()):.1f}% of observations)')
    if count < target_blocks:
        print('WARNING: insufficient complete 30-day blocks for a 20% holdout.')

    # Compare lags on identical, non-held-out dates to avoid selection leakage.
    common = y.notna() & ~hidden & x.notna().all(axis=1)
    correlations = {lag: y[common].corr(x.loc[common, lag]) for lag in x}
    for lag, correlation in correlations.items():
        print(f'Lag {lag}: training correlation={correlation:.3f}, n={common.sum()}')
    usable = {lag: r for lag, r in correlations.items() if np.isfinite(r)}
    if not usable:
        raise ValueError('Not enough overlapping variable observations to select a lag')
    best = max(usable, key=usable.get)
    print(f'Best lag: {best} days (nearby leads Marala)')
    predictor = x[best]
    filled = y.copy()
    source = pd.Series('', index=dates)
    source.loc[y.notna()] = 'observed'

    for name in ('Oct-Mar', 'Apr-Jun', 'Jul-Sep'):
        in_season = season.eq(name)
        train = in_season & ~hidden & y.gt(0) & predictor.gt(0)
        test = in_season & hidden & y.notna() & predictor.gt(0)
        if train.sum() < 10 or test.sum() < 2 or predictor[train].nunique() < 2:
            print(f'WARNING {name}: insufficient training/validation data; not filling.')
            continue
        model = LinearRegression().fit(np.log(predictor[train]).to_numpy()[:, None],
                                       np.log(y[train]).to_numpy())
        predictions = np.exp(model.predict(np.log(predictor[test]).to_numpy()[:, None]))
        threshold = y[train].quantile(0.95)
        nse, kge, bias, peak = scores(y[test], predictions, threshold)
        coverage = test.sum() / max(1, (in_season & hidden).sum())
        print(f'{name}: a={model.intercept_:.4f}, b={model.coef_[0]:.4f}; '
              f'n={test.sum()}, validation coverage={coverage:.0%}, '
              f'NSE={nse:.3f}, KGE={kge:.3f}, bias={bias:.1f}%, '
              f'peak MAPE={peak:.1f}% (training Q95={threshold:.2f})')
        if not np.isfinite(nse) or nse < 0.8:
            print(f'WARNING {name}: NSE below 0.8 or undefined; not filling.')
            continue
        # Refit accepted seasons using all paired positive observations.
        fit = in_season & y.gt(0) & predictor.gt(0)
        model.fit(np.log(predictor[fit]).to_numpy()[:, None], np.log(y[fit]).to_numpy())
        gaps = in_season & y.isna() & predictor.gt(0)
        if gaps.any():
            estimates = np.exp(model.predict(np.log(predictor[gaps]).to_numpy()[:, None]))
            estimates[~np.isfinite(estimates)] = np.nan
            filled.loc[gaps] = estimates
            source.loc[gaps & filled.notna()] = 'nearby_gauge'

    output = pd.DataFrame({'date': dates, 'q_cumecs': filled.to_numpy(),
                           'q_source': source.to_numpy(), 'is_observed': y.notna().to_numpy()})
    assert np.array_equal(filled[y.notna()].to_numpy(), y.dropna().to_numpy())
    output.to_csv('marala_discharge_regression.csv', index=False, na_rep='NaN')
    print(f"Saved marala_discharge_regression.csv; filled {source.eq('nearby_gauge').sum()} days.")


if __name__ == '__main__':
    main()
