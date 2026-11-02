# Nearby-gauge regression evaluation

Checked 30 October 2026 against `nearby_regression.py`.

## Result

The implementation passed all five automated test groups (including separate lag-0, lag-1 and lag-2 cases). Actual Marala accuracy is not yet measurable: no `nearby.csv` or identified nearby-gauge daily discharge series was found in the workspace. Marala observation files exist, but a second observed gauge is required. The historical WAPDA workbook also contains gauges on other rivers; those are not automatically suitable Chenab proxy gauges. No substitute gauge, modeled series, or duplicate Marala series was used to invent evaluation results.

| Test | Outcome |
|---|---|
| Known log-linear relationships with lags 0, 1 and 2 | Correct lag recovered; missing values reproduced within numerical tolerance |
| Observed preservation | Original positive and zero observations preserved; provenance and observation masks correct |
| Unrelated nearby gauge | Every season rejected by the NSE threshold; no missing values filled |
| Missing nearby predictor | Marala gaps remained missing |
| NSE, original KGE, percent bias and peak MAPE formulas | Exact known-answer checks passed; undefined cases returned NaN |
| Duplicate dates, negative discharge and infinite discharge | Rejected |

Test command, from the project root:

```powershell
& 'riverine flood/short range/experiments/marala_observed/.venv/Scripts/python.exe' qa/test_nearby_regression.py
```

These tests establish implementation behavior, not real-world predictive accuracy. A perfect synthetic relationship has perfect synthetic scores by construction.

## Actual-data evaluation still needed

Provide the nearby gauge name and its observed daily file (`date,q_cumecs`). Run the existing script against that series and an observed Marala series. Missing days must remain missing in the evaluation targets; exclude interpolated or modeled Marala values. Preserve measurement-basis information when deciding which Marala observations to use: IRSA daily means and FFD point readings are not identical targets.

The script selects the lag and estimates seasonal coefficients outside the hidden 30-day blocks. It reports blocked-validation NSE, KGE, bias and peak MAPE for each season, along with validation coverage. A season needs NSE at least 0.8 to permit filling. This is a gap-reconstruction validation, not a future-flow forecasting evaluation. Its single random split and potentially small seasonal/high-flow samples limit confidence; report held-out counts and repeated blocked results before relying on it operationally. Acceptance on validation data should subsequently be checked on untouched observed periods.

Peak MAPE is evaluated on held-out observed flows above the training season's Q95. It measures high-flow day errors, not event-peak timing. Positive percent bias means overprediction. NSE is not a percentage accuracy. Real seasonal scores remain **unavailable**, rather than zero or any synthetic-test value.
