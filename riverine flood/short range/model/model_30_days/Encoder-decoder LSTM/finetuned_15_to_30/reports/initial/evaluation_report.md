# Thirty-day encoder-decoder: observed benchmark results

On 1,055 observed day-30 targets from 2022-2024:

| Model | NSE | KGE | RMSE, cumecs |
|---|---:|---:|---:|
| New encoder-decoder ensemble | 0.849 | 0.915 | 306.4 |
| Previous best ensemble | 0.858 | 0.874 | 297.6 |
| Exact climatology | 0.792 | 0.845 | 359.4 |
| Smoothed climatology | 0.820 | 0.835 | 334.5 |

The new model beats both climatology controls but does not improve on the previous best overall NSE. Its high-flow RMSE is 801.6 cumecs versus the previous best 826.1; its non-high-flow RMSE is 256.9 versus 241.6.

High-flow hit rate is 41.2% versus 33.3%, but false-alarm ratio rises to 61.8% versus 45.2%. High flow means observed discharge above training Q95, not an official flood category. The nominal 90% range covers 82.5% of observations.

These are noisy-reanalysis benchmark results; operational thirty-day flood forecasting skill is unverified. See [full run results](../../RUN_RESULTS.md), the adjacent score CSVs, quantile calibration and `verification.json` for methods, counts and limitations.
