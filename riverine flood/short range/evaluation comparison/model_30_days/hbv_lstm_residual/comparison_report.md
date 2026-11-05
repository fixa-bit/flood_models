# HBV plus LSTM residual correction: 30-day results

The LSTM predicts the physical HBV model error from past hydro-weather features and the 30-day HBV/weather trajectory. The median predicted residual is added to physical HBV flow; the 10th and 90th residual quantiles are also saved.

Train: 2016-2020; early stopping validation: 2021-2021; observed test: 2022-2024. Day-30 observed targets: **1055**.
Flood threshold: training Q95 = **2494.714 m3/s**. Missing targets were omitted; no discharge values were changed.

## Lead scores

| Model | lead_day | n | NSE | KGE | RMSE_cumecs | MAE_cumecs | PBIAS_pct |
|---|---:|---:|---:|---:|---:|---:|---:|
| HBV_physical | 1 | 1067 | 0.658 | 0.675 | 458.483 | 293.012 | -11.196 |
| HBV_LSTM | 1 | 1067 | 0.891 | 0.913 | 258.155 | 151.228 | 4.584 |
| HBV_physical | 10 | 1067 | 0.717 | 0.792 | 416.583 | 270.100 | -4.287 |
| HBV_LSTM | 10 | 1067 | 0.759 | 0.770 | 384.301 | 237.445 | 15.819 |
| HBV_physical | 20 | 1065 | 0.732 | 0.817 | 406.660 | 263.602 | -1.937 |
| HBV_LSTM | 20 | 1065 | 0.749 | 0.759 | 393.759 | 244.044 | 17.046 |
| HBV_physical | 30 | 1055 | 0.730 | 0.821 | 409.456 | 263.793 | -0.811 |
| HBV_LSTM | 30 | 1055 | 0.760 | 0.778 | 386.267 | 239.728 | 16.475 |

## Flood and non-flood flow errors at lead 30

| Model | Group | n | NSE | RMSE_cumecs | MAE_cumecs |
|---|---|---:|---:|---:|---:|
| HBV_physical | flood | 51 | -1.979 | 943.385 | 766.276 |
| HBV_physical | non_flood | 1004 | 0.673 | 361.887 | 238.268 |
| HBV_LSTM | flood | 51 | -0.046 | 559.027 | 434.952 |
| HBV_LSTM | non_flood | 1004 | 0.648 | 375.375 | 229.812 |

Future weather is a reanalysis proxy, so this is a retrospective hindcast evaluation rather than operational 30-day forecast skill.

