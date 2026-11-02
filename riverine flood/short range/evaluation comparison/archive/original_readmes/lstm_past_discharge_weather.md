# Matched_LSTM

<!-- REAL_RESULTS -->

## Actual observed-test results

| model | lead_day | n | NSE | KGE | PBIAS_pct | RMSE_cumecs | MAE_cumecs | peak_MAPE_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Matched_LSTM | 1 | 1084 | 0.905 | 0.953 | 0.111 | 240.621 | 138.215 | 12.929 |
| Matched_LSTM | 5 | 1080 | 0.885 | 0.938 | -1.804 | 265.039 | 154.172 | 15.451 |
| Matched_LSTM | 10 | 1075 | 0.880 | 0.936 | -0.754 | 270.918 | 162.780 | 17.370 |

| group | n | NSE | KGE | RMSE_cumecs | MAE_cumecs | PBIAS_pct |
| --- | --- | --- | --- | --- | --- | --- |
| flood | 51 | -0.973 | 0.266 | 767.831 | 552.927 | -16.987 |
| non_flood | 1024 | 0.879 | 0.890 | 218.378 | 143.349 | 2.468 |

These use noisy future reanalysis; operational forecast accuracy is unverified. Full files are in reports/initial/.
