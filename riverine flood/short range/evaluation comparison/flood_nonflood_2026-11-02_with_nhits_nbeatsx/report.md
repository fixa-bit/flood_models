# Flood versus non-flood performance

Report date: 2026-11-02 (Asia/Karachi). This analysis reads existing saved predictions; no models were retrained, no settings tuned and no discharge filled or modified.

Flood proxy: observed target discharge strictly above training Q95. Main and 15-day experiments: **2494.714185 m3/s**, calculated from observed 2016-2020 targets only. Non-flood is observed flow at or below that threshold. These are high-flow exceedance days, not official flood classes or independent flood events.

Groups are defined by observed flow, not predicted flow. Every model in a cohort is compared on identical issue/target/lead keys, using observed targets only. Overlapping forecast windows are not independent observations. Earlier 30-day-history experiments use their own 2016-2021 training Q95; HBV uses each fold's saved training Q95; nearby regression uses its training-season Q95.

RMSE and MAE are in m3/s; lower is better. NSE and original KGE are recomputed within each subset. Subset NSE uses the subset mean as its reference and can be negative when the flow range is narrow. Do not compare flood NSE directly with non-flood NSE as if their reference variances were equal. PBIAS is positive for overprediction. Full bias, MAPE and KGE are in the CSV.

## Main experiments: day 10, 2022-2024

| Model | Flood n | Flood RMSE | Flood MAE | Flood NSE | Other n | Other RMSE | Other MAE | Other NSE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 8-basin LSTM fine-tuned | 51 | 642.992 | 432.442 | -0.384 | 1024 | 314.862 | 207.371 | 0.748 |
| 15-day seq2seq fine-tuned | 51 | 649.830 | 475.190 | -0.413 | 1024 | 306.214 | 196.115 | 0.762 |
| 2-input LSTM scratch | 51 | 657.633 | 450.916 | -0.448 | 1024 | 317.170 | 207.081 | 0.745 |
| 15-day seq2seq scratch | 51 | 673.432 | 474.358 | -0.518 | 1024 | 304.455 | 193.402 | 0.765 |
| Catchment-mean LSTM control | 51 | 703.579 | 495.081 | -0.657 | 1024 | 246.424 | 158.393 | 0.846 |
| Global LSTM fine-tuned | 51 | 706.530 | 568.806 | -0.671 | 1024 | 234.076 | 154.527 | 0.861 |
| Snow-bucket + LSTM | 51 | 730.224 | 526.837 | -0.785 | 1024 | 303.232 | 200.744 | 0.767 |
| Original LSTM | 51 | 745.564 | 528.245 | -0.861 | 1024 | 253.199 | 170.138 | 0.837 |
| LSTM + boosting ensemble | 51 | 748.273 | 540.792 | -0.874 | 1024 | 241.374 | 162.598 | 0.852 |
| Matched past-Q/weather LSTM | 51 | 767.831 | 552.927 | -0.973 | 1024 | 218.378 | 143.349 | 0.879 |
| Gradient boosting | 51 | 811.471 | 661.697 | -1.204 | 1024 | 251.435 | 169.281 | 0.840 |
| Elevation-band LSTM | 51 | 896.689 | 688.608 | -1.691 | 1024 | 233.089 | 166.341 | 0.862 |
| Climatology | 51 | 973.625 | 743.534 | -2.173 | 1024 | 296.257 | 207.062 | 0.777 |
| N-HiTS | 51 | 1091.647 | 864.918 | -2.989 | 1024 | 361.661 | 217.842 | 0.668 |
| Persistence | 51 | 1184.345 | 957.609 | -3.695 | 1024 | 391.964 | 239.291 | 0.610 |
| N-BEATSx | 51 | 1228.967 | 1007.744 | -4.055 | 1024 | 325.926 | 197.724 | 0.730 |
| 8-basin donor LSTM without adaptation | 51 | 2714.118 | 2662.483 | -23.657 | 1024 | 869.094 | 659.106 | -0.917 |
| Global LSTM zero-shot (reference) | 51 | 2857.494 | 2804.919 | -26.331 | 1024 | 888.740 | 652.928 | -1.005 |

Rows are ordered by flood-day RMSE. Zero-shot global weights were downloaded rather than trained here. Donor-only and zero-shot rows are transfer diagnostics, not recommended Marala models. The rejected weighted-fill model below is retained only as historical evaluation evidence.

## Flood detection: main day 10

| Model | TP | FN | FP | TN | Hit rate | False-alarm ratio | False-alarm rate | CSI |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Original LSTM | 30 | 21 | 22 | 1002 | 0.588 | 0.423 | 0.021 | 0.411 |
| Gradient boosting | 16 | 35 | 13 | 1011 | 0.314 | 0.448 | 0.013 | 0.250 |
| LSTM + boosting ensemble | 27 | 24 | 20 | 1004 | 0.529 | 0.426 | 0.020 | 0.380 |
| Persistence | 14 | 37 | 37 | 987 | 0.275 | 0.725 | 0.036 | 0.159 |
| Climatology | 13 | 38 | 20 | 1004 | 0.255 | 0.606 | 0.020 | 0.183 |
| Global LSTM fine-tuned | 33 | 18 | 26 | 998 | 0.647 | 0.441 | 0.025 | 0.429 |
| Global LSTM zero-shot (reference) | 0 | 51 | 0 | 1024 | 0.000 | NA | 0.000 | 0.000 |
| Elevation-band LSTM | 10 | 41 | 10 | 1014 | 0.196 | 0.500 | 0.010 | 0.164 |
| Catchment-mean LSTM control | 34 | 17 | 26 | 998 | 0.667 | 0.433 | 0.025 | 0.442 |
| Snow-bucket + LSTM | 32 | 19 | 41 | 983 | 0.627 | 0.562 | 0.040 | 0.348 |
| 8-basin LSTM fine-tuned | 39 | 12 | 50 | 974 | 0.765 | 0.562 | 0.049 | 0.386 |
| 2-input LSTM scratch | 38 | 13 | 46 | 978 | 0.745 | 0.548 | 0.045 | 0.392 |
| 8-basin donor LSTM without adaptation | 0 | 51 | 0 | 1024 | 0.000 | NA | 0.000 | 0.000 |
| 15-day seq2seq fine-tuned | 41 | 10 | 44 | 980 | 0.804 | 0.518 | 0.043 | 0.432 |
| 15-day seq2seq scratch | 41 | 10 | 43 | 981 | 0.804 | 0.512 | 0.042 | 0.436 |
| N-HiTS | 24 | 27 | 50 | 974 | 0.471 | 0.676 | 0.049 | 0.238 |
| N-BEATSx | 14 | 37 | 20 | 1004 | 0.275 | 0.588 | 0.020 | 0.197 |
| Matched past-Q/weather LSTM | 23 | 28 | 18 | 1006 | 0.451 | 0.439 | 0.018 | 0.333 |

A predicted alert means point forecast > training Q95. Hit rate = TP/(TP+FN); false-alarm ratio = FP/(TP+FP); false-alarm rate = FP/(FP+TN). Undefined ratios are NA. This classification check differs from probabilistic warning scores derived from quantile exceedance probabilities.

## Encoder-decoder models: day 15, 2022-2024

| Model | Flood n | Flood RMSE | Flood MAE | Flood NSE | Other n | Other RMSE | Other MAE | Other NSE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 15-day seq2seq fine-tuned | 51 | 633.275 | 465.998 | -0.342 | 1019 | 319.791 | 201.225 | 0.742 |
| 15-day seq2seq scratch | 51 | 679.907 | 468.934 | -0.547 | 1019 | 315.225 | 198.625 | 0.749 |
| Climatology | 51 | 973.625 | 743.534 | -2.173 | 1019 | 295.612 | 206.341 | 0.779 |
| Persistence | 51 | 1219.466 | 1028.124 | -3.978 | 1019 | 448.768 | 285.347 | 0.491 |

## HBV rolling June-September tests: day 10, 2021-2024

| Model | Flood n | Flood RMSE | Flood MAE | Flood NSE | Other n | Other RMSE | Other MAE | Other NSE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| HBV_LSTM | 63 | 736.703 | 516.793 | -0.541 | 389 | 392.623 | 293.652 | 0.397 |
| HBV_LightGBM | 63 | 844.817 | 655.414 | -1.027 | 389 | 455.369 | 374.041 | 0.188 |
| HBV | 63 | 1061.524 | 882.801 | -2.200 | 389 | 535.209 | 423.859 | -0.121 |
| persistence | 63 | 1168.855 | 944.030 | -2.880 | 389 | 657.319 | 498.420 | -0.691 |

This cohort has different test seasons, folds, observed-day coverage and training thresholds from the full-year main experiments. Its scores do not rank those models against the main table.

## Earlier discharge/GRRR experiments: day 15, 2023-2026

| Model | Flood n | Flood RMSE | Flood MAE | Flood NSE | Other n | Other RMSE | Other MAE | Other NSE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Persistence | 68 | 2839.496 | 1687.393 | -0.248 | 823 | 969.333 | 383.971 | -0.989 |
| GRRR weighted-fill LSTM (rejected) | 68 | 2895.362 | 1430.985 | -0.298 | 823 | 336.437 | 239.413 | 0.760 |
| LSTM + lagged GRRR, gaps retained | 68 | 2897.324 | 1434.199 | -0.300 | 823 | 334.862 | 238.025 | 0.763 |
| Discharge-history LSTM | 68 | 2995.444 | 1515.136 | -0.389 | 823 | 286.975 | 197.853 | 0.826 |

Threshold: 2487.634973 m3/s from observed 2016-2021 training discharge. Source predictions of the discharge-history-only LSTM store observed flow in float32; matching across the legacy tables allows 0.002 m3/s rounding differences. Each model's stored observed values are preserved. GRRR feature availability in 2026 differs from its training period.

## Nearby-gauge reconstructions: July-September 2026

| Model | Flood n | Flood RMSE | Flood MAE | Flood NSE | Other n | Other RMSE | Other MAE | Other NSE |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Khanki same-day regression | 6 | 1107.714 | 1004.291 | -1.479 | 86 | 281.001 | 236.333 | 0.753 |
| Qadirabad lagged reconstruction | 6 | 1147.998 | 1125.619 | -1.663 | 86 | 325.947 | 223.633 | 0.668 |
| Qadirabad-next-day / Khanki fallback | 6 | 1147.998 | 1125.619 | -1.663 | 86 | 325.947 | 223.633 | 0.668 |
| Qadirabad same-day regression | 6 | 1202.732 | 977.499 | -1.923 | 86 | 305.165 | 248.035 | 0.709 |
| Khanki lagged reconstruction | 6 | 1402.719 | 1338.150 | -2.976 | 86 | 314.430 | 258.238 | 0.691 |
| Trimmu lagged reconstruction | 6 | 1868.636 | 1756.527 | -6.055 | 86 | 382.956 | 301.508 | 0.541 |
| Trimmu same-day regression | 6 | 2357.845 | 2243.178 | -10.233 | 86 | 437.087 | 337.807 | 0.402 |

These are reconstructions from nearby readings, not future forecasts. Lagged downstream readings can occur after the reconstructed Marala day. The six Q95 exceedance days in this holdout are a small sample, and earlier blocked validation was unstable. This new grouping does not approve automatic filling.

## Availability and limitations

The main day-10 cohort contains 1,075 observed target days: 51 above Q95 and 1,024 at or below it. Full per-lead counts, common-date exclusions, source hashes and thresholds are in analysis_manifest.json. All leads are saved in scores_flood_nonflood_by_lead.csv. Overall scores reproduce the earlier reports to the precision retained in the prediction CSVs (RMSE tolerance 0.0001 m3/s; NSE tolerance 0.00000001). No official warning-level labels or independent inundation observations were supplied.

Weather-driven experiments use realized/noisy reanalysis as stand-in forecasts. These are not established operational TIGGE/GFS forecast scores. Models have different features, architectures and losses, so score differences do not isolate a causal benefit of a model component. Previously inspected holdouts, small flood samples, overlapping windows, regulation and reading/availability times limit conclusions. No test-driven retraining, model selection or ensemble-weight update was performed here.
