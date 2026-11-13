# Flash-flood model: test results

Generated from `metrics.json` (2026-11-13T05:14:33+00:00). Target: a reported flood onset in a 20 km cell on a Pakistan-local day. Test: 2022-01-01 to 2026-01-31, every cell-day not masked as ongoing coverage.

| Model | Area | Onsets | Base rate | PR-AUC | ROC-AUC | Brier skill vs climatology | Onsets in daily top 1 % / 5 % of cells | Hit rate | False-alarm ratio | CSI |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| LightGBM, with day's rain (forecast stand-in) | Pakistan | 8,614 | 0.00253 | 0.062 | 0.938 | -0.008 | 0.14 / 0.40 | 0.16 | 0.90 | 0.067 |
| LightGBM, with day's rain (forecast stand-in) | Chenab districts | 639 | 0.00656 | 0.070 | 0.908 | -0.004 | 0.07 / 0.17 | 0.18 | 0.90 | 0.068 |
| LightGBM, rain before the day only | Pakistan | 8,614 | 0.00253 | 0.048 | 0.929 | 0.000 | 0.13 / 0.37 | 0.12 | 0.91 | 0.053 |
| LightGBM, rain before the day only | Chenab districts | 639 | 0.00656 | 0.062 | 0.901 | 0.002 | 0.06 / 0.17 | 0.16 | 0.90 | 0.066 |
| LightGBM, weather and terrain only (no reporting inputs) | Pakistan | 8,614 | 0.00253 | 0.061 | 0.936 | -0.015 | 0.14 / 0.39 | 0.18 | 0.91 | 0.066 |
| LightGBM, weather and terrain only (no reporting inputs) | Chenab districts | 639 | 0.00656 | 0.072 | 0.906 | -0.013 | 0.06 / 0.16 | 0.21 | 0.90 | 0.074 |
| Climatology + rain trigger | Pakistan | 8,614 | 0.00253 | 0.052 | 0.915 | -0.000 | 0.13 / 0.37 | 0.18 | 0.92 | 0.060 |
| Climatology + rain trigger | Chenab districts | 639 | 0.00656 | 0.060 | 0.896 | -0.045 | 0.07 / 0.15 | 0.30 | 0.93 | 0.063 |
| Climatology (reporting-adjusted) | Pakistan | 8,614 | 0.00253 | 0.035 | 0.903 | — | 0.11 / 0.34 | 0.27 | 0.96 | 0.039 |
| Climatology (reporting-adjusted) | Chenab districts | 639 | 0.00656 | 0.048 | 0.890 | — | 0.06 / 0.15 | 0.40 | 0.95 | 0.048 |

Alarm thresholds were chosen on 2020–2021 to maximise CSI. PR-AUC should be read against the base rate (a no-skill model scores the base rate).

## By year and season (Pakistan, LightGBM with the day's rain)

| Slice | Onsets | PR-AUC | ROC-AUC | Brier skill | Top 5 % |
|---|---:|---:|---:|---:|---:|
| monsoon_jun_sep | 7,199 | 0.068 | 0.891 | -0.008 | 0.36 |
| other_months | 1,415 | 0.027 | 0.929 | -0.009 | 0.59 |
| year_2022 | 2,557 | 0.060 | 0.929 | -0.021 | 0.37 |
| year_2023 | 1,491 | 0.047 | 0.939 | -0.022 | 0.40 |
| year_2024 | 1,618 | 0.069 | 0.944 | -0.006 | 0.48 |
| year_2025 | 2,947 | 0.078 | 0.944 | 0.008 | 0.37 |
| year_2026 | 1 | 0.003 | 0.996 | -0.146 | 1.00 |

## By province (LightGBM with the day's rain)

| Area | Onsets | PR-AUC | ROC-AUC | Brier skill | Top 5 % |
|---|---:|---:|---:|---:|---:|
| AJK / Gilgit-Baltistan | 649 | 0.054 | 0.943 | 0.008 | 0.42 |
| Balochistan | 1,062 | 0.031 | 0.938 | -0.049 | 0.55 |
| Islamabad | 18 | 0.180 | 0.899 | 0.051 | 1.00 |
| Khyber Pakhtunkhwa | 1,730 | 0.056 | 0.906 | -0.007 | 0.28 |
| Punjab | 3,349 | 0.071 | 0.924 | 0.008 | 0.25 |
| Sindh | 1,806 | 0.085 | 0.925 | -0.023 | 0.33 |

## Case days

- 2025-08-14, KP, Gilgit-Baltistan and AJK cloudbursts (Buner floods began 15 Aug): 74 cells reported an onset; 23 of them were among the 5 % highest-risk cells that day.
- 2022-08-27, KP floods, Swat valley: 59 cells reported an onset; 15 of them were among the 5 % highest-risk cells that day.

## What the model relies on (share of total gain)

- LightGBM, with day's rain (forecast stand-in): reports_national_week_vs_year 16%, rain_day 12%, rain_day_nbr_max 12%, season_sin 8%, season_cos 6%, reports_cell_share_prev365 4%, lon 4%, built_fraction 4%
- LightGBM, rain before the day only: reports_national_week_vs_year 22%, season_sin 10%, rain_prev1 8%, season_cos 7%, built_fraction 7%, reports_cell_share_prev365 6%, rain_prev3 5%, lon 4%
- LightGBM, weather and terrain only (no reporting inputs): rain_day_nbr_max 15%, rain_day 12%, season_sin 9%, season_cos 7%, rain_prev30 6%, built_fraction 5%, soil_moisture_prev1 5%, lon 5%

Figures: `reliability.png`, `test_period_maps.png`, `case_days.png`.
