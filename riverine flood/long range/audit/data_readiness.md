# Long-range projection: data-readiness audit

Generated 2026-11-10T11:13:34Z by `audit/audit_data_readiness.py` (read-only over short-range data).
Counts are valid daily values after the source's own eligibility flags. Nothing was filled or merged.

| Series | Kind | Independent truth | First | Last | Valid days | Complete years (>=90%) | Flood-season only | Days in 1985-2014 | Days in 2015-2025 |
|---|---|---|---|---|---:|---|---|---:|---:|
| marala_inflow_wapda | observed | yes | 2016-03-01 | 2024-12-19 | 3209 | 8 (2017-2024) | no | 0 | 3209 |
| marala_inflow_sindh_rim | observed | yes | 2024-07-19 | 2026-11-03 | 735 | 1 (2025-2025) | no | 0 | 479 |
| marala_outflow_sindh_rim | observed | yes | 2024-07-19 | 2026-11-03 | 735 | 1 (2025-2025) | no | 0 | 479 |
| trimmu_inflow_ffd | observed | yes | 2024-06-25 | 2026-10-15 | 350 | 0 | yes | 0 | 228 |
| trimmu_outflow_ffd | observed | yes | 2024-06-25 | 2026-10-15 | 350 | 0 | yes | 0 | 228 |
| qadirabad_inflow_ffd | observed | yes | 2024-06-25 | 2026-10-15 | 350 | 0 | yes | 0 | 228 |
| khanki_inflow_ffd | observed | yes | 2024-06-25 | 2026-10-15 | 350 | 0 | yes | 0 | 228 |
| marala_glofas_v5 | simulated | no | 1980-01-01 | 2026-08-31 | 17045 | 46 (1980-2025) | no | 10957 | 4018 |
| marala_precip_chirps_v3 | satellite_gauge_blend | no | 1990-01-01 | 2026-09-30 | 13422 | 36 (1990-2025) | no | 9131 | 4018 |
| marala_precip_era5 | reanalysis | no | 1980-01-01 | 2024-12-31 | 16437 | 45 (1980-2024) | no | 10957 | 3653 |
| marala_tas_era5land | reanalysis | no | 1980-01-01 | 2024-12-31 | 16437 | 45 (1980-2024) | no | 10957 | 3653 |
| marala_swe_era5land | reanalysis | no | 1980-01-01 | 2024-12-31 | 16437 | 45 (1980-2024) | no | 10957 | 3653 |
| marala_pet_era5land | reanalysis | no | 1980-01-01 | 2024-12-31 | 16437 | 45 (1980-2024) | no | 10957 | 3653 |

Event peaks: 30 published Marala flood maxima, 1970-07-02 to 2016-08-07 (PMD journal).

## Readiness verdicts

- **Marala**: physical_model_calibration = feasible; independent_validation = feasible_but_short; ai_residual_correction = experimental_only (about a decade of observations; blocked leave-one-year-out); complete observed years = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025]
- **Trimmu**: valid_days = 350; flood_season_only = True; physical_model_calibration = not_feasible; independent_validation = not_feasible (flood-season spot checks only); ai_residual_correction = disabled; complete observed years = none

## Required inputs not found locally

| Item | Status | Consequence | Action |
|---|---|---|---|
| Trimmu year-round daily inflow/outflow (any year) | missing | No calibration or independent validation possible at Trimmu. | Request daily 2000-2025 records from Punjab Irrigation Department / FFD / WAPDA. |
| Mangla inflow/outflow and Rasul (Jhelum) series | in_raw_workbook_not_extracted | Jhelum branch to Trimmu cannot be represented yet. | Extract Mangla columns from the saved WAPDA GRAPH-DG-16 workbook (2016-03 to 2024-12); request Rasul. |
| Canal/link withdrawals at Marala, Khanki, Qadirabad, Rasul, Trimmu | missing | Natural vs regulated flow cannot be separated from measurements. | Request IRSA/Punjab Irrigation canal head discharges; until then use labelled operation scenarios. |
| Trimmu (Chenab+Jhelum) contributing catchment and its forcings | missing | Climate forcing only exists for the Marala catchment. | Delineate with the same MERIT/Global Watersheds method used for Marala; rerun GEE extractors. |
| CMIP6 / NEX-GDDP-CMIP6 / CORDEX climate projections | missing | No future forcing exists locally. | Phase 2 connector (NEX-GDDP-CMIP6 on AWS open data, catchment-mean extraction). |
| ERA5-Land tasmin/tasmax | missing | Bias correction of CMIP6 tasmin/tasmax has no local reference. | Extend the existing ERA5-Land GEE extractor. |
| Pre-2016 continuous observed Marala discharge | missing | Differential split-sample testing limited to ~10 observed years. | Pursue the WAPDA/IRSA historical request already drafted in short range. |
