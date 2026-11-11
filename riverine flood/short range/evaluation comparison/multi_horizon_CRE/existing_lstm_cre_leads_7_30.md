## Existing trained LSTM CRE: all daily leads 7–30

The project's already-trained single 30-day LSTM CRE emits a forecast for every daily lead 1–30. Re-scoring its saved predictions shows it beat the matched training-only seasonal climatology by RMSE on **24/24** leads from 7 through 30.

| Lead | CRE NSE | Climatology NSE | CRE RMSE (m³/s) | Climatology RMSE (m³/s) | N |
|---:|---:|---:|---:|---:|---:|
| 7 | 0.855 | 0.782 | 298.2 | 365.9 | 1067 |
| 14 | 0.862 | 0.791 | 291.3 | 358.8 | 1067 |
| 21 | 0.860 | 0.791 | 293.7 | 359.1 | 1064 |
| 30 | 0.858 | 0.792 | 297.6 | 359.4 | 1055 |

**Important:** this existing LSTM CRE is not the Ridge POC above. It has a 365-day encoder, future-weather sequence and observed-flow history. Its comparison uses noisy realized ERA5-Land weather, not archived forecasts available at issue time. The 2022–2024 comparison years have also been inspected in earlier project work. This confirms the model can produce useful hindcast scores across those leads under the proxy setup; it does not prove operational skill or prove one architecture is universally better.
