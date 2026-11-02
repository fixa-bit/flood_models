# Marala observed-priority experiment

Separate working dataset and experiment, prepared 30 October 2026. Existing source datasets remain untouched.

## Files and selection

`data/daily_observed_priority.csv` has a complete calendar from 2016-03-01 through 2026-10-23. There are 3,462 observed values (3,215 WAPDA, 239 FFD/PMD, eight IRSA), seven interpolated values and 420 remaining missing values. Missing numeric values are literal `nan`.

Observed daily inflow candidates take precedence over any modeled or interpolated value. Among observed candidates the deterministic priority is WAPDA, then FFD/PMD, then IRSA. WAPDA's zero is excluded. Unresolved FFD printed/archive date conflicts are excluded; conflicting values within the highest-priority source are also excluded. Other cross-source disagreements retain WAPDA and are recorded in `data/source_conflicts.csv`. This differs from the old conservative clean file, which withheld six WAPDA dates on cross-source disagreement: those six original WAPDA observations are retained here, with flags, rather than replaced by interpolation. This is a selection policy, not proof that WAPDA is correct.

IRSA daily means are included as observed values but explicitly identified by `measurement_basis`: a daily mean is not equivalent to a 06:00 point reading. WAPDA historical times mostly remain unconfirmed. Do not interpret the merged dataset as a uniform, confirmed 06:00 series. Outflow records and selected historical event maxima are excluded because they are different targets. Excluded candidates, provenance URLs/files, source conflicts, and source catalog checksum are saved alongside the data.

`observed_discharge_m3_s` preserves the selected observations with missing dates unchanged. `discharge_with_short_fill_m3_s` additionally interpolates only bounded 1-3 day gaps with endpoints in the same chronological partition and measurement basis. Longer gaps remain NaN. Interpolation uses a later observation and is retrospective; never assume it was available before that right endpoint. `observed_target_mask` excludes every interpolated value.

## Observed-only LSTM

`train.py` trains a small PyTorch LSTM once with seed 42: 30 days of inputs, 15 direct daily outputs, 16 hidden units, 15 epochs, and checkpoint selection on 2022 validation error. Train targets: 2016-2021. Validation targets: 2022. Test targets: 2023-2026. Entire target windows stay inside one partition. Earlier input context is allowed across a partition boundary, as it would be available when forecasting. Test observations are never used for fitting scalers or selecting checkpoints.

Only observed targets contribute to the masked loss. Missing input discharge is represented by standardized zero plus a missingness mask; require the latest input observed and at least 15 observed dates in the 30-day context. Seasonal sine/cosine features are included. Neither interpolated discharge nor GloFAS nor weather reanalysis enters this first baseline. Thus its results assess a discharge-history baseline, not the potential of the full meteorological feature collection. Missing target days are skipped per lead, not interpreted as zero; missing inputs are handled separately.

Outputs in `observed_only/`: selected model weights, training history, normalization parameters, input dataset checksum, per-lead validation/test MAE, RMSE and NSE, persistence comparison, and predictions exclusively on observed target days. Prediction rows identify source and measurement basis so IRSA means can be evaluated separately. These are retrospective date-level scores, not a verified operational issue-time backtest. Overlapping windows create correlated scores; event-specific evaluation remains necessary.

Reproduce from the project root in PowerShell:

```powershell
python 'riverine flood/short range/experiments/marala_observed/prepare.py'
python -m venv 'riverine flood/short range/experiments/marala_observed/.venv'
& 'riverine flood/short range/experiments/marala_observed/.venv/Scripts/python.exe' -m pip install -r 'riverine flood/short range/experiments/marala_observed/requirements.txt'
& 'riverine flood/short range/experiments/marala_observed/.venv/Scripts/python.exe' 'riverine flood/short range/experiments/marala_observed/train.py'
```

Installed dependency versions are captured in `requirements-lock.txt`. No NeuralHydrology installation is required for this initial PyTorch baseline. LSTM implementation reference: https://docs.pytorch.org/docs/stable/generated/torch.nn.LSTM.html

## GRRR follow-up

The completed [GRRR comparison and gap-filling experiment](../marala_grrr/RESULTS.md) evaluates the reach-matched 2016-2025 overlap and reports unavailable 2026 separately. Its selected model uses lagged GRRR as an input feature and retains NaN discharge gaps. Both experiment arms were scored on identical observed test pairs; lower-weight filling did not clearly improve results. GRRR is a different product from the optional GloFAS comparison.
