# N-HiTS: Marala 10-day streamflow forecasts

This folder contains the N-HiTS configuration, isolated observed-discharge table, model entry points, checkpoint and actual evaluation. It is trained from scratch. The shared implementation is in `../time_series_mlp/`; each model's data and artifacts remain in its own folder.

The computational blocks and interpolation basis are copied from [Nixtla NeuralForecast](https://github.com/Nixtla/neuralforecast) at the pinned revision in [source provenance](../time_series_mlp/source_reference/provenance.json). The upstream Apache-2.0 license is retained. The three stacks use pooling kernels 16/4/1 and forecast downsampling 4/2/1, with one block each and 64-unit MLP layers. The finest stack preserves daily resolution. This is an adaptation of the published architecture to this project's masked data, not a claim that a globally pretrained N-HiTS model was used.

All predictions cover leads 1-10. History covers 365 days of observed discharge, eight existing dynamic inputs, their missing indicators, calendar features, and historical ERA5 rain/temperature in the same normalization as future weather. Future input is only rain/temperature plus their indicators. N-HiTS interpolation constructs the forecast basis; it never fills missing observed discharge.

Train: 2016-2020; validation: 2021; test: 2022-2024. Seed 42, up to 40 epochs, validation patience 7, batch 64, learning rate 0.0005, AdamW, weight decay 0.0001 and dropout 0.1. A single configuration was frozen before training; no HPO sweep or test-driven retry is used. Quantiles are trained with masked pinball loss in normalized log-flow space; sorting the summed block outputs enforces ordering.

`data/marala_daily.csv` is a byte-identical copy of `../data/marala_daily.csv`, with its SHA256/source recorded in `data/provenance.json`. Every observed discharge and NaN is preserved. Targets are excluded individually when missing; only all-missing target windows are skipped, apart from history/calendar/split boundaries. Missing predictor values use training means inside tensors plus missing indicators. No validation/test normalization is fitted.

Run from the parent `model` directory:

```powershell
$py = '../experiments/marala_observed/.venv/Scripts/python.exe'
& $py -m unittest discover -s N-HiTS/tests -v
& $py N-HiTS/train.py --config N-HiTS/config.yaml
& $py N-HiTS/evaluate.py
```

Choose a new `training.output_dir` before another run; existing checkpoints are protected from overwriting. Training can continue a compatible checkpoint with `--checkpoint path/to/best.pt`, using `finetuning` learning rate/epochs and output directory. Inherited training/selection years are excluded from later test evaluation. Change paths, year ranges, model size, dropout, quantiles, seeds, horizon and learning rate in config. Keep input meaning/order and context/horizon compatible when loading old weights.

The matched-input LSTM is in `controls/lstm/`, trained with `config_lstm_control.yaml`. It receives exactly the same predictor channels, target windows, weather noise and quantiles. The original weather-only LSTM and other old models are context comparisons because they have different predictors. N-HiTS uses past discharge; any apparent improvement cannot automatically be attributed to architecture when comparing with that older model.

Eight N-HiTS correctness tests passed, including exact agreement with the pinned upstream computational block. These synthetic tests do not establish accuracy. Actual results follow below and in `RUN_RESULTS.md`; shared commands/run status are in `../time_series_mlp/`.

Known limits: one seeded run, a short record, few independent flood events, regulation and daily reading times. Test years were inspected by earlier experiments. Future weather uses realized ERA5-Land plus artificial noise, not issued TIGGE/GFS forecasts, so operational accuracy is unverified. Non-crossing quantiles do not guarantee calibrated intervals. A new forecast archive requires matching input units and a compatible reference configuration/checkpoint for the evaluator's paired-weather check.

<!-- REAL_RESULTS -->

## Actual observed-test results

| model | lead_day | n | NSE | KGE | PBIAS_pct | RMSE_cumecs | MAE_cumecs | peak_MAPE_pct |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| NHITS | 1 | 1084 | 0.890 | 0.933 | -1.088 | 259.674 | 135.020 | 19.687 |
| NHITS | 5 | 1080 | 0.797 | 0.898 | 0.624 | 352.695 | 207.712 | 22.947 |
| NHITS | 10 | 1075 | 0.704 | 0.849 | 1.932 | 425.593 | 248.540 | 28.709 |

| group | n | NSE | KGE | RMSE_cumecs | MAE_cumecs | PBIAS_pct |
| --- | --- | --- | --- | --- | --- | --- |
| flood | 51 | -2.989 | -0.030 | 1091.647 | 864.918 | -18.912 |
| non_flood | 1024 | 0.668 | 0.767 | 361.661 | 217.842 | 6.070 |

These use noisy future reanalysis; operational forecast accuracy is unverified. Full files are in reports/initial/.
