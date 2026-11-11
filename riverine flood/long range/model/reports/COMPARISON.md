# Marala long-range comparison (held-out test, issues from 2024-01-01)

All models in a mode are scored on the same (issue date, target date) pairs. Skill = 1 − RMSE / RMSE of observed day-of-year climatology (2016–2023). Point forecast = P50. Coverage = share of observations inside P10–P90 (ideal 0.80). Issues overlap (one per day), so pairs are not independent.

## Mode: climate_conditioned

| Model | Leads (days) | Issues | NSE | KGE | RMSE m³/s | Skill vs clim | PBIAS % | P10–P90 coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| climatology | 1-30 | 769 | 0.41 | 0.43 | 924 | 0.00 | -9.9 | 0.78 |
| climatology | 31-90 | 773 | 0.40 | 0.42 | 941 | 0.00 | -10.2 | 0.78 |
| climatology | 91-180 | 773 | 0.40 | 0.43 | 947 | 0.00 | -7.5 | 0.77 |
| climatology | 1-180 | 773 | 0.40 | 0.43 | 941 | 0.00 | -8.8 | 0.77 |
| damped_persistence | 1-30 | 769 | 0.42 | 0.45 | 915 | 0.01 | -10.0 | 0.77 |
| damped_persistence | 31-90 | 773 | 0.39 | 0.42 | 944 | -0.00 | -11.4 | 0.80 |
| damped_persistence | 91-180 | 773 | 0.40 | 0.42 | 948 | -0.00 | -8.5 | 0.80 |
| damped_persistence | 1-180 | 773 | 0.40 | 0.43 | 941 | -0.00 | -9.7 | 0.80 |
| tft_scratch | 1-30 | 769 | 0.47 | 0.52 | 876 | 0.05 | -6.5 | 0.73 |
| tft_scratch | 31-90 | 773 | 0.46 | 0.53 | 888 | 0.06 | -3.3 | 0.72 |
| tft_scratch | 91-180 | 773 | 0.46 | 0.54 | 894 | 0.06 | 0.9 | 0.67 |
| tft_scratch | 1-180 | 773 | 0.46 | 0.54 | 889 | 0.06 | -1.7 | 0.70 |
| tft_pretrained_only | 1-30 | 769 | 0.51 | 0.54 | 838 | 0.09 | -26.0 | 0.22 |
| tft_pretrained_only | 31-90 | 773 | 0.48 | 0.51 | 876 | 0.07 | -29.8 | 0.17 |
| tft_pretrained_only | 91-180 | 773 | 0.48 | 0.55 | 879 | 0.07 | -27.7 | 0.16 |
| tft_pretrained_only | 1-180 | 773 | 0.49 | 0.53 | 871 | 0.07 | -28.1 | 0.17 |
| tft_finetuned | 1-30 | 769 | 0.58 | 0.61 | 781 | 0.15 | -3.3 | 0.66 |
| tft_finetuned | 31-90 | 773 | 0.57 | 0.59 | 792 | 0.16 | -2.9 | 0.64 |
| tft_finetuned | 91-180 | 773 | 0.57 | 0.60 | 799 | 0.16 | 1.6 | 0.59 |
| tft_finetuned | 1-180 | 773 | 0.57 | 0.60 | 794 | 0.16 | -0.7 | 0.62 |
| glofas_raw | 1-30 | 769 | 0.51 | 0.43 | 836 | 0.09 | -42.3 | 0.00 |
| glofas_raw | 31-90 | 773 | 0.51 | 0.43 | 851 | 0.09 | -42.6 | 0.00 |
| glofas_raw | 91-180 | 773 | 0.49 | 0.44 | 868 | 0.08 | -42.5 | 0.00 |
| glofas_raw | 1-180 | 773 | 0.50 | 0.43 | 857 | 0.09 | -42.5 | 0.00 |

By target period, leads 1–180:

| Model | Period | NSE | KGE | Skill vs clim |
|---|---|---:|---:|---:|
| climatology | 2024 | 0.87 | 0.93 | 0.00 |
| climatology | 2025-2026 | 0.32 | 0.30 | 0.00 |
| damped_persistence | 2024 | 0.86 | 0.93 | -0.04 |
| damped_persistence | 2025-2026 | 0.32 | 0.30 | 0.00 |
| tft_scratch | 2024 | 0.90 | 0.91 | 0.11 |
| tft_scratch | 2025-2026 | 0.39 | 0.43 | 0.05 |
| tft_pretrained_only | 2024 | 0.56 | 0.68 | -0.85 |
| tft_pretrained_only | 2025-2026 | 0.47 | 0.47 | 0.12 |
| tft_finetuned | 2024 | 0.90 | 0.85 | 0.11 |
| tft_finetuned | 2025-2026 | 0.52 | 0.50 | 0.16 |
| glofas_raw | 2024 | 0.22 | 0.50 | -1.45 |
| glofas_raw | 2025-2026 | 0.55 | 0.42 | 0.18 |

## Mode: forecast

| Model | Leads (days) | Issues | NSE | KGE | RMSE m³/s | Skill vs clim | PBIAS % | P10–P90 coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| climatology | 1-30 | 884 | 0.45 | 0.48 | 888 | 0.00 | -8.3 | 0.78 |
| climatology | 31-90 | 887 | 0.42 | 0.45 | 898 | 0.00 | -9.0 | 0.79 |
| climatology | 91-180 | 827 | 0.40 | 0.43 | 937 | 0.00 | -7.3 | 0.77 |
| climatology | 1-180 | 888 | 0.42 | 0.44 | 915 | 0.00 | -8.1 | 0.78 |
| damped_persistence | 1-30 | 884 | 0.45 | 0.49 | 885 | 0.00 | -9.2 | 0.79 |
| damped_persistence | 31-90 | 887 | 0.41 | 0.44 | 904 | -0.01 | -10.6 | 0.81 |
| damped_persistence | 91-180 | 827 | 0.40 | 0.42 | 938 | -0.00 | -8.3 | 0.81 |
| damped_persistence | 1-180 | 888 | 0.41 | 0.44 | 917 | -0.00 | -9.3 | 0.80 |
| tft_scratch | 1-30 | 884 | 0.45 | 0.49 | 882 | 0.01 | -7.3 | 0.79 |
| tft_scratch | 31-90 | 887 | 0.42 | 0.47 | 894 | 0.01 | -6.2 | 0.79 |
| tft_scratch | 91-180 | 827 | 0.41 | 0.45 | 932 | 0.00 | -5.6 | 0.77 |
| tft_scratch | 1-180 | 888 | 0.42 | 0.47 | 910 | 0.01 | -6.1 | 0.78 |
| tft_pretrained_only | 1-30 | 884 | 0.20 | 0.20 | 1067 | -0.20 | -45.3 | 0.57 |
| tft_pretrained_only | 31-90 | 887 | 0.16 | 0.18 | 1079 | -0.20 | -45.1 | 0.52 |
| tft_pretrained_only | 91-180 | 827 | 0.19 | 0.23 | 1086 | -0.16 | -40.9 | 0.54 |
| tft_pretrained_only | 1-180 | 888 | 0.18 | 0.21 | 1080 | -0.18 | -43.2 | 0.54 |
| tft_finetuned | 1-30 | 884 | 0.44 | 0.51 | 891 | -0.00 | -6.8 | 0.76 |
| tft_finetuned | 31-90 | 887 | 0.41 | 0.47 | 904 | -0.01 | -7.2 | 0.74 |
| tft_finetuned | 91-180 | 827 | 0.40 | 0.46 | 940 | -0.00 | -5.3 | 0.72 |
| tft_finetuned | 1-180 | 888 | 0.41 | 0.47 | 919 | -0.00 | -6.3 | 0.74 |

By target period, leads 1–180:

| Model | Period | NSE | KGE | Skill vs clim |
|---|---|---:|---:|---:|
| climatology | 2024 | 0.87 | 0.93 | 0.00 |
| climatology | 2025-2026 | 0.35 | 0.34 | 0.00 |
| damped_persistence | 2024 | 0.86 | 0.93 | -0.04 |
| damped_persistence | 2025-2026 | 0.34 | 0.33 | -0.00 |
| tft_scratch | 2024 | 0.86 | 0.92 | -0.03 |
| tft_scratch | 2025-2026 | 0.35 | 0.36 | 0.01 |
| tft_pretrained_only | 2024 | 0.56 | 0.68 | -0.84 |
| tft_pretrained_only | 2025-2026 | 0.13 | 0.06 | -0.16 |
| tft_finetuned | 2024 | 0.84 | 0.90 | -0.11 |
| tft_finetuned | 2025-2026 | 0.34 | 0.36 | -0.00 |

## Mode: projection

| Model | Leads (days) | Issues | NSE | KGE | RMSE m³/s | Skill vs clim | PBIAS % | P10–P90 coverage |
|---|---|---:|---:|---:|---:|---:|---:|---:|
| climatology | 1-30 | 769 | 0.41 | 0.43 | 924 | 0.00 | -9.9 | 0.78 |
| climatology | 31-90 | 773 | 0.40 | 0.42 | 941 | 0.00 | -10.2 | 0.78 |
| climatology | 91-180 | 773 | 0.40 | 0.43 | 947 | 0.00 | -7.5 | 0.77 |
| climatology | 1-180 | 773 | 0.40 | 0.43 | 941 | 0.00 | -8.8 | 0.77 |
| damped_persistence | 1-30 | 769 | 0.42 | 0.45 | 915 | 0.01 | -10.0 | 0.77 |
| damped_persistence | 31-90 | 773 | 0.39 | 0.42 | 944 | -0.00 | -11.4 | 0.80 |
| damped_persistence | 91-180 | 773 | 0.40 | 0.42 | 948 | -0.00 | -8.5 | 0.80 |
| damped_persistence | 1-180 | 773 | 0.40 | 0.43 | 941 | -0.00 | -9.7 | 0.80 |
| tft_scratch | 1-30 | 769 | 0.46 | 0.54 | 879 | 0.05 | -4.3 | 0.69 |
| tft_scratch | 31-90 | 773 | 0.46 | 0.54 | 892 | 0.05 | -3.7 | 0.70 |
| tft_scratch | 91-180 | 773 | 0.46 | 0.54 | 899 | 0.05 | -1.5 | 0.69 |
| tft_scratch | 1-180 | 773 | 0.46 | 0.54 | 893 | 0.05 | -2.7 | 0.69 |
| tft_pretrained_only | 1-30 | 769 | 0.50 | 0.50 | 849 | 0.08 | -32.5 | 0.23 |
| tft_pretrained_only | 31-90 | 773 | 0.49 | 0.49 | 864 | 0.08 | -32.7 | 0.22 |
| tft_pretrained_only | 91-180 | 773 | 0.49 | 0.50 | 871 | 0.08 | -31.7 | 0.21 |
| tft_pretrained_only | 1-180 | 773 | 0.49 | 0.50 | 865 | 0.08 | -32.2 | 0.22 |
| tft_finetuned | 1-30 | 769 | 0.55 | 0.60 | 801 | 0.13 | -3.4 | 0.72 |
| tft_finetuned | 31-90 | 773 | 0.56 | 0.59 | 807 | 0.14 | -2.5 | 0.73 |
| tft_finetuned | 91-180 | 773 | 0.56 | 0.59 | 807 | 0.15 | -1.3 | 0.70 |
| tft_finetuned | 1-180 | 773 | 0.56 | 0.59 | 806 | 0.14 | -2.0 | 0.72 |
| glofas_raw | 1-30 | 769 | 0.51 | 0.43 | 836 | 0.09 | -42.3 | 0.00 |
| glofas_raw | 31-90 | 773 | 0.51 | 0.43 | 851 | 0.09 | -42.6 | 0.00 |
| glofas_raw | 91-180 | 773 | 0.49 | 0.44 | 868 | 0.08 | -42.5 | 0.00 |
| glofas_raw | 1-180 | 773 | 0.50 | 0.43 | 857 | 0.09 | -42.5 | 0.00 |

By target period, leads 1–180:

| Model | Period | NSE | KGE | Skill vs clim |
|---|---|---:|---:|---:|
| climatology | 2024 | 0.87 | 0.93 | 0.00 |
| climatology | 2025-2026 | 0.32 | 0.30 | 0.00 |
| damped_persistence | 2024 | 0.86 | 0.93 | -0.04 |
| damped_persistence | 2025-2026 | 0.32 | 0.30 | 0.00 |
| tft_scratch | 2024 | 0.89 | 0.87 | 0.08 |
| tft_scratch | 2025-2026 | 0.39 | 0.43 | 0.05 |
| tft_pretrained_only | 2024 | 0.56 | 0.67 | -0.85 |
| tft_pretrained_only | 2025-2026 | 0.48 | 0.42 | 0.13 |
| tft_finetuned | 2024 | 0.89 | 0.83 | 0.07 |
| tft_finetuned | 2025-2026 | 0.51 | 0.48 | 0.15 |
| glofas_raw | 2024 | 0.22 | 0.50 | -1.45 |
| glofas_raw | 2025-2026 | 0.55 | 0.42 | 0.18 |

## 90- and 180-day mean flow on the seasonal Ridge test dates

Only the (issue date, horizon) pairs in the short-range seasonal Ridge 2024 test. Ridge values are read from its saved predictions and use its own month-of-issue climatology; the others use the day-of-year climatology. Compare skill, not RMSE, across those two groups. 9 and 7 issues only.

| Mode | Model | Horizon | Issues | RMSE m³/s | Climatology RMSE | Skill |
|---|---|---:|---:|---:|---:|---:|
| climate_conditioned | climatology | 90 | 9 | 51 | 51 | +0.00 |
| climate_conditioned | climatology | 180 | 7 | 21 | 21 | +0.00 |
| climate_conditioned | damped_persistence | 90 | 9 | 136 | 51 | -1.65 |
| climate_conditioned | damped_persistence | 180 | 7 | 78 | 21 | -2.63 |
| climate_conditioned | glofas_raw | 90 | 9 | 478 | 51 | -8.30 |
| climate_conditioned | glofas_raw | 180 | 7 | 479 | 21 | -21.34 |
| climate_conditioned | seasonal_ridge (short range) | 90 | 9 | 90 | 111 | +0.19 |
| climate_conditioned | seasonal_ridge (short range) | 180 | 7 | 70 | 78 | +0.10 |
| climate_conditioned | tft_finetuned | 90 | 9 | 158 | 51 | -2.08 |
| climate_conditioned | tft_finetuned | 180 | 7 | 107 | 21 | -4.01 |
| climate_conditioned | tft_pretrained_only | 90 | 9 | 295 | 51 | -4.73 |
| climate_conditioned | tft_pretrained_only | 180 | 7 | 276 | 21 | -11.87 |
| climate_conditioned | tft_scratch | 90 | 9 | 110 | 51 | -1.14 |
| climate_conditioned | tft_scratch | 180 | 7 | 71 | 21 | -2.33 |
| forecast | climatology | 90 | 9 | 51 | 51 | +0.00 |
| forecast | climatology | 180 | 7 | 21 | 21 | +0.00 |
| forecast | damped_persistence | 90 | 9 | 136 | 51 | -1.65 |
| forecast | damped_persistence | 180 | 7 | 78 | 21 | -2.63 |
| forecast | seasonal_ridge (short range) | 90 | 9 | 90 | 111 | +0.19 |
| forecast | seasonal_ridge (short range) | 180 | 7 | 70 | 78 | +0.10 |
| forecast | tft_finetuned | 90 | 9 | 90 | 51 | -0.75 |
| forecast | tft_finetuned | 180 | 7 | 58 | 21 | -1.71 |
| forecast | tft_pretrained_only | 90 | 9 | 323 | 51 | -5.28 |
| forecast | tft_pretrained_only | 180 | 7 | 284 | 21 | -12.26 |
| forecast | tft_scratch | 90 | 9 | 73 | 51 | -0.41 |
| forecast | tft_scratch | 180 | 7 | 54 | 21 | -1.50 |
| projection | climatology | 90 | 9 | 51 | 51 | +0.00 |
| projection | climatology | 180 | 7 | 21 | 21 | +0.00 |
| projection | damped_persistence | 90 | 9 | 136 | 51 | -1.65 |
| projection | damped_persistence | 180 | 7 | 78 | 21 | -2.63 |
| projection | glofas_raw | 90 | 9 | 478 | 51 | -8.30 |
| projection | glofas_raw | 180 | 7 | 479 | 21 | -21.34 |
| projection | seasonal_ridge (short range) | 90 | 9 | 90 | 111 | +0.19 |
| projection | seasonal_ridge (short range) | 180 | 7 | 70 | 78 | +0.10 |
| projection | tft_finetuned | 90 | 9 | 152 | 51 | -1.96 |
| projection | tft_finetuned | 180 | 7 | 124 | 21 | -4.78 |
| projection | tft_pretrained_only | 90 | 9 | 328 | 51 | -5.38 |
| projection | tft_pretrained_only | 180 | 7 | 308 | 21 | -13.36 |
| projection | tft_scratch | 90 | 9 | 137 | 51 | -1.66 |
| projection | tft_scratch | 180 | 7 | 95 | 21 | -3.43 |

## Flood peaks

Largest observed daily inflow in each target year against the same model's P50 and P90 for that date, at fixed leads (one issue date per row).

| Mode | Model | Year | Observed peak m³/s | Date | Lead | P50 | P90 |
|---|---|---|---:|---|---:|---:|---:|
| climate_conditioned | climatology | 2024 | 3171 | 2024-08-08 | 30 | 2236 | 3143 |
| climate_conditioned | climatology | 2024 | 3171 | 2024-08-08 | 90 | 2236 | 3143 |
| climate_conditioned | climatology | 2024 | 3171 | 2024-08-08 | 180 | 2236 | 3143 |
| climate_conditioned | climatology | 2025 | 21789 | 2025-08-27 | 30 | 1719 | 2416 |
| climate_conditioned | climatology | 2025 | 21789 | 2025-08-27 | 90 | 1719 | 2416 |
| climate_conditioned | climatology | 2025 | 21789 | 2025-08-27 | 180 | 1719 | 2416 |
| climate_conditioned | glofas_raw | 2024 | 3171 | 2024-08-08 | 30 | 3013 |  |
| climate_conditioned | glofas_raw | 2024 | 3171 | 2024-08-08 | 90 | 3013 |  |
| climate_conditioned | glofas_raw | 2024 | 3171 | 2024-08-08 | 180 | 3013 |  |
| climate_conditioned | glofas_raw | 2025 | 21789 | 2025-08-27 | 30 | 8566 |  |
| climate_conditioned | glofas_raw | 2025 | 21789 | 2025-08-27 | 90 | 8566 |  |
| climate_conditioned | glofas_raw | 2025 | 21789 | 2025-08-27 | 180 | 8566 |  |
| climate_conditioned | tft_finetuned | 2024 | 3171 | 2024-08-08 | 30 | 3048 | 3855 |
| climate_conditioned | tft_finetuned | 2024 | 3171 | 2024-08-08 | 90 | 3076 | 3899 |
| climate_conditioned | tft_finetuned | 2024 | 3171 | 2024-08-08 | 180 | 3081 | 3905 |
| climate_conditioned | tft_finetuned | 2025 | 21789 | 2025-08-27 | 30 | 4058 | 6026 |
| climate_conditioned | tft_finetuned | 2025 | 21789 | 2025-08-27 | 90 | 4022 | 5992 |
| climate_conditioned | tft_finetuned | 2025 | 21789 | 2025-08-27 | 180 | 4035 | 6030 |
| climate_conditioned | tft_scratch | 2024 | 3171 | 2024-08-08 | 30 | 2573 | 3431 |
| climate_conditioned | tft_scratch | 2024 | 3171 | 2024-08-08 | 90 | 2610 | 3471 |
| climate_conditioned | tft_scratch | 2024 | 3171 | 2024-08-08 | 180 | 2615 | 3491 |
| climate_conditioned | tft_scratch | 2025 | 21789 | 2025-08-27 | 30 | 2314 | 3195 |
| climate_conditioned | tft_scratch | 2025 | 21789 | 2025-08-27 | 90 | 2399 | 3312 |
| climate_conditioned | tft_scratch | 2025 | 21789 | 2025-08-27 | 180 | 2404 | 3332 |
| forecast | climatology | 2024 | 3171 | 2024-08-08 | 30 | 2236 | 3143 |
| forecast | climatology | 2024 | 3171 | 2024-08-08 | 90 | 2236 | 3143 |
| forecast | climatology | 2024 | 3171 | 2024-08-08 | 180 | 2236 | 3143 |
| forecast | climatology | 2025 | 21789 | 2025-08-27 | 30 | 1719 | 2416 |
| forecast | climatology | 2025 | 21789 | 2025-08-27 | 90 | 1719 | 2416 |
| forecast | climatology | 2025 | 21789 | 2025-08-27 | 180 | 1719 | 2416 |
| forecast | tft_finetuned | 2024 | 3171 | 2024-08-08 | 30 | 2298 | 3008 |
| forecast | tft_finetuned | 2024 | 3171 | 2024-08-08 | 90 | 2304 | 3029 |
| forecast | tft_finetuned | 2024 | 3171 | 2024-08-08 | 180 | 2320 | 3037 |
| forecast | tft_finetuned | 2025 | 21789 | 2025-08-27 | 30 | 1688 | 2202 |
| forecast | tft_finetuned | 2025 | 21789 | 2025-08-27 | 90 | 1704 | 2236 |
| forecast | tft_finetuned | 2025 | 21789 | 2025-08-27 | 180 | 1727 | 2258 |
| forecast | tft_scratch | 2024 | 3171 | 2024-08-08 | 30 | 2292 | 2983 |
| forecast | tft_scratch | 2024 | 3171 | 2024-08-08 | 90 | 2321 | 3039 |
| forecast | tft_scratch | 2024 | 3171 | 2024-08-08 | 180 | 2227 | 2924 |
| forecast | tft_scratch | 2025 | 21789 | 2025-08-27 | 30 | 1779 | 2285 |
| forecast | tft_scratch | 2025 | 21789 | 2025-08-27 | 90 | 1797 | 2334 |
| forecast | tft_scratch | 2025 | 21789 | 2025-08-27 | 180 | 1748 | 2275 |
| projection | climatology | 2024 | 3171 | 2024-08-08 | 30 | 2236 | 3143 |
| projection | climatology | 2024 | 3171 | 2024-08-08 | 90 | 2236 | 3143 |
| projection | climatology | 2024 | 3171 | 2024-08-08 | 180 | 2236 | 3143 |
| projection | climatology | 2025 | 21789 | 2025-08-27 | 30 | 1719 | 2416 |
| projection | climatology | 2025 | 21789 | 2025-08-27 | 90 | 1719 | 2416 |
| projection | climatology | 2025 | 21789 | 2025-08-27 | 180 | 1719 | 2416 |
| projection | glofas_raw | 2024 | 3171 | 2024-08-08 | 30 | 3013 |  |
| projection | glofas_raw | 2024 | 3171 | 2024-08-08 | 90 | 3013 |  |
| projection | glofas_raw | 2024 | 3171 | 2024-08-08 | 180 | 3013 |  |
| projection | glofas_raw | 2025 | 21789 | 2025-08-27 | 30 | 8566 |  |
| projection | glofas_raw | 2025 | 21789 | 2025-08-27 | 90 | 8566 |  |
| projection | glofas_raw | 2025 | 21789 | 2025-08-27 | 180 | 8566 |  |
| projection | tft_finetuned | 2024 | 3171 | 2024-08-08 | 30 | 3046 | 3822 |
| projection | tft_finetuned | 2024 | 3171 | 2024-08-08 | 90 | 3045 | 3806 |
| projection | tft_finetuned | 2024 | 3171 | 2024-08-08 | 180 | 3008 | 3743 |
| projection | tft_finetuned | 2025 | 21789 | 2025-08-27 | 30 | 3918 | 5316 |
| projection | tft_finetuned | 2025 | 21789 | 2025-08-27 | 90 | 3975 | 5354 |
| projection | tft_finetuned | 2025 | 21789 | 2025-08-27 | 180 | 4019 | 5354 |
| projection | tft_scratch | 2024 | 3171 | 2024-08-08 | 30 | 2601 | 3300 |
| projection | tft_scratch | 2024 | 3171 | 2024-08-08 | 90 | 2598 | 3280 |
| projection | tft_scratch | 2024 | 3171 | 2024-08-08 | 180 | 2575 | 3254 |
| projection | tft_scratch | 2025 | 21789 | 2025-08-27 | 30 | 2225 | 2941 |
| projection | tft_scratch | 2025 | 21789 | 2025-08-27 | 90 | 2242 | 2974 |
| projection | tft_scratch | 2025 | 21789 | 2025-08-27 | 180 | 2211 | 2935 |
