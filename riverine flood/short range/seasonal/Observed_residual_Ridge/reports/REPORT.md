# Observed-only seasonal residual Ridge

| Horizon | Test origins | Model RMSE | Climatology RMSE | Skill vs climatology | NSE | KGE | Bias | Flood hit rate |
|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| 90 days | 9 | 90.2 | 110.8 | 0.186 | 0.969 | 0.883 | 4.0% | 1.000 |
| 180 days | 7 | 70.1 | 77.8 | 0.098 | 0.912 | 0.876 | 5.8% | 1.000 |

Validation: observed 2022–2023; alpha selected from the configured Ridge candidates. Final fit: observed WAPDA 2016–2023. Test: observed WAPDA 2024 only. Test origins are monthly and overlap in their future target windows.

The model uses antecedent discharge and antecedent weather/snow indicators only. Target values are never filled. These few test origins make results exploratory; a single held-out year does not establish dependable seasonal skill.
