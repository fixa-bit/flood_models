# Rolling held-out observed-year check

Each test year is kept out; alpha is chosen using the two preceding validation years, and the model is fit on earlier observed years only.

| Horizon | Test origins | Test years | Model RMSE | Climatology RMSE | Skill vs climatology | NSE |
|---:|---:|---|---:|---:|---:|---:|
| 90 days | 57 | 2020,2021,2022,2023,2024 | 120.9 | 129.9 | 0.069 | 0.958 |
| 180 days | 55 | 2020,2021,2022,2023,2024 | 85.0 | 92.5 | 0.081 | 0.954 |

Monthly origins overlap in their target windows. These rolling results are a stronger check than a single test year, but they are still a small, single-basin record.
