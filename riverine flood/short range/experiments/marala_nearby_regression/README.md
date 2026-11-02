# Which nearby station is suitable for Marala regression?

Evaluated 30 October 2026 using actual observed discharge. **Khanki is the best candidate for the tested seasonal log-linear regression, followed by Qadirabad. Trimmu performs poorly. None is sufficiently consistent to approve automatic Marala gap filling across seasons.** No original discharge values were changed.

## Main comparison: same-day or earlier nearby observations

The existing script permits lags 0, 1 and 2, meaning Marala on day t is estimated from the nearby station on day t-lag. All stations selected lag 0 from 2024-2025 training data. Seasonal log-linear models were fitted without the hidden targets. The table below shows July-September, the only season with substantial evaluation coverage.

| Station | Median blocked-validation NSE, 2024-2025 | Block splits with NSE >= 0.8 | 2026 holdout NSE | 2026 KGE | 2026 RMSE, m3/s | 2026 PBIAS | 2026 high-flow MAPE |
|---|---:|---:|---:|---:|---:|---:|---:|
| Khanki | 0.388 | 0/10 | 0.811 | 0.773 | 392.2 | -2.2% | 21.9% |
| Qadirabad | 0.163 | 0/10 | 0.777 | 0.758 | 425.9 | -3.1% | 21.4% |
| Trimmu | -1.262 | 0/10 | 0.336 | 0.307 | 735.6 | -9.5% | 49.3% |

The later-year July-September check contains 92 observed days per station. High-flow error is mean absolute percentage error on six held-out days above each model's training-season Q95. NSE is a model skill score, **not percentage accuracy**. Positive PBIAS means overprediction. The repeated-block numbers are medians across correlated splits, not independent flood events or a confidence interval.

Khanki narrowly meets the requested NSE 0.8 rule on the 2026 monsoon check, but fails it on all ten development block splits. That instability prevents treating it as a validated all-season replacement for Marala. Qadirabad and Trimmu fail the monsoon rule on the later-year check as well.

## Lagged retrospective reconstruction

We also tested signed lags -2 through +2 separately. A lag of -1 means **tomorrow's nearby reading estimates today's missing Marala reading**. This is permissible for reconstructing past records after both observations are available; it is not an input available for a current-day forecast.

| Station | Highest descriptive correlation across all paired dates | Lag | Selected reconstruction lag from development data | Monsoon median blocked NSE | Monsoon 2026 NSE |
|---|---:|---:|---:|---:|---:|
| Khanki | 0.836 | -1 | -1 | 0.373 | 0.729 |
| Qadirabad | 0.930 | -1 | -1 | 0.118 | 0.773 |
| Trimmu | 0.396 | -2 | -2 | -1.182 | 0.552 |

**Qadirabad has the strongest lagged raw correlation**, but correlation does not establish accuracy of the requested log-regression. Lag selection by training correlation and log-space fitting do not directly optimize errors in original discharge units, particularly at peaks. Adding negative lags did not produce a model that consistently passed the NSE threshold. No alternate model was tuned on the 2026 results.

## Other seasons

Each later-year October-March and April-June score uses only **13 dates**: October and June respectively. The collection contains no November-May observations. For the original nonnegative-lag model, 2026 NSE values are:

| Station | October-March (October only) | April-June (June only) |
|---|---:|---:|
| Khanki | -0.096 | -0.337 |
| Qadirabad | -0.505 | -0.844 |
| Trimmu | -1.837 | -4.035 |

All fail the NSE 0.8 rule. October has no evaluable 30-day-block development split under the sampling used. June has only two; no year-round or winter suitability can be inferred. Insufficient evidence is not counted as approval.

## Would these files actually recover missing Marala days?

The existing combined observed-priority Marala calendar contains 427 dates with no selected observation before short-gap interpolation. At the selected lag 0, **each nearby station adds zero observations on those missing dates**: the FFD station records largely share Marala's reporting dates. These datasets therefore cannot recover the missing 2016-2023 records or long off-season gaps.

Using later observations at the selected negative lags provides predictors on seven currently missing dates for Khanki/Qadirabad or ten for Trimmu, before any seasonal accuracy gate. These are candidate short gaps, not approved estimates, and no values were filled. See `results/missing_day_predictor_availability.csv` for dates. Earlier `data/daily_observed_priority.csv` has seven interpolated values in a separate column; these were not counted as observations or used as evaluation targets.

## Method and saved evidence

- Extracted Marala inflow from the exact same 363 official FFD source snapshots as the nearby stations, matching observation basis and 06:00 Pakistan time. Used only the 350 eligible observed dates; excluded the 13 archive/printed-date conflicts. Both target and predictors are observations, not interpolation or GloFAS.
- Required identical target dates across all stations and tested lags for fair comparison: 311 dates remained, with 193 in 2024-2025 and 118 in 2026. These include 258 July-September dates in total.
- Ten reproducible development splits use two disjoint fully observed 30-calendar-day target blocks each. This hides 60 of 228 observed development dates (26.3%, the nearest whole-block count to 20%). Some hidden dates lack all lagged predictors and cannot be scored; all scored counts and exact blocks are saved.
- Chose lags using development training observations only, separately within each split. Fitted `log(Q_Marala) = a + b log(Q_nearby)` by season, with at least ten training pairs. Evaluated in original m3/s after exponentiation, without bias correction or model changes. The held-out 2026 fits and lags used 2024-2025 only.
- Original sources and nearby CSVs were not moved or modified. This is a gap-reconstruction study with contemporaneous/later observations, not a verified forecast backtest. More data, especially extreme events and full-year gauge records, are needed before operational use.

`results/seasonal_scores.csv` contains every fold and season, coefficients, lag, train/test counts, NSE, KGE, PBIAS, RMSE/MAE, peak error and threshold decisions. `heldout_predictions.csv` contains every prediction and observation with target and predictor dates. `blocked_validation_summary.csv`, `descriptive_lag_correlations.csv`, `validation_blocks.csv`, `marala_observations_with_provenance.csv`, `marala.csv` and `evaluation_metadata.json` preserve the full evaluation trail. `validation_checks.json` records successful independent metric, date, lag, source and block checks.

Reproduce from the workspace root with the existing Python environment containing pandas, numpy, scikit-learn, beautifulsoup4 and pymupdf:

```powershell
& 'riverine flood/short range/experiments/marala_observed/.venv/Scripts/python.exe' 'riverine flood/short range/experiments/marala_nearby_regression/evaluate.py'
```

Recommendation: retain **Khanki as the first candidate for further model development** and **Qadirabad as a secondary, lagged reconstruction candidate**. Do not apply automatic fills using these results; the requested NSE >= 0.8 acceptance is not stable across held-out blocks or seasons. Keep all observed records and station folders intact.
