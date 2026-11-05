# Calibrated physical HBV: 30-day results

Calibration used observed discharge from 2016-2020 after 730 spin-up days. Validation: 2021-2021. Test: 2022-2024.
Observed day-30 test targets: **1055**. Missing targets were skipped; no discharge values were filled.

Training-period flood threshold (Q95): **2494.714 m3/s**.

## Lead scores

| lead_day | n | NSE | KGE | RMSE_cumecs | MAE_cumecs | PBIAS_pct |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 1067 | 0.658 | 0.675 | 458.483 | 293.012 | -11.196 |
| 10 | 1067 | 0.717 | 0.792 | 416.583 | 270.100 | -4.287 |
| 20 | 1065 | 0.732 | 0.817 | 406.660 | 263.602 | -1.937 |
| 30 | 1055 | 0.730 | 0.821 | 409.456 | 263.793 | -0.811 |

## Flood and non-flood scores at day 30

| class | n | NSE | KGE | RMSE_cumecs | MAE_cumecs |
|---|---:|---:|---:|---:|---:|
| flood | 51 | -1.979 | 0.224 | 943.385 | 766.276 |
| non_flood | 1004 | 0.673 | 0.829 | 361.887 | 238.268 |

Future forcing uses reanalysis weather as a forecast stand-in. These are retrospective hindcast scores, not operational 30-day forecast skill.

