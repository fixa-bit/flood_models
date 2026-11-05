# HBV plus LightGBM residual correction: 30-day results

Separate LightGBM quantile models predict the physical HBV error for each lead from issue-date hydrology and the 30-day HBV/weather trajectory. The median predicted residual is added to physical HBV flow; the 10th and 90th residual quantiles are also saved.

Train: 2016-2020; early stopping validation: 2021-2021; observed test: 2022-2024. Day-30 observed targets: **1055**.
Flood threshold: training Q95 = **2494.714 m3/s**. Missing targets were omitted; no discharge values were changed.

## Lead scores

| Model | lead_day | n | NSE | KGE | RMSE_cumecs | MAE_cumecs | PBIAS_pct |
|---|---:|---:|---:|---:|---:|---:|---:|
| HBV_physical | 1 | 1067 | 0.658 | 0.675 | 458.483 | 293.012 | -11.196 |
| HBV_LightGBM | 1 | 1067 | 0.902 | 0.911 | 245.593 | 122.840 | -1.636 |
| HBV_physical | 10 | 1067 | 0.717 | 0.792 | 416.583 | 270.100 | -4.287 |
| HBV_LightGBM | 10 | 1067 | 0.777 | 0.860 | 369.455 | 231.034 | -1.032 |
| HBV_physical | 20 | 1065 | 0.732 | 0.817 | 406.660 | 263.602 | -1.937 |
| HBV_LightGBM | 20 | 1065 | 0.779 | 0.868 | 369.042 | 240.256 | 7.319 |
| HBV_physical | 30 | 1055 | 0.730 | 0.821 | 409.456 | 263.793 | -0.811 |
| HBV_LightGBM | 30 | 1055 | 0.780 | 0.874 | 369.351 | 238.597 | 6.467 |

## Flood and non-flood flow errors at lead 30

| Model | Group | n | NSE | RMSE_cumecs | MAE_cumecs |
|---|---|---:|---:|---:|---:|
| HBV_physical | flood | 51 | -1.979 | 943.385 | 766.276 |
| HBV_physical | non_flood | 1004 | 0.673 | 361.887 | 238.268 |
| HBV_LightGBM | flood | 51 | -0.903 | 754.040 | 578.381 |
| HBV_LightGBM | non_flood | 1004 | 0.714 | 338.332 | 221.337 |

Future weather is a reanalysis proxy, so this is a retrospective hindcast evaluation rather than operational 30-day forecast skill.

