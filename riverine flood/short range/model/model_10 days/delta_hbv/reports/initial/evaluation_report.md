# delta-HBV observed test performance

| model | lead_day | n | NSE | KGE | RMSE_cumecs | MAE_cumecs | PBIAS_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| delta_HBV | 1 | 1084 | 0.456 | 0.680 | 577.118 | 360.653 | -21.412 |
| delta_HBV | 2 | 1083 | 0.456 | 0.680 | 576.964 | 360.446 | -21.459 |
| delta_HBV | 3 | 1082 | 0.456 | 0.679 | 577.114 | 360.753 | -21.499 |
| delta_HBV | 4 | 1081 | 0.456 | 0.680 | 577.132 | 360.664 | -21.506 |
| delta_HBV | 5 | 1080 | 0.458 | 0.680 | 576.361 | 361.181 | -21.488 |
| delta_HBV | 6 | 1079 | 0.459 | 0.681 | 575.716 | 361.322 | -21.383 |
| delta_HBV | 7 | 1078 | 0.462 | 0.683 | 574.329 | 360.322 | -21.314 |
| delta_HBV | 8 | 1077 | 0.466 | 0.684 | 572.438 | 359.105 | -21.256 |
| delta_HBV | 9 | 1076 | 0.464 | 0.685 | 573.568 | 359.000 | -20.991 |
| delta_HBV | 10 | 1075 | 0.474 | 0.691 | 567.639 | 356.184 | -20.512 |

| model | lead_day | group | n | NSE | KGE | RMSE_cumecs | MAE_cumecs | PBIAS_pct | peak_n | peak_MAPE_pct | flood_hit_rate | false_alarm_rate | false_alarm_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| delta_HBV | 10 | all | 1075 | 0.474 | 0.691 | 567.639 | 356.184 | -20.512 | 51 | 34.001 | 0.431 | 0.017 | 0.436 |
| delta_HBV | 10 | flood | 51 | -3.952 | -0.448 | 1216.305 | 978.444 | -11.459 | 51 | 34.001 | 0.431 | NA | 0.000 |
| delta_HBV | 10 | non_flood | 1024 | 0.328 | 0.636 | 514.374 | 325.193 | -22.309 | 0 | NA | NA | 0.017 | 1.000 |

Observed test days: 1084; test years: [2022, 2023, 2024].

The full methods and limitations are in README.md and the separate evaluation comparison/delta_hbv/comparison_report.md.
