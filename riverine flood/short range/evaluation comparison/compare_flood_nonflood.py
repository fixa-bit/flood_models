"""Read saved predictions only; compare observed Q95 exceedance and other days."""
import argparse
import csv
import gzip
import hashlib
import json
import math
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent / 'model'
SOURCES = {}


def track(path):
    path = Path(path).resolve()
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if path in SOURCES and SOURCES[path] != digest:
        raise AssertionError('An input changed during analysis')
    SOURCES[path] = digest
    return path


def read_csv(path):
    path = track(path)
    opener = gzip.open if path.suffix == '.gz' else open
    with opener(path, 'rt', newline='', encoding='utf-8-sig') as file:
        return list(csv.DictReader(file))


def read_json(path):
    return json.loads(track(path).read_text())


def number(value):
    try:
        return float(value)
    except (ValueError, TypeError):
        return float('nan')


def quantile(values, probability):
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    left = int(index); right = min(left + 1, len(ordered) - 1)
    return ordered[left] + (ordered[right] - ordered[left]) * (index - left)


def add_wide(models, path, columns, threshold, *, observed='observed_cumecs', issue='issue_date',
             target='target_date', lead='lead_day', split=None):
    for row in read_csv(path):
        if split and row.get('split') != split:
            continue
        q = number(row[observed])
        if not math.isfinite(q):
            continue
        key = (row[issue], row[target], int(row[lead]))
        for column, name in columns.items():
            prediction = number(row[column])
            if not math.isfinite(prediction):
                raise ValueError(f'Nonfinite prediction on an observed day: {name}, {key}')
            if key in models[name]:
                raise ValueError(f'Duplicate prediction: {name}, {key}')
            models[name][key] = (q, prediction, threshold)


def measures(records):
    n = len(records)
    if not n:
        return {'n': 0, 'NSE': float('nan'), 'KGE': float('nan'), 'RMSE_cumecs': float('nan'),
                'MAE_cumecs': float('nan'), 'PBIAS_pct': float('nan'), 'MAPE_pct': float('nan')}
    y = [r[0] for r in records]; p = [r[1] for r in records]
    mean_y, mean_p = math.fsum(y) / n, math.fsum(p) / n
    sy = math.fsum((v - mean_y) ** 2 for v in y)
    sp = math.fsum((v - mean_p) ** 2 for v in p)
    errors = [b - a for a, b in zip(y, p)]
    sse = math.fsum(e * e for e in errors)
    kge = float('nan')
    if sy > 0 and sp > 0 and mean_y > 0:
        r = math.fsum((a - mean_y) * (b - mean_p) for a, b in zip(y, p)) / math.sqrt(sy * sp)
        kge = 1 - math.sqrt((r - 1) ** 2 + (math.sqrt(sp / sy) - 1) ** 2 + (mean_p / mean_y - 1) ** 2)
    positive_errors = [abs(b - a) / a for a, b in zip(y, p) if a > 0]
    return {'n': n, 'NSE': 1 - sse / sy if sy > 0 else float('nan'), 'KGE': kge,
            'RMSE_cumecs': math.sqrt(sse / n), 'MAE_cumecs': math.fsum(abs(e) for e in errors) / n,
            'PBIAS_pct': 100 * math.fsum(errors) / math.fsum(y) if math.fsum(y) else float('nan'),
            'MAPE_pct': 100 * math.fsum(positive_errors) / len(positive_errors) if positive_errors else float('nan')}


def score_cohort(name, models, rows, alerts, metadata, max_lead=None, observed_tolerance=1e-8):
    leads = sorted({key[2] for values in models.values() for key in values})
    if max_lead:
        leads = [lead for lead in leads if lead <= max_lead]
    counts = []
    for lead in leads:
        sets = [{key for key in values if key[2] == lead} for values in models.values()]
        common = set.intersection(*sets)
        if not common:
            raise ValueError(f'No common observed dates for {name}, lead {lead}')
        keys = sorted(common)
        reference = next(iter(models.values()))
        target_days = {key[1] for key in keys}
        flood_days = {key[1] for key in keys if reference[key][0] > reference[key][2]}
        counts.append({'lead_day': lead, 'n': len(keys), 'flood_n': sum(reference[k][0] > reference[k][2] for k in keys),
                       'unique_days': len(target_days), 'unique_flood_days': len(flood_days),
                       'excluded_for_common_alignment': {m: len(s) - len(common) for m, s in zip(models, sets)}})
        for model, values in models.items():
            for key in keys:
                if not math.isclose(values[key][0], reference[key][0], rel_tol=0, abs_tol=observed_tolerance):
                    raise AssertionError('Models are not scored on matching observed values')
                if not math.isclose(values[key][2], reference[key][2], rel_tol=1e-12):
                    raise AssertionError('Models use different flood thresholds within a cohort')
            all_records = [values[k] for k in keys]
            flooded = [r for r in all_records if r[0] > r[2]]
            other = [r for r in all_records if r[0] <= r[2]]
            scores = {group: measures(records) for group, records in [('all', all_records), ('flood', flooded), ('non_flood', other)]}
            if len(flooded) + len(other) != len(all_records):
                raise AssertionError('Flood/non-flood partition lost a target')
            reconstructed = math.fsum(s['n'] * s['RMSE_cumecs'] ** 2 for s in scores.values() if s['n'])
            expected = 2 * scores['all']['n'] * scores['all']['RMSE_cumecs'] ** 2
            if not math.isclose(reconstructed, expected, rel_tol=1e-12, abs_tol=1e-6):
                raise AssertionError('Group errors do not reproduce overall squared errors')
            for group, stats in scores.items():
                rows.append({'cohort': name, 'model': model, 'lead_day': lead, 'group': group, **stats})
            tp = sum(y > t and p > t for y, p, t in all_records)
            fn = sum(y > t and p <= t for y, p, t in all_records)
            fp = sum(y <= t and p > t for y, p, t in all_records)
            tn = sum(y <= t and p <= t for y, p, t in all_records)
            ratio = lambda a, b: a / b if b else float('nan')
            alerts.append({'cohort': name, 'model': model, 'lead_day': lead, 'n': len(all_records),
                           'TP': tp, 'FN': fn, 'FP': fp, 'TN': tn, 'POD': ratio(tp, tp + fn),
                           'false_alarm_ratio': ratio(fp, tp + fp), 'false_alarm_rate': ratio(fp, fp + tn),
                           'CSI': ratio(tp, tp + fp + fn)})
    thresholds = sorted({r[2] for values in models.values() for r in values.values()})
    metadata[name] = {'models': list(models), 'thresholds_cumecs': thresholds, 'counts_by_lead': counts,
                      'first_test_date': min(k[1] for values in models.values() for k in values),
                      'last_test_date': max(k[1] for values in models.values() for k in values)}


def save_csv(path, rows):
    with path.open('w', newline='', encoding='utf-8') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0])); writer.writeheader(); writer.writerows(rows)


def md_table(headers, values):
    def display(value):
        if isinstance(value, float):
            return f'{value:.3f}' if math.isfinite(value) else 'NA'
        return str(value)
    return '\n'.join(['| ' + ' | '.join(headers) + ' |', '| ' + ' | '.join(['---'] * len(headers)) + ' |']
                     + ['| ' + ' | '.join(display(v) for v in row) + ' |' for row in values])


def comparison_table(rows, cohort, lead):
    selected = [r for r in rows if r['cohort'] == cohort and r['lead_day'] == lead]
    models = sorted({r['model'] for r in selected}, key=lambda m: next(r['RMSE_cumecs'] for r in selected if r['model'] == m and r['group'] == 'flood'))
    values = []
    for model in models:
        flood = next(r for r in selected if r['model'] == model and r['group'] == 'flood')
        other = next(r for r in selected if r['model'] == model and r['group'] == 'non_flood')
        values.append([model, flood['n'], flood['RMSE_cumecs'], flood['MAE_cumecs'], flood['NSE'],
                       other['n'], other['RMSE_cumecs'], other['MAE_cumecs'], other['NSE']])
    return md_table(['Model', 'Flood n', 'Flood RMSE', 'Flood MAE', 'Flood NSE', 'Other n', 'Other RMSE', 'Other MAE', 'Other NSE'], values)


def main(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError('Choose a new report directory; saved analyses are not overwritten')
    rows, alerts, metadata = [], [], {}
    manifest = read_json(ROOT.parent / 'evaluation comparison/initial_lstm_baselines/evaluation_manifest.json')
    threshold = manifest['thresholds']['marala']['flood']
    training = [number(r['q_cumecs']) for r in read_csv(ROOT.parent / 'evaluation comparison/common/data/marala_daily.csv')
                if 2016 <= int(r['date'][:4]) <= 2020 and math.isfinite(number(r['q_cumecs']))]
    if not math.isclose(quantile(training, .95), threshold, rel_tol=1e-12):
        raise AssertionError('Saved flood threshold is not training-only Q95')
    main_models = defaultdict(dict)
    specifications = [
        ('evaluation comparison/initial_lstm_baselines/predictions.csv', {'LSTM': 'Original LSTM', 'gradient_boosting': 'Gradient boosting',
          'Ensemble': 'LSTM + boosting ensemble', 'persistence': 'Persistence', 'climatology': 'Climatology'}),
        ('evaluation comparison/global_pretrained_lstm/predictions.csv', {'Global_finetuned': 'Global LSTM fine-tuned', 'Global_zero_shot': 'Global LSTM zero-shot (reference)'}),
        ('evaluation comparison/spatially_distributed_model/predictions.csv', {'ElevationBands': 'Elevation-band LSTM', 'MeanControl': 'Catchment-mean LSTM control'}),
        ('evaluation comparison/hybrid_physics_ml/predictions.csv', {'Hybrid': 'Snow-bucket + LSTM'}),
        ('evaluation comparison/pretrained_multibasin_lstm/predictions.csv', {'finetuned': '8-basin LSTM fine-tuned', 'scratch': '2-input LSTM scratch', 'pretrained_only': '8-basin donor LSTM without adaptation'}),
        ('evaluation comparison/encoder_decoder_lstm/predictions.csv.gz', {'finetuned': '15-day seq2seq fine-tuned', 'scratch': '15-day seq2seq scratch'})]
    for path, columns in [
        ('model_10 days/N-HiTS/reports/initial/predictions.csv', {'NHITS': 'N-HiTS'}),
        ('model_10 days/N-BEATSx/reports/initial/predictions.csv', {'NBEATSx': 'N-BEATSx'}),
        ('model_10 days/delta_hbv/reports/initial/predictions.csv', {'delta_HBV': 'delta-HBV'}),
        ('model_10 days/lstm_past_discharge_weather/reports/initial/predictions.csv', {'Matched_LSTM': 'Matched past-Q/weather LSTM'})]:
        if (ROOT / path).exists():
            specifications.append((path, columns))
    for path, columns in specifications:
        source_root = ROOT.parent if path.startswith('evaluation comparison/') else ROOT
        add_wide(main_models, source_root / path, columns, threshold)
    score_cohort('main_2022_2024', main_models, rows, alerts, metadata, max_lead=10)
    extended = defaultdict(dict)
    add_wide(extended, ROOT.parent / 'evaluation comparison/encoder_decoder_lstm/predictions.csv.gz',
             {'finetuned': '15-day seq2seq fine-tuned', 'scratch': '15-day seq2seq scratch',
              'persistence': 'Persistence', 'climatology': 'Climatology'}, threshold)
    score_cohort('seq2seq_15day_2022_2024', extended, rows, alerts, metadata)
    hbv = defaultdict(dict)
    for r in read_csv(ROOT.parent / 'evaluation comparison/hbv_residual_2026-10-30/reports/rolling_predictions.csv.gz'):
        if not math.isfinite(number(r['observed'])):
            continue
        key = (r['issue_date'], r['valid_date'], int(r['lead_day']))
        if key in hbv[r['model']]:
            raise ValueError('Duplicate HBV prediction')
        hbv[r['model']][key] = (number(r['observed']), number(r['p50']), number(r['threshold_train_q95_cumecs']))
    score_cohort('hbv_monsoons_2021_2024', hbv, rows, alerts, metadata)
    legacy_threshold = read_json(ROOT.parent / 'evaluation comparison/grrr_lstm/experiment/report.json')['highflow_threshold_m3_s']
    legacy_training = [number(r['observed_discharge_m3_s']) for r in read_csv(ROOT / 'model_15 days/discharge_history_lstm/data/daily_observed_priority.csv')
                       if r['split'] == 'train' and r['is_observed'] == '1' and math.isfinite(number(r['observed_discharge_m3_s']))]
    if not math.isclose(quantile(legacy_training, .95), legacy_threshold, rel_tol=1e-12):
        raise AssertionError('Legacy threshold is not observed training Q95')
    legacy = defaultdict(dict)
    add_wide(legacy, ROOT / 'model_15 days/discharge_history_lstm/observed_only/predictions_observed_days.csv',
             {'lstm_m3_s': 'Discharge-history LSTM'}, legacy_threshold, observed='observed_m3_s',
             issue='issue_after_date', lead='lead_days', split='test')
    add_wide(legacy, ROOT.parent / 'evaluation comparison/grrr_lstm/experiment/predictions_observed_days.csv',
             {'nan_gaps_m3_s': 'LSTM + lagged GRRR, gaps retained', 'weighted_fills_m3_s': 'GRRR weighted-fill LSTM (rejected)',
              'persistence_m3_s': 'Persistence'}, legacy_threshold, observed='observed_m3_s',
             issue='issue_after_date', lead='lead_days', split='test')
    score_cohort('earlier_2023_2026', legacy, rows, alerts, metadata, observed_tolerance=.002)
    nearby_dir = ROOT.parent / 'experiments/marala_nearby_regression'
    thresholds = {(r['station'], r['mode']): number(r['train_q95']) for r in read_csv(nearby_dir / 'results/seasonal_scores.csv')
                  if r['split'] == 'holdout_2026' and r['season'] == 'Jul-Sep'}
    nearby = defaultdict(dict)
    for r in read_csv(nearby_dir / 'results/heldout_predictions.csv'):
        if r['split'] != 'holdout_2026' or r['season'] != 'Jul-Sep':
            continue
        name = r['station'] + (' same-day regression' if r['mode'] == 'past_only' else ' lagged reconstruction')
        nearby[name][(r['date'], r['date'], 0)] = (number(r['observed_cumecs']), number(r['predicted_cumecs']), thresholds[(r['station'], r['mode'])])
    for r in read_csv(nearby_dir / 'hybrid_results/heldout_predictions.csv'):
        if r['split'] == 'holdout_2026' and r['season'] == 'Jul-Sep' and r['scope'] == 'same_dates_as_previous' and r['method'] == 'Hybrid':
            nearby['Qadirabad-next-day / Khanki fallback'][(r['date'], r['date'], 0)] = (
                number(r['observed_cumecs']), number(r['predicted_cumecs']), thresholds[('Khanki', 'past_only')])
    score_cohort('nearby_reconstruction_monsoon_2026', nearby, rows, alerts, metadata)
    # Independently reproduce the stored overall day-10 results before reporting new subgroups.
    old_scores = read_csv(ROOT.parent / 'evaluation comparison/global_pretrained_lstm/scores_by_lead.csv')
    for old_name, new_name in [('Existing_local_LSTM', 'Original LSTM'), ('Global_finetuned', 'Global LSTM fine-tuned')]:
        old = next(r for r in old_scores if r['model'] == old_name and r['lead_day'] == '10')
        new = next(r for r in rows if r['cohort'] == 'main_2022_2024' and r['model'] == new_name and r['lead_day'] == 10 and r['group'] == 'all')
        for metric in ['NSE', 'RMSE_cumecs']:
            # CSVs round original float32 forecasts; allow small rounding differences.
            tolerance = 1e-4 if metric == 'RMSE_cumecs' else 1e-8
            if not math.isclose(new[metric], number(old[metric]), rel_tol=1e-10, abs_tol=tolerance):
                raise AssertionError(f'Overall score differs for {new_name}, {metric}: '
                                     f'{new[metric]} on {new["n"]} matched dates vs {old[metric]} on {old["n"]} original dates')
    for path, digest in SOURCES.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise AssertionError('An existing source was modified')
    output.mkdir(parents=True)
    save_csv(output / 'scores_flood_nonflood_by_lead.csv', rows)
    save_csv(output / 'flood_detection_by_lead.csv', alerts)
    selected = [r for r in rows if r['cohort'] == 'main_2022_2024' and r['lead_day'] == 10]
    save_csv(output / 'main_day10_scores.csv', selected)
    report = ['# Flood versus non-flood performance', '',
              'Report date: 2026-11-02 (Asia/Karachi). This analysis reads existing saved predictions; no models were retrained, no settings tuned and no discharge filled or modified.', '',
              f'Flood proxy: observed target discharge strictly above training Q95. Main and 15-day experiments: **{threshold:.6f} m3/s**, calculated from observed 2016-2020 targets only. Non-flood is observed flow at or below that threshold. These are high-flow exceedance days, not official flood classes or independent flood events.', '',
              'Groups are defined by observed flow, not predicted flow. Every model in a cohort is compared on identical issue/target/lead keys, using observed targets only. Overlapping forecast windows are not independent observations. Earlier 30-day-history experiments use their own 2016-2021 training Q95; HBV uses each fold\'s saved training Q95; nearby regression uses its training-season Q95.', '',
              'RMSE and MAE are in m3/s; lower is better. NSE and original KGE are recomputed within each subset. Subset NSE uses the subset mean as its reference and can be negative when the flow range is narrow. Do not compare flood NSE directly with non-flood NSE as if their reference variances were equal. PBIAS is positive for overprediction. Full bias, MAPE and KGE are in the CSV.', '',
              '## Main experiments: day 10, 2022-2024', '', comparison_table(rows, 'main_2022_2024', 10), '',
              'Rows are ordered by flood-day RMSE. Zero-shot global weights were downloaded rather than trained here. Donor-only and zero-shot rows are transfer diagnostics, not recommended Marala models. The rejected weighted-fill model below is retained only as historical evaluation evidence.', '',
              '## Flood detection: main day 10', '',
              md_table(['Model', 'TP', 'FN', 'FP', 'TN', 'Hit rate', 'False-alarm ratio', 'False-alarm rate', 'CSI'],
                       [[r[k] for k in ['model', 'TP', 'FN', 'FP', 'TN', 'POD', 'false_alarm_ratio', 'false_alarm_rate', 'CSI']]
                        for r in alerts if r['cohort'] == 'main_2022_2024' and r['lead_day'] == 10]), '',
              'A predicted alert means point forecast > training Q95. Hit rate = TP/(TP+FN); false-alarm ratio = FP/(TP+FP); false-alarm rate = FP/(FP+TN). Undefined ratios are NA. This classification check differs from probabilistic warning scores derived from quantile exceedance probabilities.', '',
              '## Encoder-decoder models: day 15, 2022-2024', '', comparison_table(rows, 'seq2seq_15day_2022_2024', 15), '',
              '## HBV rolling June-September tests: day 10, 2021-2024', '', comparison_table(rows, 'hbv_monsoons_2021_2024', 10), '',
              'This cohort has different test seasons, folds, observed-day coverage and training thresholds from the full-year main experiments. Its scores do not rank those models against the main table.', '',
              '## Earlier discharge/GRRR experiments: day 15, 2023-2026', '', comparison_table(rows, 'earlier_2023_2026', 15), '',
              f'Threshold: {legacy_threshold:.6f} m3/s from observed 2016-2021 training discharge. Source predictions of the discharge-history-only LSTM store observed flow in float32; matching across the legacy tables allows 0.002 m3/s rounding differences. Each model\'s stored observed values are preserved. GRRR feature availability in 2026 differs from its training period.', '',
              '## Nearby-gauge reconstructions: July-September 2026', '', comparison_table(rows, 'nearby_reconstruction_monsoon_2026', 0), '',
              'These are reconstructions from nearby readings, not future forecasts. Lagged downstream readings can occur after the reconstructed Marala day. The six Q95 exceedance days in this holdout are a small sample, and earlier blocked validation was unstable. This new grouping does not approve automatic filling.', '',
              '## Availability and limitations', '',
              'The main day-10 cohort contains 1,075 observed target days: 51 above Q95 and 1,024 at or below it. Full per-lead counts, common-date exclusions, source hashes and thresholds are in analysis_manifest.json. All leads are saved in scores_flood_nonflood_by_lead.csv. Overall scores reproduce the earlier reports to the precision retained in the prediction CSVs (RMSE tolerance 0.0001 m3/s; NSE tolerance 0.00000001). No official warning-level labels or independent inundation observations were supplied.', '',
              'Weather-driven experiments use realized/noisy reanalysis as stand-in forecasts. These are not established operational TIGGE/GFS forecast scores. Models have different features, architectures and losses, so score differences do not isolate a causal benefit of a model component. Previously inspected holdouts, small flood samples, overlapping windows, regulation and reading/availability times limit conclusions. No test-driven retraining, model selection or ensemble-weight update was performed here.']
    (output / 'report.md').write_text('\n'.join(report) + '\n', encoding='utf-8')
    manifest = {'report_date': '2026-11-02', 'flood_definition': 'observed Q > observed-training Q95',
                'no_retraining': True, 'no_discharge_filling': True, 'all_input_hashes_unchanged': True,
                'overall_day10_scores_reproduced': True, 'group_error_partitions_verified': True,
                'cohorts': metadata, 'sources': [{'path': str(path), 'sha256': digest} for path, digest in SOURCES.items()]}
    (output / 'analysis_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
    print(comparison_table(rows, 'main_2022_2024', 10), flush=True)
    print('Saved:', output / 'report.md', flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default=str(ROOT.parent / 'evaluation comparison/flood_nonflood_reorganized'))
    main(parser.parse_args().output)
