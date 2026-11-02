"""Compare observed Chenab proxies; do not fill or modify discharge records.

2024-2025: ten random 30-day-block validation splits. 2026: later-year check.
Negative lag uses a later nearby reading and is for retrospective reconstruction.
"""
import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
DATA = PROJECT / 'riverine flood/short range/dataset/chenab_marala/raw/marala/discharge/nearby stations'
CATALOG = DATA.parents[3] / 'processed/marala/discharge'
OUT = HERE / 'results'
STATIONS = ('Khanki', 'Qadirabad', 'Trimmu')
SEASONS = ('Oct-Mar', 'Apr-Jun', 'Jul-Sep')
MODES = {'past_only': (0, 1, 2), 'reconstruction': (-2, -1, 0, 1, 2)}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_marala():
    collector = load_module('nearby_collector', DATA / 'collect_ffd.py')
    collector.STATIONS = ('Marala',)
    catalogs = [row for year in (2024, 2025, 2026)
                for row in pd.read_csv(CATALOG / f'marala_ffd_{year}_bulletin_discharge.csv', keep_default_na=False).to_dict('records')]
    lookup = {r['source_url']: r for r in catalogs}
    rows = []
    manifest = pd.read_csv(DATA / 'source_manifest.csv', keep_default_na=False)
    for receipt in manifest.to_dict('records'):
        body = (DATA / receipt['local_file']).read_bytes()
        assert hashlib.sha256(body).hexdigest() == receipt['sha256']
        rows.extend(collector.parse(int(receipt['year']), lookup[receipt['url']], body, receipt))
    full = pd.DataFrame(rows)
    full.to_csv(OUT / 'marala_observations_with_provenance.csv', index=False)
    accepted = full[full['eligible_daily'].eq(1)].copy()
    assert len(accepted) == 350, 'Recheck date/time eligibility against collected station sources'
    assert accepted.groupby('date')['inflow_cumecs'].nunique().le(1).all()
    accepted = accepted.drop_duplicates('date').set_index(pd.to_datetime(accepted.drop_duplicates('date')['date']))
    return pd.to_numeric(accepted['inflow_cumecs']).sort_index()


def measure(obs, pred, threshold):
    a, b = np.asarray(obs), np.asarray(pred)
    if len(a) < 2:
        return dict(n=len(a), nse=np.nan, kge=np.nan, pbias_pct=np.nan,
                    rmse_cumecs=np.nan, mae_cumecs=np.nan, peak_mape_pct=np.nan, peak_n=0)
    denom = np.sum((a - a.mean()) ** 2)
    nse = 1 - np.sum((b - a) ** 2) / denom if denom > 0 else np.nan
    r = np.corrcoef(a, b)[0, 1] if a.std() > 0 and b.std() > 0 else np.nan
    kge = 1 - np.sqrt((r - 1) ** 2 + (b.std() / a.std() - 1) ** 2 + (b.mean() / a.mean() - 1) ** 2) if a.std() > 0 and a.mean() > 0 else np.nan
    high = (a > threshold) & (a > 0)
    return dict(n=len(a), nse=nse, kge=kge,
                pbias_pct=100 * np.sum(b - a) / np.sum(a),
                rmse_cumecs=np.sqrt(np.mean((a - b) ** 2)), mae_cumecs=np.mean(np.abs(a - b)),
                peak_mape_pct=100 * np.mean(np.abs((b[high] - a[high]) / a[high])) if high.any() else np.nan,
                peak_n=int(high.sum()))


def fit_and_score(y, predictors, season, train, test, station, mode, split_name):
    lags = MODES[mode]
    correlations = {lag: y[train].corr(predictors[lag][train]) for lag in lags}
    lag = max(correlations, key=correlations.get)
    x = predictors[lag]
    summaries, predictions = [], []
    for name in SEASONS:
        a, b = train & season.eq(name), test & season.eq(name)
        if a.sum() < 10 or b.sum() < 2 or x[a].nunique() < 2:
            summaries.append(dict(station=station, mode=mode, split=split_name, season=name,
                                  lag=lag, train_n=int(a.sum()), n=int(b.sum()), status='insufficient_data'))
            continue
        reg = LinearRegression().fit(np.log(x[a]).to_numpy()[:, None], np.log(y[a]))
        pred = np.exp(reg.predict(np.log(x[b]).to_numpy()[:, None]))
        assert np.isfinite(pred).all()
        threshold = y[a].quantile(0.95)
        result = measure(y[b], pred, threshold)
        summaries.append(dict(station=station, mode=mode, split=split_name, season=name,
                              lag=lag, train_n=int(a.sum()), **result, status='evaluated',
                              log_intercept=float(reg.intercept_), log_slope=float(reg.coef_[0]),
                              train_correlation=float(correlations[lag]), train_q95=float(threshold),
                              passes_nse_08=bool(np.isfinite(result['nse']) and result['nse'] >= 0.8)))
        for day, observed, predicted in zip(y[b].index, y[b], pred):
            predictions.append(dict(station=station, mode=mode, split=split_name, season=name,
                                    date=day.date().isoformat(), nearby_date=(day - pd.Timedelta(days=lag)).date().isoformat(),
                                    lag=lag, observed_cumecs=observed, predicted_cumecs=predicted,
                                    above_train_q95=bool(observed > threshold)))
    return summaries, predictions


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    marala = load_marala()
    dates = pd.date_range(marala.index.min(), marala.index.max(), freq='D')
    y = marala.reindex(dates)
    y.rename('q_cumecs').rename_axis('date').to_csv(OUT / 'marala.csv', na_rep='NaN')
    season = pd.Series(np.select([dates.month.isin([10, 11, 12, 1, 2, 3]), dates.month.isin([4, 5, 6])],
                                 ['Oct-Mar', 'Apr-Jun'], default='Jul-Sep'), index=dates)
    predictors, descriptive = {}, []
    common = y.gt(0)
    for station in STATIONS:
        nearby = pd.read_csv(DATA / station / 'nearby.csv', parse_dates=['date']).set_index('date')['q_cumecs']
        predictors[station] = {lag: nearby.reindex(dates - pd.Timedelta(days=lag)).set_axis(dates) for lag in (-2, -1, 0, 1, 2)}
        for lag, x in predictors[station].items():
            paired = y.gt(0) & x.gt(0)
            descriptive.append(dict(station=station, lag=lag, overlap=int(paired.sum()),
                                    correlation=y[paired].corr(x[paired])))
            common &= x.gt(0)
    pd.DataFrame(descriptive).to_csv(OUT / 'descriptive_lag_correlations.csv', index=False)
    dev = pd.Series(dates.year <= 2025, index=dates)
    later = pd.Series(dates.year == 2026, index=dates)
    # Exact same target dates for every station and both lag modes.
    dev_common, later_common = common & dev, common & later
    summaries, predictions, blocks = [], [], []
    starts = np.flatnonzero((y.notna() & dev).rolling(30).sum().eq(30).to_numpy()) - 29
    target_blocks = max(1, round(0.2 * (y.notna() & dev).sum() / 30))
    for seed in range(10):
        hidden = pd.Series(False, index=dates)
        count = 0
        for start in np.random.default_rng(seed).permutation(starts):
            block = dates[start:start + 30]
            if hidden.loc[block].any():
                continue
            hidden.loc[block] = True
            blocks.append(dict(seed=seed, start=block[0].date().isoformat(), end=block[-1].date().isoformat()))
            count += 1
            if count == target_blocks:
                break
        train, test = dev_common & ~hidden, dev_common & hidden
        for station in STATIONS:
            for mode in MODES:
                a, b = fit_and_score(y, predictors[station], season, train, test, station, mode, f'block_seed_{seed}')
                summaries.extend(a)
                predictions.extend(b)
    # Later-year results are computed once with lag/fits learned only from 2024-25.
    for station in STATIONS:
        for mode in MODES:
            a, b = fit_and_score(y, predictors[station], season, dev_common, later_common, station, mode, 'holdout_2026')
            summaries.extend(a)
            predictions.extend(b)
    scores = pd.DataFrame(summaries)
    scores.to_csv(OUT / 'seasonal_scores.csv', index=False, na_rep='NaN')
    pd.DataFrame(predictions).to_csv(OUT / 'heldout_predictions.csv', index=False)
    pd.DataFrame(blocks).to_csv(OUT / 'validation_blocks.csv', index=False)
    block_scores = scores[scores['split'].str.startswith('block_seed_') & scores['status'].eq('evaluated')]
    repeated = block_scores.groupby(['station', 'mode', 'season']).agg(
        evaluated_splits=('nse', 'count'), median_nse=('nse', 'median'),
        min_nse=('nse', 'min'), max_nse=('nse', 'max'),
        median_kge=('kge', 'median'), median_pbias_pct=('pbias_pct', 'median'),
        median_rmse_cumecs=('rmse_cumecs', 'median'), median_peak_mape_pct=('peak_mape_pct', 'median'),
        nse_pass_splits=('passes_nse_08', 'sum')).reset_index()
    repeated.to_csv(OUT / 'blocked_validation_summary.csv', index=False)
    # Availability benefit only: count truly missing combined Marala observations.
    original = pd.read_csv(HERE.parent / 'marala_observed/data/daily_observed_priority.csv', parse_dates=['date']).set_index('date')
    original_y = original['observed_discharge_m3_s']
    availability = []
    for station in STATIONS:
        nearby = pd.read_csv(DATA / station / 'nearby.csv', parse_dates=['date']).set_index('date')['q_cumecs']
        for mode in MODES:
            row = scores[(scores['station'] == station) & (scores['mode'] == mode) & scores['split'].eq('holdout_2026')].iloc[0]
            lag = int(row['lag'])
            x = nearby.reindex(original.index - pd.Timedelta(days=lag)).set_axis(original.index)
            can_fill = original_y.isna() & x.gt(0)
            availability.append(dict(station=station, mode=mode, selected_lag=lag,
                                     combined_missing_days=int(original_y.isna().sum()),
                                     missing_days_with_predictor_before_accuracy_gate=int(can_fill.sum()),
                                     candidate_dates=';'.join(d.date().isoformat() for d in original.index[can_fill])))
    pd.DataFrame(availability).to_csv(OUT / 'missing_day_predictor_availability.csv', index=False)
    metadata = dict(target='FFD observed Marala inflow at confirmed 06:00 PKT; no interpolated/model targets',
                    eligible_marala_dates=int(y.notna().sum()), common_all_station_all_lag_dates=int(common.sum()),
                    common_development_dates=int(dev_common.sum()), common_2026_dates=int(later_common.sum()),
                    seasonal_common_dates={name: int((common & season.eq(name)).sum()) for name in SEASONS},
                    random_block_seeds=list(range(10)), block_length_days=30,
                    blocks_per_seed=target_blocks, actual_hidden_days_per_seed=30 * target_blocks,
                    development_observed_days=int((y.notna() & dev).sum()),
                    lag_convention='Q_Marala(t) from Q_nearby(t-lag). Negative uses future nearby observations, reconstruction only.',
                    primary_selection='Use 2024-2025 blocked validation; 2026 is a later-year generalization check. No tuning after 2026 scores.',
                    metrics='NSE, original KGE, positive-overprediction PBIAS, RMSE/MAE in m3/s; peak MAPE above training-season Q95.',
                    no_discharge_values_changed=True)
    (OUT / 'evaluation_metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    print(json.dumps(metadata, indent=2))
    print('\nBLOCKED VALIDATION\n', repeated.to_string(index=False))
    print('\n2026 HOLDOUT\n', scores[scores['split'].eq('holdout_2026')][['station', 'mode', 'season', 'lag', 'n', 'nse', 'kge', 'pbias_pct', 'rmse_cumecs', 'peak_mape_pct', 'peak_n', 'passes_nse_08']].to_string(index=False))
    print('\nAVAILABILITY\n', pd.DataFrame(availability).to_string(index=False))


if __name__ == '__main__':
    main()
