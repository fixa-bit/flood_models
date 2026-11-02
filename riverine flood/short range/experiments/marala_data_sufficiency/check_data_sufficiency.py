"""Read-only 10-day Marala sufficiency audit. Dependencies: pandas numpy matplotlib.

Run from any directory. Optionally pass --forecasts FILE.csv with issue_date,
lead_days and forecast variables (or variable/value columns). No data are filled.
"""
import argparse
import calendar
import hashlib
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.colors import ListedColormap
from matplotlib.patches import Patch
import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PROJECT = HERE.parents[3]
MODEL = PROJECT / 'riverine flood/short range/dataset/chenab_marala'
RAW, PROCESSED = MODEL / 'raw/marala', MODEL / 'processed/marala'
READ_HASHES = {}


def read(path, **kwargs):
    if path not in READ_HASHES:
        READ_HASHES[path] = hashlib.sha256(path.read_bytes()).hexdigest()
    return pd.read_csv(path, **kwargs)


def dated(path):
    frame = read(path, parse_dates=['date']).set_index('date').sort_index()
    if frame.index.has_duplicates or not frame.index.equals(frame.index.normalize()):
        raise ValueError(f'Expected unique daily dates: {path}')
    return frame


def markdown(frame):
    def cell(x):
        if pd.isna(x):
            return 'not available'
        return f'{x:.3f}' if isinstance(x, (float, np.floating)) else str(x)
    return '\n'.join(['| ' + ' | '.join(map(str, frame.columns)) + ' |',
                      '| ' + ' | '.join(['---'] * len(frame.columns)) + ' |']
                     + ['| ' + ' | '.join(cell(x) for x in row) + ' |' for row in frame.itertuples(index=False, name=None)])


def runs(mask):
    return mask[mask].groupby(mask.ne(mask.shift()).cumsum()).size()


def higher(value, good, warn):
    return 'PASS' if value >= good else 'WARN' if value >= warn else 'FAIL'


def observed_discharge():
    pieces, paths, excluded = [], [], []
    for source, filenames in [('WAPDA', ['marala_wapda_daily_inflow.csv']),
                              ('FFD', [f'marala_ffd_{y}_bulletin_discharge.csv' for y in (2024, 2025, 2026)])]:
        for filename in filenames:
            path = PROCESSED / 'discharge' / filename
            paths.append(dict(input='Observed discharge: ' + source, path=str(path), status='found' if path.exists() else 'MISSING'))
            if not path.exists():
                continue
            frame = read(path, parse_dates=['date'])
            column = 'marala_inflow_cusecs' if source == 'WAPDA' else 'marala_inflow_1000_cusecs'
            q = pd.to_numeric(frame[column], errors='raise') * (0.028316846592 if source == 'WAPDA' else 28.316846592)
            eligible = np.isfinite(q) & q.gt(0)
            if 'date_status' in frame:
                eligible &= frame['date_status'].eq('matches_archive')
            if source == 'FFD':
                eligible &= frame['observation_time'].eq('06:00 PKT')
            excluded.append(f'{filename}: {int((~eligible).sum())} nonpositive, date-conflict or unconfirmed-time rows excluded.')
            part = pd.DataFrame({'date': frame.loc[eligible, 'date'], 'q': q[eligible], 'source': source})
            pieces.append(part)
    if not pieces:
        raise ValueError('No observed-discharge files found')
    frame = pd.concat(pieces).sort_values(['date', 'source'])
    # Reject within-source conflicts; WAPDA has priority over FFD cross-source differences.
    unique = frame.groupby(['date', 'source'])['q'].nunique().eq(1)
    frame = frame.set_index(['date', 'source']).loc[unique].reset_index().drop_duplicates(['date', 'source'])
    wp = frame[frame['source'].eq('WAPDA')].set_index('date')['q']
    ffd = frame[frame['source'].eq('FFD')].set_index('date')['q']
    combined = wp.combine_first(ffd).sort_index()
    dates = pd.date_range(combined.index.min(), combined.index.max(), freq='D')
    counts = {'WAPDA': len(wp), 'FFD additional dates': int((~ffd.index.isin(wp.index)).sum())}
    return combined.reindex(dates), paths, excluded, counts


def inputs(period):
    # Core is one preferred rainfall product plus temperature, snow, dewpoint, solar and PET.
    specs = [
        (PROCESSED / 'rainfall/chirps_v3_primary/marala_chirps_v3_final_rnl_daily_1990_2026.csv', {'precipitation_mm': 'rain_chirps_v3_mm'}, True),
        (RAW / 'temperature/google_earth_engine/marala_daily_temperature_1980_2024.csv', {'era5land_temperature_2m_c': 'temperature_c'}, True),
        (RAW / 'marala_daily_snow_1980_2024.csv', {c: c for c in ('swe_mm', 'snow_depth_m', 'snowmelt_mm')}, True),
        (RAW / 'marala_daily_dewpoint_ssrd_1980_2024.csv', {c: c for c in ('dewpoint_c', 'ssrd_wm2')}, True),
        (RAW / 'potential_evaporation_sum/marala_daily_pet_1980_2024.csv', {'pet_mm': 'pet_mm'}, True),
        (RAW / 'rainfall/google_earth_engine/marala_daily_precipitation_1980_2024.csv', {c: c for c in ('era5land_mm', 'chirps_mm', 'persiann_mm', 'imerg_mm')}, False)]
    columns, core, rows, paths = {}, [], [], []
    def add(frame, rename, required):
        for old, name in rename.items():
            series = pd.to_numeric(frame[old], errors='raise') if old in frame else pd.Series(dtype=float)
            columns[name] = series
            if required:
                core.append(name)
            finite = series[np.isfinite(series)]
            aligned = series.reindex(period)
            missing = ~np.isfinite(aligned)
            rows.append(dict(column=name, role='core' if required else 'optional/alternative',
                             first_date=finite.index.min().date().isoformat() if len(finite) else None,
                             last_date=finite.index.max().date().isoformat() if len(finite) else None,
                             missing_days=int(missing.sum()), missing_pct=100 * missing.mean()))
    for path, rename, required in specs:
        paths.append(dict(input='Dynamic inputs', path=str(path), status='found' if path.exists() else 'MISSING'))
        add(dated(path) if path.exists() else pd.DataFrame(), rename, required)
    modis = sorted((RAW / 'NDSI_Snow_Cover').glob('[12][0-9][0-9][0-9].csv'))
    paths.append(dict(input='Optional MODIS yearly CSVs', path=str(RAW / 'NDSI_Snow_Cover/[year].csv'), status=f'{len(modis)} files found; consolidated file missing'))
    if modis:
        frame = pd.concat([dated(path) for path in modis]).sort_index()
        if frame.index.has_duplicates:
            raise ValueError('Duplicate MODIS dates')
        add(frame, {'snow_cover_pct': 'modis_ndsi_index', 'valid_frac': 'modis_valid_fraction'}, False)
    static_path = RAW / 'static_attributes/marala_static_attributes.csv'
    paths.append(dict(input='Static attributes', path=str(static_path), status='found' if static_path.exists() else 'MISSING'))
    if static_path.exists():
        static = read(static_path)
        if len(static) != 1:
            raise ValueError('Expected one static attribute row')
        for name in static:
            valid = np.isfinite(pd.to_numeric(static[name], errors='raise').iloc[0])
            rows.append(dict(column=name, role='static; not daily', first_date='not applicable', last_date='not applicable',
                             missing_days=0 if valid else len(period), missing_pct=0.0 if valid else 100.0))
    paths.append(dict(input='Merged daily training table', path=str(MODEL / 'marala_daily_merged.csv'), status='MISSING; separate inputs audited in memory'))
    return pd.concat(columns, axis=1, sort=True).sort_index(), core, pd.DataFrame(rows), paths


def forecasts(path, q):
    # A CSV must retain forecast issue dates and leads, not just realized weather dates.
    if path is None:
        candidates = []
        for root, dirs, names in os.walk(PROJECT):
            dirs[:] = [d for d in dirs if d not in ('.venv', '.git', 'node_modules', '__pycache__', '_sources', 'chunks', 'compact_copy_zarr')]
            for name in names:
                p = Path(root) / name
                if p.suffix.lower() in ('.csv', '.nc', '.grib', '.grib2', '.grb', '.parquet') and any(s in str(p).lower() for s in ('tigge', 'gfs', 'weather_forecast', 'weather forecast')):
                    candidates.append(p)
        if len(candidates) == 1 and candidates[0].suffix.lower() == '.csv':
            path = candidates[0]
        else:
            return dict(text='not available; not downloaded yet' if not candidates else 'Candidate files found, but issue/lead coverage not verified: ' + '; '.join(map(str, candidates)), overlap_days=0, ten_day_issues=pd.DatetimeIndex([]))
    frame = read(path)
    if 'issue_date' not in frame or 'lead_days' not in frame:
        raise ValueError('Forecast CSV needs issue_date and lead_days columns')
    frame['issue_date'] = pd.to_datetime(frame['issue_date']).dt.normalize()
    leads = pd.to_numeric(frame['lead_days'], errors='raise')
    variables = sorted(frame['variable'].dropna().unique()) if 'variable' in frame else [c for c in frame if c not in ('issue_date', 'lead_days', 'valid_date', 'member')]
    issues = pd.DatetimeIndex(frame['issue_date'].unique())
    complete = pd.DatetimeIndex([d for d, g in frame.groupby('issue_date') if set(range(1, 11)).issubset(set(g['lead_days']))])
    overlap = int((q.notna() & q.index.isin(issues)).sum())
    text = f'{path}; issue dates {issues.min().date()} to {issues.max().date()}; lead days {sorted(leads.unique().tolist())}; variables {variables}; {overlap} observed issue-day overlaps. Complete 1-10 lead-label coverage on {len(complete)} issue dates. Values, ensemble completeness and issuance latency still need validation.'
    return dict(text=text, overlap_days=overlap, ten_day_issues=complete)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--forecasts', type=Path)
    args = parser.parse_args()
    q, paths, exclusions, source_counts = observed_discharge()
    observed = q.notna()
    first, last = q.index.min(), q.index.max()
    annual = pd.DataFrame({'observed_days': observed.groupby(q.index.year).sum().astype(int)})
    annual['calendar_days'] = [366 if calendar.isleap(y) else 365 for y in annual.index]
    annual['coverage_pct'] = 100 * annual['observed_days'] / annual['calendar_days']
    annual.index.name = 'year'
    monthly = observed.groupby(q.index.strftime('%Y-%m')).sum().astype(int).rename('observed_days').rename_axis('month').reset_index()
    month_summary = observed.groupby(q.index.month).sum().astype(int).rename('observed_days').rename_axis('month_of_year').reset_index()
    gaps, continuous = runs(~observed), runs(observed)
    gap_table = pd.DataFrame([dict(gap_length=label, gaps=int(mask.sum()), days=int(gaps[mask].sum())) for label, mask in
                              [('1-3 days', gaps.le(3)), ('4-30 days', gaps.between(4, 30)), ('over 30 days', gaps.gt(30))]])
    longest, equivalent_years = int(continuous.max()), observed.sum() / 365.25
    seasons = []
    for year in annual.index:
        for name, months, denominator in [('monsoon Jul-Sep', (7, 8, 9), 92), ('snowmelt Apr-Jun', (4, 5, 6), 91)]:
            n = int(observed[(q.index.year == year) & q.index.month.isin(months)].sum())
            seasons.append(dict(year=year, season=name, observed_days=n, calendar_days=denominator, usable=n / denominator >= 0.8))
    seasons = pd.DataFrame(seasons)
    monsoon_years = seasons[seasons['season'].eq('monsoon Jul-Sep') & seasons['usable']]['year'].tolist()
    snow_years = seasons[seasons['season'].eq('snowmelt Apr-Jun') & seasons['usable']]['year'].tolist()
    maxima = q.groupby(q.index.year).max()[annual['coverage_pct'].ge(90)]
    if len(maxima) >= 10:
        low, high = maxima.quantile([0.5, 0.8])
        flood_method = f'Empirical annual-maxima 0.5/0.8 quantiles as approximate 2-/5-year levels; {len(maxima)} years with >=90% annual observations. Sampling uncertainty is substantial.'
        high_label = 'approximate 5-year level'
    else:
        low, high = q.quantile([0.95, 0.99])
        flood_method = f'Q95/Q99 daily-flow proxies: only {len(maxima)} annual maxima have >=90% annual observations (<10). These are NOT verified 2-/5-year return levels.'
        high_label = 'Q99 proxy (not a verified 5-year flow)'
    flood_years = sorted(q[q.gt(high)].index.year.unique().tolist())
    frame, core, coverage, input_paths = inputs(q.index)
    paths.extend(input_paths)
    history = pd.date_range(first - pd.Timedelta(days=365), last + pd.Timedelta(days=10))
    forcing_missing = ~np.isfinite(frame[core].reindex(history))
    # Previous 365 days exclude issue day t; targets are t+1 through t+10.
    missing_fraction = forcing_missing.mean(axis=1).rolling(365, min_periods=365).mean().shift(1)
    worst_fraction = forcing_missing.rolling(365, min_periods=365).mean().shift(1).max(axis=1)
    target_days = observed.reindex(history, fill_value=False).rolling(10, min_periods=10).sum().shift(-10)
    candidates = target_days.ge(8) & missing_fraction.le(0.10) & history.isin(q.index)
    strict = candidates & worst_fraction.le(0.10)
    # Extra diagnostic if past discharge is also used as a hindcast input.
    past_q_missing = (~observed.reindex(history, fill_value=False)).rolling(365, min_periods=365).mean().shift(1)
    with_past_q = strict & past_q_missing.le(0.10)
    optional_names = [c for c in frame if c != 'modis_valid_fraction']
    all_missing = ~np.isfinite(frame[optional_names].reindex(history))
    with_optional = target_days.ge(8) & all_missing.mean(axis=1).rolling(365, min_periods=365).mean().shift(1).le(0.10) & history.isin(q.index)
    optional_strict = with_optional & all_missing.rolling(365, min_periods=365).mean().shift(1).max(axis=1).le(0.10)
    samples = pd.DataFrame({'literal_core_samples': candidates, 'per_column_strict_samples': strict,
                            'also_require_past_Q': with_past_q, 'all_optional_dynamic_samples': with_optional,
                            'all_optional_per_column_strict': optional_strict}).groupby(history.year).sum().astype(int).reindex(annual.index)
    samples.index.name = 'year'
    forecast = forecasts(args.forecasts, q)
    complete_samples = int((candidates & history.isin(forecast['ten_day_issues'])).sum())
    core_missing_pct = 100 * (~np.isfinite(frame[core].reindex(q.index))).to_numpy().mean()
    worst_pct = coverage[coverage['role'].eq('core')]['missing_pct'].max()
    on_observed_pct = 100 * (~np.isfinite(frame[core].reindex(q.index[observed]))).to_numpy().mean()
    archived_years = forecast['overlap_days'] / 365.25
    verdict = pd.DataFrame([
        ('Observed years (observed-day equivalent)', f'{equivalent_years:.2f}', higher(equivalent_years, 20, 10)),
        ('Longest continuous run, years', f'{longest / 365.25:.2f}', higher(longest / 365.25, 8, 4)),
        ('Monsoon seasons >=80% observed', str(len(monsoon_years)), higher(len(monsoon_years), 15, 8)),
        ('Observed years overlapping archived forecasts', f'{archived_years:.2f}', higher(archived_years, 8, 4)),
        ('Missing core inputs: calendar-period cell %', f'{core_missing_pct:.2f}%', 'PASS' if core_missing_pct <= 5 else 'WARN' if core_missing_pct <= 15 else 'FAIL'),
        ('Worst core input column missing %', f'{worst_pct:.2f}%', 'PASS' if worst_pct <= 5 else 'WARN' if worst_pct <= 15 else 'FAIL'),
        ('Complete hindcast-forecast samples (lead labels checked)', str(complete_samples), 'FAIL' if not complete_samples else 'WARN')], columns=['requirement', 'value', 'status'])
    # Latest possible target-only split; require >=3 usable monsoons and a high-flow year.
    split = 'IMPOSSIBLE: no chronological target-only split meets the stated test requirements.'
    for start in reversed(annual.index.tolist()):
        if start < annual.index.min() + 2:
            continue
        if sum(y >= start for y in monsoon_years) >= 3 and any(y >= start for y in flood_years):
            split = f'Target-only proposal: train {annual.index.min()}-{start - 2}, validation {start - 1}, test {start}-{annual.index.max()}. Test has {sum(y >= start for y in monsoon_years)} usable monsoons and high-flow proxy years {[y for y in flood_years if y >= start]}. This is NOT executable as a hindcast-forecast LSTM split without archived forecasts and matching dynamic inputs.'
            break
    structural_split = 'No input-supported split found with >=3 usable test monsoons, a high-flow year, and nonempty train/validation samples.'
    available_years = samples.index[samples['per_column_strict_samples'].gt(0)].tolist()
    if available_years:
        end = max(available_years)
        for start in reversed(available_years):
            if start < min(available_years) + 2:
                continue
            test_years = [y for y in monsoon_years if start <= y <= end and y in available_years]
            has_flood = ((q.index.year >= start) & (q.index.year <= end) & q.gt(high)).any()
            if len(test_years) >= 3 and has_flood and samples.loc[start - 1, 'per_column_strict_samples'] > 0:
                structural_split = f'History-input-only alternative: train {min(available_years)}-{start - 2}, validation {start - 1}, test {start}-{end}. This consumes much of the short record for testing; it still has no archived future weather.'
                break
    recommendation = 'gradient boosting baseline only' if archived_years < 4 else ('single-basin LSTM' if equivalent_years >= 20 and len(monsoon_years) >= 15 else 'multi-basin pretraining plus fine-tuning')
    # Reports/plots only; no merged data or discharge estimates are written.
    matrix = np.full((len(annual), 366), -1.0)
    for day, value in observed.items():
        matrix[day.year - annual.index.min(), day.day_of_year - 1] = int(value)
    fig, ax = plt.subplots(figsize=(13, 5))
    ax.imshow(matrix, aspect='auto', interpolation='nearest', cmap=ListedColormap(['#dddddd', '#d95f02', '#1b7894']), vmin=-1, vmax=1)
    ax.set_yticks(range(len(annual)), annual.index)
    ax.set_xticks(np.array([1, 60, 121, 182, 244, 305, 366]) - 1, [1, 60, 121, 182, 244, 305, 366])
    ax.set(xlabel='Day of year', ylabel='Year', title='Marala observed discharge coverage (WAPDA, then FFD)')
    ax.legend(handles=[Patch(color='#1b7894', label='Observed'), Patch(color='#d95f02', label='Missing'), Patch(color='#dddddd', label='Outside audited span')], loc='upper center', bbox_to_anchor=(0.5, -0.14), ncol=3)
    fig.tight_layout(); fig.savefig(HERE / 'discharge_timeline.png', dpi=180, bbox_inches='tight'); plt.close(fig)
    fig, ax = plt.subplots(figsize=(11, 4))
    ax.bar(annual.index, annual['observed_days'], color='#1b7894')
    ax.set(xticks=annual.index, xlabel='Year', ylabel='Observed days', title='Marala observed discharge days per year')
    fig.tight_layout(); fig.savefig(HERE / 'observed_days_per_year.png', dpi=180); plt.close(fig)
    lines = ['# Marala 10-day streamflow data sufficiency report', '',
             'Read-only audit. Thresholds are rules of thumb, not guarantees of LSTM skill. No values were filled, interpolated, corrected or written back. Units are converted to cumecs in memory only.', '',
             '## Located inputs', '', markdown(pd.DataFrame(paths)), '',
             'The existing `experiments/marala_observed/data/daily_observed_priority.csv` contains a separate interpolated column and IRSA means; it is not used as observed ground truth here. No `marala_daily_merged.csv` was found. Optional MODIS is incomplete; reanalysis and CHIRPS are not archived weather forecasts.', '',
             '## 1. Observed discharge coverage', '',
             f'{first.date()} to {last.date()}; {int(observed.sum())} observed days; {len(annual)} distinct calendar years; {(last - first).days / 365.25:.2f} years elapsed; {equivalent_years:.2f} observed-day-equivalent years. Source counts: {source_counts}.', '',
             'Observed-year threshold uses observed days / 365.25 so partial seasonal years are not counted as full years. The distinct calendar-year count and elapsed span above are separate measures.', '',
             'WAPDA takes priority over FFD. The known WAPDA zero and unresolved FFD printed/archive date conflicts are excluded, without correcting original values. WAPDA/FFD disagreements retain the original WAPDA reading; within-source conflicting dates are rejected. IRSA means, outflow, historical event maxima and modeled values are excluded.', '',
             'Most historical WAPDA observation times remain unconfirmed. FFD labels 06:00 PKT; weather features describe UTC days. This date-level coverage audit does not establish that every predictor was available at a common forecast issue time.', '',
             *exclusions, '', markdown(annual.reset_index()), '', '### Observed days by year-month', '', markdown(monthly), '',
             '### Observed days by calendar month across all years', '', markdown(month_summary), '', markdown(gap_table), '',
             f'Longest continuous observed run: {longest} days = {longest / 365.25:.2f} years. Bounded 1-3 day gaps would add {int(gaps[gaps.le(3)].sum())} days IF interpolated; no interpolation was performed.', '',
             '## 2. Hydrological coverage', '',
             f'Usable Jul-Sep monsoons (>=80% of 92 days): {len(monsoon_years)}, years {monsoon_years}. Usable Apr-Jun snowmelt seasons (>=80% of 91 days): {len(snow_years)}, years {snow_years}.', '',
             markdown(seasons), '', flood_method, '',
             f'Lower threshold: {low:.3f} m3/s, {int(q.gt(low).sum())} observed days above it. Higher threshold: {high:.3f} m3/s, {int(q.gt(high).sum())} observed days above it. Years above {high_label}: {flood_years}. These are exceedance DAYS, not independent flood-event counts.', '',
             'Thresholds here describe the entire collection for the sufficiency audit. Model tuning, bias correction and fitted preprocessing must use training data only.', '',
             '## 3. Input coverage', '',
             'Missingness uses every calendar day between the first and last observed discharge dates, including days with no discharge. First/last dates below are the first/last finite values in each saved series. Static fields have no daily timestamp and are checked for a finite scalar only.', '', markdown(coverage), '',
             f'Core columns: {core}. Aggregate core missingness: {core_missing_pct:.2f}% of dynamic cells; worst core column: {worst_pct:.2f}%. On dates with observed discharge only, aggregate core missingness is {on_observed_pct:.2f}%. Optional precipitation alternatives and MODIS are audited but not required for the primary sample count.', '',
             'MODIS snow_cover_pct is an NDSI index, not fractional snow-covered area; valid_frac is a QC field. Static climate normals use 1980-2024 and must be recomputed from the training period if used in model fitting. Snow depth/SWE magnitudes and weighting still need physical review. Temporal completeness is not a quality or issue-time availability clearance.', '',
             '## 4. Archived weather forecast coverage', '', forecast['text'], '',
             f'Observed-day-equivalent years overlapping archive issue dates: {archived_years:.3f}. ERA5-Land/CHIRPS are historical analyzed weather, not forecasts available for t+1 through t+10. Missing source components: archived TIGGE/GFS issue/valid/lead data, plus a consolidated daily training table and the incomplete optional MODIS continuation.', '',
             '## 5. Usable samples', '',
             'Issue day t: observed Q on >=8 of t+1...t+10; the prior 365 calendar days t-365...t-1 have <=10% missing core input CELLS. Historical weather/state features are counted; discharge targets are never imputed. All 365 prior dates must be present as calendar positions. No forecast archive requirement is included in the history-only counts.', '',
             f'Literal core-input candidates: {int(candidates.sum())}. Stricter <=10% missing in EVERY core column: {int(strict.sum())}. If past discharge is also a hindcast input with <=10% missing: {int(with_past_q.sum())}. Including every optional/alternative dynamic feature (QC excluded), cell-rule candidates: {int(with_optional.sum())}; per-column-strict candidates: {int(optional_strict.sum())}. Complete candidates also having forecast lead labels 1-10: {complete_samples}.', '',
             markdown(samples.reset_index()), '',
             'These are overlapping structural samples before split-boundary purging, not independent flood events. A literal cell average can hide a completely missing individual feature, so the per-column count is also shown. Publication latency, valid spatial coverage, and a genuine forecast issue timestamp still need validation.', '',
             '## 6. Proposed chronological split', '', split, '', structural_split, '',
             'An executable complete hindcast-forecast LSTM split is IMPOSSIBLE with no verified archived forecasts. Keep whole 10-day target windows within their partition; historical context may precede its partition. Fit scalers and imputers on training data only. No split is written or model fitted by this script.', '',
             '## 7. Verdict', '', markdown(verdict), '',
             'Status rules: observed years PASS >=20 / WARN >=10 / FAIL <10; continuous years PASS >=8 / WARN >=4 / FAIL <4; monsoons PASS >=15 / WARN >=8 / FAIL <8; archive-overlap years PASS >=8 / WARN >=4 / FAIL <4; missing input cells PASS <=5% / WARN <=15% / FAIL >15%. Extra worst-column and complete-sample rows expose limitations hidden by averages.', '',
             f'**Recommendation: {recommendation}.** The full 10-day hindcast-forecast LSTM is not data-ready. A history-only baseline can be evaluated now. Multi-basin pretraining plus fine-tuning is a later experiment after source QC and basin-specific weather; it cannot replace a missing forecast archive or observed Marala test targets.', '',
             '## 8. Plots', '', '![Observed/missing discharge timeline](discharge_timeline.png)', '', '![Observed days per year](observed_days_per_year.png)', '',
             'Run: `python check_data_sufficiency.py` (optional `--forecasts archive.csv`, with issue_date and lead_days). Only pandas, numpy and matplotlib are required in addition to the Python standard library.']
    report = '\n'.join(lines) + '\n'
    for path, digest in READ_HASHES.items():
        if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f'Input changed during read-only audit: {path}; rerun once external updates finish')
    report += f'\nIntegrity check: all {len(READ_HASHES)} input-file SHA-256 hashes were identical before and after inspection.\n'
    (HERE / 'data_sufficiency_report.md').write_text(report, encoding='utf-8')
    print(report)


if __name__ == '__main__':
    main()
