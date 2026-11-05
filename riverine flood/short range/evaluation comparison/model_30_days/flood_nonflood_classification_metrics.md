# Lead-30 flood/non-flood model comparison

- Flood threshold: **2494.71 m3/s** (must be training-derived).
- Common observed cases: **1055** (51 flood, 1004 non-flood).
- Flood means observed flow at or above the threshold. Accuracy uses both classes; class precision/recall/F1 are computed one-vs-rest.

| Model | Actual class | n | Accuracy | Precision | Recall | F1 | RMSE (m3/s) | MAE (m3/s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| Weather-only LSTM | Flood | 51 | 0.947 | 0.451 | 0.451 | 0.451 | 931.4 | 725.7 |
| Weather-only LSTM | Non-flood | 1004 | 0.947 | 0.972 | 0.972 | 0.972 | 311.0 | 198.6 |
| Past-discharge LSTM | Flood | 51 | 0.951 | 0.490 | 0.471 | 0.480 | 903.8 | 705.9 |
| Past-discharge LSTM | Non-flood | 1004 | 0.951 | 0.973 | 0.975 | 0.974 | 311.2 | 190.3 |
| Climatology-residual ensemble | Flood | 51 | 0.955 | 0.548 | 0.333 | 0.415 | 826.1 | 637.2 |
| Climatology-residual ensemble | Non-flood | 1004 | 0.955 | 0.967 | 0.986 | 0.976 | 241.6 | 169.1 |
| Fine-tuned encoder-decoder | Flood | 51 | 0.939 | 0.382 | 0.412 | 0.396 | 801.6 | 572.7 |
| Fine-tuned encoder-decoder | Non-flood | 1004 | 0.939 | 0.970 | 0.966 | 0.968 | 256.9 | 176.2 |
| delta-HBV | Flood | 51 | 0.955 | 0.543 | 0.490 | 0.515 | 1155.8 | 951.1 |
| delta-HBV | Non-flood | 1004 | 0.955 | 0.974 | 0.979 | 0.977 | 424.5 | 270.1 |
| Calibrated physical HBV | Flood | 51 | 0.951 | 0.485 | 0.314 | 0.381 | 943.4 | 766.3 |
| Calibrated physical HBV | Non-flood | 1004 | 0.951 | 0.966 | 0.983 | 0.974 | 361.9 | 238.3 |
| HBV-LSTM residual | Flood | 51 | 0.940 | 0.432 | 0.745 | 0.547 | 559.0 | 435.0 |
| HBV-LSTM residual | Non-flood | 1004 | 0.940 | 0.987 | 0.950 | 0.968 | 375.4 | 229.8 |
| HBV-LightGBM residual | Flood | 51 | 0.944 | 0.435 | 0.529 | 0.478 | 754.0 | 578.4 |
| HBV-LightGBM residual | Non-flood | 1004 | 0.944 | 0.976 | 0.965 | 0.970 | 338.3 | 221.3 |
| Spatial elevation-band LSTM | Flood | 51 | 0.941 | 0.392 | 0.392 | 0.392 | 854.2 | 611.4 |
| Spatial elevation-band LSTM | Non-flood | 1004 | 0.941 | 0.969 | 0.969 | 0.969 | 304.9 | 200.5 |
| Catchment-mean control | Flood | 51 | 0.951 | 0.491 | 0.529 | 0.509 | 728.2 | 530.6 |
| Catchment-mean control | Non-flood | 1004 | 0.951 | 0.976 | 0.972 | 0.974 | 266.3 | 171.5 |
| N-HiTS | Flood | 51 | 0.933 | 0.250 | 0.196 | 0.220 | 1292.7 | 1112.5 |
| N-HiTS | Non-flood | 1004 | 0.933 | 0.960 | 0.970 | 0.965 | 354.3 | 219.5 |
| N-BEATSx | Flood | 51 | 0.914 | 0.267 | 0.451 | 0.336 | 1163.9 | 893.0 |
| N-BEATSx | Non-flood | 1004 | 0.914 | 0.971 | 0.937 | 0.954 | 464.4 | 278.8 |
