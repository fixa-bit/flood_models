# Actual run: Marala, 2026-10-30

**These are observed-discharge test results using realized future ERA5 weather plus noise. They do not demonstrate operational TIGGE/GFS forecast accuracy.**

## What ran

```powershell
# Working directory: D:\projects\flood_model\flood_model\riverine flood\short range\model
$python = "../experiments/marala_observed/.venv/Scripts/python.exe"
& $python data.py --config config.yaml --prepare
& $python -u train.py --config config.yaml
& $python -m unittest discover -s tests -v
& $python -u evaluate.py --config config.yaml
```

The preparation command created the included table once. It refuses to overwrite it. LSTM training ran once for seed 42; folder organization changed afterwards without retraining or changing weights. Evaluation was rerun while fixing report output organization and saving component metadata; test scores were not used to tune hyperparameters or weights. The final correctness suite passed all 13 tests (4.652 seconds). The synthetic fine-tuning test loads a checkpoint, updates trainable weights, retains normalization and preserves frozen encoder weights; it is not a real-basin accuracy experiment. No real new-basin or archived-product fine-tuning was run.

Real LSTM training: **16 epochs**, early stopping after epoch 16; selected epoch **10** by validation pinball **0.07978935** in normalized log space. CPU, hidden size 64, hindcast 365 days, horizon 10, one layer, seed 42. Training-loop time: **106.50 seconds**. This loss is not an accuracy percentage.

Train years: 2016-2020; validation and ensemble-weight fitting: 2021; test: 2022-2024. Train / validation / test issue samples: 1,767 / 356 / 1,084. All 10 target dates must remain within their split. Individual missing target days remain masked.

The daily table contains **3454** selected observed targets (2016-03-01 to 2026-10-15) and **13636** NaN targets across its weather-context calendar. No target filling or interpolation was performed. Input normalization and target normalization use training years only.

| q_source | observed_targets |
| --- | --- |
| FFD | 239 |
| WAPDA | 3215 |

## Observed test counts

| year | observed_days_scored |
| --- | --- |
| 2022 | 365 |
| 2023 | 365 |
| 2024 | 354 |

Unique observed basin-days across all leads: **1084**. Scored issue/lead/target pairs: **10795**. Day 1 has 1,084 observed targets and day 10 has 1,075. Overlapping issue windows do not represent independent floods.

## Day 1 and day 10 comparison

| lead_day | model | n | NSE | KGE | PBIAS_pct | RMSE_cumecs | MAE_cumecs |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | LSTM | 1084 | 0.886 | 0.902 | -2.371 | 263.760 | 157.279 |
| 1 | persistence | 1084 | 0.870 | 0.935 | 0.000 | 282.358 | 134.178 |
| 1 | climatology | 1084 | 0.784 | 0.849 | 7.793 | 363.415 | 233.349 |
| 1 | gradient_boosting | 1084 | 0.875 | 0.916 | 2.670 | 276.755 | 170.310 |
| 1 | Ensemble | 1084 | 0.891 | 0.912 | -0.231 | 258.621 | 155.689 |
| 10 | LSTM | 1075 | 0.857 | 0.910 | 5.644 | 295.702 | 187.128 |
| 10 | persistence | 1075 | 0.652 | 0.826 | 0.364 | 461.403 | 273.370 |
| 10 | climatology | 1075 | 0.790 | 0.850 | 8.144 | 358.575 | 232.513 |
| 10 | gradient_boosting | 1075 | 0.851 | 0.877 | 0.541 | 302.424 | 192.642 |
| 10 | Ensemble | 1075 | 0.866 | 0.916 | 4.630 | 286.462 | 180.540 |

The different-model ensemble combines the LSTM median and gradient boosting. Nonnegative weights were fitted separately per lead on 2021 observations only and normalized to sum to one. The LSTM itself has one trained seed in this run. Weights are in `ensemble/runs/initial/weights.json`; additional LSTM seeds are supported but were not trained. The blend is not better at every lead or season.

## Day 10 seasonal limitations

| model | season | n | NSE | KGE | PBIAS_pct | peak_n | peak_MAPE_pct | flood_hit_rate | false_alarm_rate | false_alarm_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LSTM | Apr-Jun | 273 | 0.601 | 0.771 | 9.419 | 3 | 12.579 | 0.333 | 0.000 | 0.000 |
| Ensemble | Apr-Jun | 273 | 0.588 | 0.745 | 10.120 | 3 | 15.189 | 0.333 | 0.000 | 0.000 |
| LSTM | Jul-Sep | 276 | 0.602 | 0.671 | 6.689 | 47 | 15.384 | 0.617 | 0.096 | 0.431 |
| Ensemble | Jul-Sep | 276 | 0.643 | 0.693 | 4.337 | 47 | 15.687 | 0.553 | 0.087 | 0.435 |
| LSTM | Oct-Mar | 526 | 0.254 | 0.520 | -3.041 | 1 | 81.073 | 0.000 | 0.000 | NA |
| Ensemble | Oct-Mar | 526 | 0.294 | 0.512 | -2.293 | 1 | 81.040 | 0.000 | 0.000 | NA |

The high-flow/flood threshold is training Q95: **2494.71 cumecs**, not an official danger level or a 5-year return flow. Day-10 monsoon ensemble hit rate is 55.3%; false-alarm ratio is 43.5%. Sparse seasonal peak counts, including just one Oct-Mar peak, limit interpretation. Overall annual NSE includes the strong seasonal cycle and hides weaker within-season performance.

## LSTM interval calibration

| lead_day | observed_targets | nominal_coverage | actual_coverage |
| --- | --- | --- | --- |
| 1 | 1084 | 0.900 | 0.899 |
| 2 | 1083 | 0.900 | 0.880 |
| 3 | 1082 | 0.900 | 0.878 |
| 4 | 1081 | 0.900 | 0.865 |
| 5 | 1080 | 0.900 | 0.889 |
| 6 | 1079 | 0.900 | 0.874 |
| 7 | 1078 | 0.900 | 0.880 |
| 8 | 1077 | 0.900 | 0.877 |
| 9 | 1076 | 0.900 | 0.849 |
| 10 | 1075 | 0.900 | 0.833 |

Day-10 empirical coverage is 83.3% against nominal 90%, so these intervals are under-covering overall. Day-10 coverage by season is 81.0% Apr-Jun, 91.7% Jul-Sep and 80.0% Oct-Mar. Non-crossing quantiles do not guarantee calibrated uncertainty. The different-model blend has no claimed prediction interval.

## Verification and limits

All original preparation-source SHA256 values still match. The merged daily file SHA256 matches the training checkpoint and evaluation manifest. Combined outputs contain all five models (50 overall rows and 150 seasonal rows); separate prediction and score files exist for each model. `ensemble/reports/initial/verification.json` records this check and package versions.

| package | version |
| --- | --- |
| torch | 2.15.0+cpu |
| numpy | 2.4.6 |
| pandas | 3.1.0 |
| scikit-learn | 1.9.1 |
| matplotlib | 3.11.2 |
| PyYAML | 6.0.3 |

Most weather inputs end in 2024. No real archived forecasts were evaluated. Source observation times and final-product publication latency need review before operational forecasts. The test years have been inspected in earlier workspace experiments: they were excluded from this run's fitting, but they are not a globally untouched research holdout. Short record, regulation, limited independent extremes and overlapping windows remain material limitations.

Keep both the LSTM and gradient boosting as research candidates and retain persistence/climatology benchmarks. Collect older observations, more basins and archived forecasts before relying on 10-day flood warnings. The synthetic suite establishes code behavior only.

[Full seasonal/lead evaluation](ensemble/reports/initial/evaluation_report.md) | [Configuration](config.yaml) | [Instructions](README.md)
