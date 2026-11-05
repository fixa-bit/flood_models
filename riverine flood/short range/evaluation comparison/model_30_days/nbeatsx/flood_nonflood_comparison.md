# Lead-30 flood/non-flood model comparison

- Flood threshold: **2494.71 m3/s** (must be training-derived).
- Common observed cases: **1055** (51 flood, 1004 non-flood).
- Flood means observed flow at or above the threshold. Accuracy uses both classes; class precision/recall/F1 are computed one-vs-rest.

| Model | Actual class | n | Accuracy | Precision | Recall | F1 | RMSE (m3/s) | MAE (m3/s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| N-BEATSx | Flood | 51 | 0.914 | 0.267 | 0.451 | 0.336 | 1163.9 | 893.0 |
| N-BEATSx | Non-flood | 1004 | 0.914 | 0.971 | 0.937 | 0.954 | 464.4 | 278.8 |
