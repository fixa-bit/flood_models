# N-BEATSx: Marala 10-day streamflow forecasts

This folder contains the weather-aware N-BEATSx configuration, isolated observed-discharge table, model entry points, checkpoint and measured evaluation. It is trained from scratch, with shared code in `../time_series_mlp/`.

The computational blocks are copied from [Nixtla NeuralForecast](https://github.com/Nixtla/neuralforecast), pinned in [source provenance](../time_series_mlp/source_reference/provenance.json), with the upstream Apache-2.0 license retained. Three stacks use the published identity, polynomial-trend and Fourier-seasonality bases, one block per stack, 64-unit MLP hidden layers, degree 2 and harmonics 2. Historical/future exogenous weather enters the block coefficient networks, as in the published N-BEATSx default stack arrangement. This is N-BEATSx, not the original discharge-only N-BEATS.

The model reads 365 historical days and directly predicts leads 1-10. Predictors include past observed discharge, the eight existing dynamic inputs, historical ERA5 rain/temperature, calendar channels and missing indicators. Future inputs are only rain/temperature and their indicators. The exogenous variables never include observed future discharge or future snow/soil states.

Train: 2016-2020; validation: 2021; test: 2022-2024. Seed 42, up to 40 epochs, patience 7, batch 64, learning rate 0.0005, AdamW, weight decay 0.0001 and dropout 0.1. There is one frozen configuration per model and no HPO sweep or retry based on test performance. Quantile forecasts use normalized log flow and masked pinball loss, with output sorting to prevent quantile crossing.

`data/marala_daily.csv` is a byte-identical copy of the original table; see `data/provenance.json`. No discharge values or NaN locations are filled or changed. Partial target gaps are masked from loss and scoring. Predictor imputation occurs only inside tensors, using training-period statistics and separate indicators. Source files and their hashes are verified after training.

Run from the parent `model` directory:

```powershell
$py = '../experiments/marala_observed/.venv/Scripts/python.exe'
& $py -m unittest discover -s N-BEATSx/tests -v
& $py N-BEATSx/train.py --config N-BEATSx/config.yaml
& $py N-BEATSx/evaluate.py
```

To retrain, change the file paths, chronological year ranges and output directories in a copied config. Existing checkpoints are protected from overwriting. `train.py --checkpoint path/to/best.pt` continues a compatible checkpoint with the `finetuning` settings and inherited year history. Preserve feature order, window dimensions and quantiles when continuing old weights. New basins need correctly aligned inputs and a distinct basin ID; this saved evaluation compares Marala against its existing reference experiment.

A matched-input LSTM was trained separately under `../N-HiTS/controls/lstm/`. It uses the same predictor channels, periods, future weather noise and quantiles. Its learning rate differs, as frozen in advance. Earlier weather-only LSTMs have different information and are context comparisons rather than matched controls.

Eight N-BEATSx correctness tests passed, including agreement with the pinned upstream block, masking, temporal alignment and checkpoint training/loading. Synthetic tests do not establish real accuracy. Actual observed-only results follow below and in `RUN_RESULTS.md`.

Known limits: limited data, one seed, regulation, sparse independent extremes, uncertain daily observation times, and previously inspected holdouts. Weather is realized ERA5-Land with artificial forecast noise; actual operational accuracy remains unverified. Ordered quantiles are not automatically calibrated. Archived forecasts need compatible normalization/schema and a matching reference configuration/checkpoint for the paired-weather evaluation check.

<!-- REAL_RESULTS -->

## Actual observed-test results

| model | lead_day | n | NSE | KGE | PBIAS_pct | RMSE_cumecs | MAE_cumecs | peak_MAPE_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NBEATSx | 1 | 1084 | 0.883 | 0.937 | -0.462 | 268.099 | 142.175 | 21.060 |
| NBEATSx | 5 | 1080 | 0.794 | 0.876 | -2.233 | 355.067 | 211.307 | 27.740 |
| NBEATSx | 10 | 1075 | 0.718 | 0.830 | -3.913 | 415.743 | 236.153 | 32.678 |

| group | n | NSE | KGE | RMSE_cumecs | MAE_cumecs | PBIAS_pct |
| --- | --- | --- | --- | --- | --- | --- |
| flood | 51 | -4.055 | -0.011 | 1228.967 | 1007.744 | -30.628 |
| non_flood | 1024 | 0.730 | 0.857 | 325.926 | 197.724 | 1.390 |

These use noisy future reanalysis; operational forecast accuracy is unverified. Full files are in reports/initial/.
