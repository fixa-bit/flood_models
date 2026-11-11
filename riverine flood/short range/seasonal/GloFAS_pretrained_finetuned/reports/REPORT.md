# Seasonal GloFAS pretraining experiment

| Horizon | Test origins | RMSE | MAE | NSE | Bias | RMSE skill vs observed climatology | Flood hit rate |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 90 days | 9 | 410.6 | 324.2 | 0.366 | -13.7% | -2.707 | 0.333 |
| 180 days | 7 | 212.6 | 202.7 | 0.193 | -10.6% | -1.734 | 0.000 |

Test set: observed WAPDA Marala targets in 2024 only; model fitting used GloFAS 1980–2015, observed fine-tuning 2016–2023, and validation 2022–2023 for epoch selection.

**Caution:** GloFAS is simulated, not measured flow. This is a small exploratory test with few independent seasonal forecast origins; scores do not establish operational long-range forecast skill. The forecast features use antecedent conditions only. No target values were filled or altered.
