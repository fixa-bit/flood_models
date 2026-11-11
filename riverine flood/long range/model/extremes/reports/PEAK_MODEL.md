# Marala annual flood-peak model

Censored log-normal regression on storm rainfall, fitted on 1980–2016 (23 PMD-listed flood years, 14 years censored below 200k cusecs = 5663 m³/s).

## Predictor selection (leave-one-year-out)

| Predictors | Mean log score (higher is better) | Brier, ≥400k cusecs (lower is better) |
|---|---:|---:|
| P3 (selected) | -0.883 | 0.146 |
| P3+A30 | -0.892 | 0.147 |
| P3+A30+T3 | -0.927 | 0.154 |
| no_predictor | -1.023 | 0.209 |

Coefficients (standardised predictors): {'intercept': np.float64(8.896), 'log_p3': np.float64(0.373)}; residual sd (log) = 0.56.

## Test years (not used in fitting)

Observed values are the largest **daily** inflow (WAPDA, then Sindh rim); PMD training peaks are instantaneous, so the observed daily value is a lower bound on the event peak. The TFT column is the largest climate-conditioned TFT P50 at 30-day lead in that year.

| Year | Storm 3-day P (mm) | Observed daily max (m³/s) | Peak model median [P10–P90] | P(≥200k) | P(≥400k) | P(≥600k) | TFT max P50 |
|---|---:|---:|---|---:|---:|---:|---:|
| 2017 | 86 | 4,103 (365 d) | 7,987 [3,875–16,463] | 0.73 | 0.27 | 0.09 |  |
| 2018 | 105 | 5,021 (365 d) | 9,256 [4,491–19,079] | 0.81 | 0.36 | 0.14 |  |
| 2019 | 47 | 3,877 (365 d) | 5,197 [2,521–10,711] | 0.44 | 0.08 | 0.02 |  |
| 2020 | 57 | 7,232 (366 d) | 5,914 [2,869–12,189] | 0.53 | 0.12 | 0.03 |  |
| 2021 | 81 | 5,488 (364 d) | 7,638 [3,706–15,744] | 0.70 | 0.24 | 0.08 |  |
| 2022 | 77 | 4,415 (365 d) | 7,372 [3,576–15,195] | 0.68 | 0.22 | 0.07 |  |
| 2023 | 103 | 5,222 (365 d) | 9,147 [4,438–18,854] | 0.80 | 0.35 | 0.14 |  |
| 2024 | 51 | 3,171 (364 d) | 5,492 [2,664–11,319] | 0.48 | 0.10 | 0.02 | 3,073 |
| 2025 | 161 | 21,789 (360 d) | 12,642 [6,134–26,058] | 0.92 | 0.58 | 0.30 | 4,058 |
| 2026 | 126 | 5,524 (255 d) | 10,535 [5,111–21,714] | 0.86 | 0.45 | 0.20 | 531 |

400k cusecs = 11 327 m³/s; 600k cusecs = 16 990 m³/s. 2026 has observations only to early November.

Marala floods are flash events. The 2025 peak (769.5k cusecs on 2025-08-27) is a single 06:00 reading between 107.5k and 191.9k cusecs (FFD and Sindh rim agree). The 2016 PMD event peak (11 669 m³/s) appears in the WAPDA daily series as only 4 117 m³/s. Daily series, and the daily TFT, therefore cannot represent event peaks. Only 2025 gives a clean test, and its observed peak lies inside the model's P10–P90.
