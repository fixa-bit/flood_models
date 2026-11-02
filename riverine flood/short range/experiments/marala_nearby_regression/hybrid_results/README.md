# Qadirabad next day, otherwise Khanki same day

Tested the proposed rule using existing seasonal log-linear fits and held-out observed Marala discharge. No fits were tuned and no original discharge values were changed.

The routing rule is: preserve observed Marala; for a missing day t use a Qadirabad(t+1)-based estimate if available, otherwise a Khanki(t)-based estimate, otherwise leave NaN. Routing was evaluated without the NSE gate to measure the proposal's behavior; failed validation does not authorize filling.

## Comparison on identical dates

On the same 92 observed July-September 2026 days used in the prior comparison:

| Method | NSE | KGE | RMSE, m3/s | MAE, m3/s | High-flow MAPE |
|---|---:|---:|---:|---:|---:|
| Khanki same day | 0.811 | 0.773 | 392.2 | 286.4 | 21.9% |
| Qadirabad next day, otherwise Khanki | 0.773 | 0.813 | 430.4 | 282.5 | 25.4% |

Qadirabad next-day readings were available on all 92 dates, so the combined rule never used Khanki during this monsoon check. It equals the Qadirabad-only model there. KGE and MAE improve slightly, but NSE, RMSE and high-flow MAPE worsen, and NSE is below the required 0.8.

Repeated 2024-2025 block-validation median monsoon NSE on the original identical target dates is 0.118 for the rule and 0.388 for Khanki. With additional available held-out dates included, the medians are 0.556 and 0.591 respectively; neither passes 0.8. Expanded-date comparisons have different counts for Qadirabad alone, so the original identical-date comparison remains the primary reference.

In the expanded 2026 check, the rule uses Qadirabad on 121 days and falls back to Khanki on one October day. Its NSE is -0.948 on 15 October dates, -0.545 on 15 June dates, and 0.773 on 92 July-September dates. All fail the requested threshold. This collection does not cover November-May, so no full-season claims are supported.

## Missing-day coverage

Of 427 dates without a selected Marala observation in the combined calendar, seven have a next-day Qadirabad reading. **Zero additional missing dates are supplied by the same-day Khanki fallback.** Seven available predictors do not mean seven approved fills; seasonal validation still fails. No filled dataset was created.

This is a reconstruction option only after the next-day gauge observation becomes available. Using Qadirabad(t+1) to predict Marala(t) at an issue time on day t would use future information. Any reconstructed values must remain labeled as estimates and excluded from observed-only evaluation.

## Files and limits

`seasonal_scores.csv`, `heldout_predictions.csv`, `blocked_validation_median_nse.csv`, `missing_day_predictor_availability.csv`, and `metadata.json` contain the complete comparison, routing counts and dates. `../evaluate_hybrid.py` reproduces the test using the prior saved coefficients and validation blocks. Assertions verify that the rule exactly equals Qadirabad when available and equals Khanki when falling back.

This is a post-hoc comparison on previously examined holdouts, not a new blind test. Independent confirmation needs another untouched observed period. Recommendation: keep Khanki as the first candidate for model development; do not enable the proposed availability-based switch for automatic filling under the NSE >= 0.8 requirement.
