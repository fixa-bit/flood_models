# Spatial elevation-band LSTM comparison

Day-30 observed-target test (2022–2024), aligned to 1,055 common dates and the training-period Q95 flood threshold of 2,494.714 m³/s.

| Model | NSE | KGE | RMSE (m³/s) | Flood precision | Flood recall |
|---|---:|---:|---:|---:|---:|
| Elevation-band LSTM | 0.801 | 0.874 | 351.79 | 0.392 | 0.392 |
| Catchment-mean control | 0.850 | 0.919 | 305.15 | 0.491 | 0.529 |

The mean-input control outperformed the elevation-band model on this test split. Inputs use noisy ERA5-Land reanalysis as a 30-day weather proxy, so this is a retrospective comparison rather than operational forecast skill. Observed discharge was not filled or changed.

Files here contain the two prediction series, per-lead and seasonal scores, 90% quantile coverage, the report, and the integrity record. The trained checkpoints and complete model code are in `../../../model/model_30_days/Spatial elevation-band LSTM/`.
