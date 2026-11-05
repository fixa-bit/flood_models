# N-HiTS 30-day comparison

N-HiTS was scored on the same 1,055 observed lead-30 targets (2022–2024) as the other models, using the training-period Q95 threshold of 2,494.714 m³/s.

| Actual class | Days | Precision | Recall | F1 | RMSE (m³/s) | MAE (m³/s) |
|---|---:|---:|---:|---:|---:|---:|
| Flood | 51 | 0.250 | 0.196 | 0.220 | 1,292.69 | 1,112.55 |
| Non-flood | 1,004 | 0.960 | 0.970 | 0.965 | 354.35 | 219.54 |

Overall day-30 NSE is 0.678 and KGE is 0.813. The model detected 10 of the 51 flood days. Its NSE is below the training-climatology baseline (0.792) on this split. Future weather is noisy ERA5-Land reanalysis, not an archived forecast.

The adjacent CSVs contain the prediction series, lead/season scores, quantile coverage, flood detections and verification record. Checkpoint and model code are under `../../../model/model_30_days/N-HiTS/`.
