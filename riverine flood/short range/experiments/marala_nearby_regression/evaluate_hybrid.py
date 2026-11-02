"""Evaluate Qadirabad(t+1), otherwise Khanki(t), without changing observations.

Reuse previously saved seasonal fits and validation partitions. This is a
post-hoc comparison on existing holdouts, not a new blind validation dataset.
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

from evaluate import DATA, HERE, SEASONS, measure

OUT = HERE / 'hybrid_results'
MODELS = {'Khanki': 'past_only', 'Qadirabad': 'reconstruction'}


def main():
    OUT.mkdir(exist_ok=True)
    previous = HERE / 'results'
    scores = pd.read_csv(previous / 'seasonal_scores.csv')
    original_predictions = pd.read_csv(previous / 'heldout_predictions.csv', parse_dates=['date'])
    y = pd.read_csv(previous / 'marala.csv', parse_dates=['date']).set_index('date')['q_cumecs']
    dates = y.index
    season = pd.Series(np.select([dates.month.isin([10, 11, 12, 1, 2, 3]), dates.month.isin([4, 5, 6])],
                                 ['Oct-Mar', 'Apr-Jun'], default='Jul-Sep'), index=dates)
    khanki = pd.read_csv(DATA / 'Khanki/nearby.csv', parse_dates=['date']).set_index('date')['q_cumecs']
    qadirabad = pd.read_csv(DATA / 'Qadirabad/nearby.csv', parse_dates=['date']).set_index('date')['q_cumecs']
    x = {'Khanki': khanki.reindex(dates),
         'Qadirabad': qadirabad.reindex(dates + pd.Timedelta(days=1)).set_axis(dates)}
    blocks = pd.read_csv(previous / 'validation_blocks.csv', parse_dates=['start', 'end'])
    summaries, predictions = [], []
    split_names = list(scores['split'].drop_duplicates())
    for split in split_names:
        test = pd.Series(False, index=dates)
        if split == 'holdout_2026':
            test.loc[dates.year == 2026] = True
        else:
            seed = int(split.rsplit('_', 1)[1])
            for row in blocks[blocks['seed'].eq(seed)].itertuples():
                test |= pd.Series(dates.to_series().between(row.start, row.end).to_numpy(), index=dates)
        test &= y.gt(0)
        for name in SEASONS:
            fitted, estimates = {}, {}
            for station, mode in MODELS.items():
                row = scores[(scores['station'] == station) & (scores['mode'] == mode)
                             & scores['split'].eq(split) & scores['season'].eq(name)].iloc[0]
                fitted[station] = row
                estimate = pd.Series(np.nan, index=dates)
                available = test & season.eq(name) & x[station].gt(0)
                if row['status'] == 'evaluated':
                    assert int(row['lag']) == (0 if station == 'Khanki' else -1)
                    estimate.loc[available] = np.exp(row['log_intercept'] + row['log_slope'] * np.log(x[station][available]))
                estimates[station] = estimate
            hybrid = estimates['Qadirabad'].combine_first(estimates['Khanki'])
            route = pd.Series('', index=dates)
            route.loc[estimates['Qadirabad'].notna()] = 'Qadirabad_next_day'
            route.loc[estimates['Qadirabad'].isna() & estimates['Khanki'].notna()] = 'Khanki_same_day'
            # Compare with previous evaluation on its exact common target dates.
            old = original_predictions[(original_predictions['station'] == 'Khanki')
                                       & original_predictions['mode'].eq('past_only')
                                       & original_predictions['split'].eq(split)
                                       & original_predictions['season'].eq(name)]
            matched = pd.Series(dates.isin(old['date']), index=dates)
            estimates['Hybrid'] = hybrid
            for scope in ('same_dates_as_previous', 'all_available_heldout_dates'):
                for method, prediction in estimates.items():
                    valid = test & season.eq(name) & prediction.notna()
                    if scope == 'same_dates_as_previous':
                        valid &= matched
                    threshold = fitted['Khanki']['train_q95'] if method == 'Hybrid' else fitted[method]['train_q95']
                    metric = measure(y[valid], prediction[valid], threshold)
                    if not valid.any():
                        continue
                    summaries.append(dict(scope=scope, split=split, season=name, method=method, **metric,
                                          qadirabad_route_days=int((valid & route.eq('Qadirabad_next_day')).sum()) if method == 'Hybrid' else 0,
                                          khanki_fallback_days=int((valid & route.eq('Khanki_same_day')).sum()) if method == 'Hybrid' else 0))
                    for day in dates[valid]:
                        predictions.append(dict(scope=scope, split=split, season=name, method=method,
                                                date=day.date().isoformat(), observed_cumecs=y[day],
                                                predicted_cumecs=prediction[day],
                                                route=route[day] if method == 'Hybrid' else method))
    summary = pd.DataFrame(summaries)
    prediction_table = pd.DataFrame(predictions)
    # The rule must equal Qadirabad whenever that prediction is available.
    wide = prediction_table.pivot(index=['scope', 'split', 'season', 'date'], columns='method', values='predicted_cumecs')
    has_qadirabad = wide['Qadirabad'].notna()
    np.testing.assert_allclose(wide.loc[has_qadirabad, 'Hybrid'], wide.loc[has_qadirabad, 'Qadirabad'])
    fallback = wide['Qadirabad'].isna() & wide['Khanki'].notna()
    np.testing.assert_allclose(wide.loc[fallback, 'Hybrid'], wide.loc[fallback, 'Khanki'])
    summary.to_csv(OUT / 'seasonal_scores.csv', index=False, na_rep='NaN')
    prediction_table.to_csv(OUT / 'heldout_predictions.csv', index=False)
    observed = pd.read_csv(HERE.parent / 'marala_observed/data/daily_observed_priority.csv', parse_dates=['date']).set_index('date')['observed_discharge_m3_s']
    q_available = qadirabad.reindex(observed.index + pd.Timedelta(days=1)).set_axis(observed.index).gt(0)
    k_available = khanki.reindex(observed.index).gt(0)
    gaps = observed.isna()
    candidate_days = pd.DataFrame({'date': observed.index[gaps],
                                   'qadirabad_next_day_available': q_available[gaps].to_numpy(),
                                   'khanki_same_day_available': k_available[gaps].to_numpy()})
    candidate_days.to_csv(OUT / 'missing_day_predictor_availability.csv', index=False)
    metadata = dict(rule='Observed Marala always wins. Otherwise Qadirabad(t+1), otherwise Khanki(t), otherwise NaN.',
                    rule_evaluation='Scored ungated routing to test whether this proposal improves errors; no fills applied.',
                    original_missing_marala_dates=int(gaps.sum()),
                    gaps_with_qadirabad_predictor=int((gaps & q_available).sum()),
                    gaps_only_khanki_fallback_can_cover=int((gaps & ~q_available & k_available).sum()),
                    no_discharge_data_modified=True,
                    limitation='Post-hoc comparison on previously inspected holdouts. A separate untouched period is needed for an independent confirmation.')
    (OUT / 'metadata.json').write_text(json.dumps(metadata, indent=2) + '\n')
    monsoon = summary[summary['split'].eq('holdout_2026') & summary['season'].eq('Jul-Sep')]
    print(monsoon.to_string(index=False))
    print('\nAll-season 2026 hybrid routing:\n', summary[summary['split'].eq('holdout_2026') & summary['method'].eq('Hybrid')].to_string(index=False))
    repeated = summary[summary['split'].str.startswith('block_seed')].groupby(['scope', 'season', 'method'])['nse'].median()
    repeated.rename('median_nse').to_csv(OUT / 'blocked_validation_median_nse.csv')
    print('\nRepeated median NSE:\n', repeated.to_string())
    print(json.dumps(metadata, indent=2))


if __name__ == '__main__':
    main()
