# Residual ensemble: observed benchmark results

Thirty-day point forecasts use the mean-flow head. On 1,055 observed day-30 targets from the previously inspected 2022-2024 benchmark:

| Model | NSE | RMSE, cumecs |
|---|---:|---:|
| Residual LSTM ensemble | 0.858 | 297.6 |
| Exact month/day climatology | 0.792 | 359.4 |
| Smoothed climatology | 0.820 | 334.5 |

High-flow RMSE was 826.1 cumecs, compared with climatology 973.6. Empirically adjusted P05-P95 coverage was 90.6%. High-flow hit rate remains limited at 33%; these are noisy-reanalysis results, not verified operational weather-forecast scores.

See [full run results](../../RUN_RESULTS.md), `scores_by_lead.csv`, `scores_by_season_and_lead.csv`, `scores_flood_nonflood_by_lead.csv`, `quantile_calibration.csv` and `verification.json` for methods, counts and limitations.
