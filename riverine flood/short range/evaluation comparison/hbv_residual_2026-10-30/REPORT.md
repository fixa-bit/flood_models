# HBV residual models: actual training and rolling monsoon results

Run date (Asia/Karachi): 2026-10-30. Evaluated monsoons: [2021, 2022, 2023, 2024].

Each fold calibrates HBV and fits monthly weather mappings on 2016 through test_year-2. The following complete year selects ML early stopping; the next June-September season is evaluated. All ten target dates stay in their own split/season. Initial 730 days spin up stores. Daily issue forecasts update states from past weather and use discharge observed through issue day. No test target enters fitting, normalization, weather mapping or threshold selection.

## Mean of the ten lead-specific scores

| Model | KGE | NSE | MAE m³/s | Flood MAE m³/s | Event peak MAE m³/s | Timing MAE days |
|---|---:|---:|---:|---:|---:|---:|
| HBV | 0.522 | 0.178 | 507.862 | 936.664 | 1107.438 | 2.800 |
| HBV_LSTM | 0.764 | 0.638 | 315.673 | 519.702 | 915.190 | 2.513 |
| HBV_LightGBM | 0.722 | 0.602 | 336.269 | 576.735 | 859.367 | 2.675 |
| persistence | 0.596 | 0.200 | 451.139 | 836.947 | 55.466 | 4.650 |

These means summarize lead-specific scores; they are not a single pooled KGE. Flood days exceed each fold's training Q95. Event windows are +/-5 days around observed exceedance clusters separated by more than seven days. Signed errors and event dates are in peak_events.csv.

## Does the hybrid beat the baselines?

- HBV_LSTM vs HBV: higher KGE at 10/10 leads; lower MAE at 10/10; lower flood MAE at 10/10; lower event peak magnitude MAE at 10/10; lower timing MAE at 6/10.
- HBV_LSTM vs persistence: higher KGE at 9/10 leads; lower MAE at 9/10; lower flood MAE at 10/10; lower event peak magnitude MAE at 0/10; lower timing MAE at 7/10.
- HBV_LightGBM vs HBV: higher KGE at 10/10 leads; lower MAE at 10/10; lower flood MAE at 10/10; lower event peak magnitude MAE at 10/10; lower timing MAE at 4/10.
- HBV_LightGBM vs persistence: higher KGE at 9/10 leads; lower MAE at 10/10; lower flood MAE at 10/10; lower event peak magnitude MAE at 0/10; lower timing MAE at 8/10.

Threshold metrics (POD, FAR, CSI and Brier) are saved per lead and season, together with TP/FP/FN and observed event counts. Forecast exceedance uses probability >=0.5. Undefined ratios are left missing. Statistical Q90/Q95/Q99 thresholds are training-derived, not official flood classes. No official station thresholds were supplied in this configuration.

Persistence can reproduce the observed event magnitude after a delay; its small local-window peak magnitude error should be judged jointly with timing and threshold scores. Neither hybrid consistently improves every flood diagnostic.

## Statistical flood-threshold scores

The following are means of the ten pooled lead-specific scores at each fold's training Q95.

| Model | POD | FAR | CSI | Brier score |
|---|---:|---:|---:|---:|
| HBV | 0.267 | 0.392 | 0.227 | 0.126 |
| HBV_LSTM | 0.660 | 0.302 | 0.511 | 0.067 |
| HBV_LightGBM | 0.551 | 0.333 | 0.431 | 0.075 |
| persistence | 0.402 | 0.598 | 0.258 | 0.167 |

## Data and operational limitations

- No archived weather forecasts were supplied. Future ERA5-Land rainfall and temperature are realized reanalysis, so these are optimistic weather-driven hindcasts. Training/operations mismatch remains unquantified.
- No authentic meteorological ensemble was found; this run has one reanalysis member. P10/P50/P90 quantify conditional residual uncertainty, not full weather, parameter or structural uncertainty. Genuine issued ensembles are supported by the archive input schema and are propagated separately through HBV and both corrections.
- Rainfall quantile mapping uses training ERA5-Land vs CHIRPS v3. Temperature has no independent observed reference and uses an identity mapping against the same ERA5-Land series; independent temperature bias correction is unvalidated.
- MOD10A1 exports actually available end in 2019. They contain mean NDSI, not fractional snow-covered area. MODIS is used as a quality-screened, two-day-delayed historical index and for rank diagnostics only. The snow fraction feature is an assumed HBV depletion curve. No independent MODIS validation covers the test monsoons.
- No issued GloFAS forecasts were available; that baseline was not evaluated.
- Observed discharge is not gap-filled. WAPDA historical observation times are largely unconfirmed; dates are aligned with UTC weather days by the existing table. Operational availability and reading/day alignment need validation.
- These years have already been inspected in earlier workspace experiments. They are excluded from each fold's fitting but are not a globally untouched research holdout. Seasonal sample sizes are small and daily forecast windows overlap.
- HBV is lumped, with a linear routing reservoir. Elevation bands, glacier ice melt, regulation and diversions are not resolved. Final AI-adjusted flow need not conserve water even when HBV does.
- Mixture probabilities use equal member weights and a piecewise-linear conditional quantile function with constant tails outside P10/P90. Very rare exceedances and cross-lead event probabilities are not resolved by this approximation.
- HBV_LightGBM mean empirical P10-P90 coverage: 0.623 (nominal 0.80). The intervals are not post-calibrated on the test seasons.
- HBV_LSTM mean empirical P10-P90 coverage: 0.627 (nominal 0.80). The intervals are not post-calibrated on the test seasons.

## Saved artifacts

- `folds/YYYY/physical/`: calibrated parameters, optimizer trace, daily states/fluxes, water balance and MODIS diagnostics.
- `folds/YYYY/forcing/`: train-only monthly quantile maps and PET climatology.
- `folds/YYYY/models/`: 30 LightGBM text models, feature importance, LSTM best checkpoint, normalization and training history.
- `folds/YYYY/forecasts/`: P10/P50/P90, threshold probabilities, per-member forecasts and HBV trajectories.
- `reports/`: rolling predictions, all requested metrics, event details, baseline comparisons and plots.
- `final/`: refit on all eligible 2016-2024 observations with stopping lengths fixed from the last fold. Its last historical forecast is an in-sample replay, not an operational forecast or a held-out score.
- `data/`, `config.json`, `requirements-lock.txt`, `input_manifest.json`, `artifact_manifest.json` and `training.log`: reproducibility records.
