# Reusable observed-day model evaluation

Use this skill to compare one or more forecast prediction CSVs on the same observed test cases, including flood and non-flood days.

## Required prediction columns

- `target_date`
- `lead_day`
- `observed_cumecs`
- One numeric column containing the model's predicted discharge

The script detects the prediction column when exactly one eligible numeric column remains. Otherwise add `--prediction-column`.

## Run

```powershell
python compare_models.py `
  --predictions "LSTM=path\to\lstm_predictions.csv" "HBV=path\to\hbv_predictions.csv" `
  --lead-day 30 `
  --flood-threshold 2494.714185 `
  --output comparison.md
```

The flood threshold must be chosen from training data only (for example, the training-period 95th percentile). Predictions are aligned on target date and lead; only cases shared by every model and having an observed target are scored. The output gives overall accuracy and class-specific precision, recall, F1, support, RMSE and MAE for flood and non-flood days. Flood is the positive class; non-flood metrics treat non-flood as the positive class. Accuracy is shared across both rows because it uses both classes. The script uses Python's standard library only.

The output is a retrospective classification/flow-error comparison, not a measure of operational warning skill. Use real archived forecast inputs for operational claims.
