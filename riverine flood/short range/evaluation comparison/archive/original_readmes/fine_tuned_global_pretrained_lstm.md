# Fine-tuned global pretrained LSTM

This folder contains an actual published global LSTM, its original weights and normalization, Marala predictors and basin attributes, local fine-tuning code, checkpoints, and an observed-only comparison with the previously trained local LSTM. The older `../pretrained_multibasin_lstm` eight-US-basin experiment is separate.

The source is the [Fine Flood Forecasts authors' Caravan model](https://huggingface.co/EmilRyd/caravan_model), with 6,375 pretraining basins reported in its published config, trained in 2001-2020. Revision: `43f1ab45d2c3678e728b552919b898824e5f1069`. See the [authors' code](https://github.com/EmilRyd/Fine-Flood-Forecasts) and [paper](https://arxiv.org/abs/2504.12559). Download URLs, sizes and SHA256 hashes are in [pretrained/download_receipt.json](pretrained/download_receipt.json).

## What was fine-tuned

The original NeuralHydrology 1.11.0 CudaLSTM has 256 hidden units, 365 daily input steps, 14 dynamic predictors, 51 static attributes, a linear 51-to-10 static embedding, and a deterministic runoff-regression head. All eight published parameter tensors are loaded exactly, including the recurrent layers, static embedding and head. Only two zero-initialized missing-indicator adapters are added. This is a genuine transfer of trained weights, not training a new model from scratch with a similar name.

The parent was trained as a daily rainfall-runoff simulator. Here its recurrent state after 365 days is continued for ten weather-driven future steps using the same recurrent layer and output head. This is a local 10-day adaptation of that global simulator, not a published pretrained 10-day encoder-decoder. Quantiles and 90% interval calibration are unavailable from this deterministic head; no artificial intervals are reported.

Local training uses 2016-2020, validation uses 2021, and comparison uses 2022-2024. These test years are later than the global pretraining cutoff, and the code rejects a validation/test period overlapping global training. The published global validation period was 1981-1990. The separate Google FloodHub global checkpoint was not selected: its published training extends through 2023, overlapping this project's comparison period, and its original seven-day forecasting inputs differ substantially.

## Data and source preservation

- [data/marala_global_daily.csv](data/marala_global_daily.csv): original observed discharge and NaNs, plus the global model's daily predictors. Original discharge: `../data/marala_daily.csv`.
- [data/marala_static_attributes.csv](data/marala_static_attributes.csv): one Marala row with all 51 required attributes. Source coverage and derivations: [data/static_attribute_provenance.csv](data/static_attribute_provenance.csv).
- `data/raw/era5land_daily/2015.csv` through `2024.csv`: 3,653 downloaded daily ERA5-Land catchment averages. Units and checksums: [data/raw/download_receipt.json](data/raw/download_receipt.json).
- [data/raw/hydroatlas_intersections.json](data/raw/hydroatlas_intersections.json): raw HydroATLAS level-12 attributes and catchment-intersection area weights. Catchment area is approximately 28,794 km2. Climate statics use existing 1981-2020 weather only.
- [data/preparation_report.json](data/preparation_report.json): feature order, hashes, units/source mapping and exact observed-target preservation check. All 3,454 observed targets in the full source table and all 13,636 target NaNs are preserved, including later years outside this comparison.

No discharge is interpolated, filled, rescaled on disk or replaced. Conversion from cumecs to runoff mm/day is performed only in training tensors, then inverted for predictions. Samples are excluded only when every future target is missing, apart from calendar/history/split boundaries. Partial targets are masked before loss arithmetic. Original global feature/target normalization is retained; no validation/test statistics are fitted. Missing predictors use a normalized global-mean value and separate indicator channels.

Radiation inputs are net solar and net thermal flux, not downwelling solar radiation. Pressure is kPa, temperatures are Celsius, snow water equivalent and rain/PET are mm, and radiation is W/m2. The weather extraction uses UTC daily aggregates; the original Caravan preprocessing uses local days. That mismatch is recorded rather than silently treated as identical.

## Reproduce

Run from the parent `model` directory using the existing environment:

```powershell
$py = '../experiments/marala_observed/.venv/Scripts/python.exe'
& $py -m unittest discover -s fine_tuned_global_pretrained_lstm/tests -v
& $py fine_tuned_global_pretrained_lstm/finetune.py --config fine_tuned_global_pretrained_lstm/config.yaml
& $py fine_tuned_global_pretrained_lstm/evaluate.py --config fine_tuned_global_pretrained_lstm/config.yaml
```

The completed checkpoint is protected against overwriting. Set a new `training.output_dir` in a copied config before another run; keep `evaluation.output_dir` separate too. For an exact fresh run, use a new output directory with the same seed and settings. The saved config and normalization are alongside each checkpoint.

The default run uses seed 42, up to 25 epochs, batch size 32, recurrent learning rate 0.00001, embedding/head/adapters learning rate 0.00005, weight decay 0.00001, clipping 1, validation patience 5, and two CPU threads. Every sample reads all 365 days; training gradients span the most recent 60 history days plus the ten future steps to reduce CPU cost. Earlier history still initializes the hidden/cell state. Validation and evaluation process the full sequence without gradient truncation.

Downloads and preparation have already been run. Their separate commands, if rebuilding in a new folder, are:

```powershell
& $py fine_tuned_global_pretrained_lstm/download_pretrained.py
# Earth Engine must be authenticated for the project in extraction.json.
$eePy = '../dataset/chenab_marala/raw/marala/rainfall/google_earth_engine/.venv/Scripts/python.exe'
& $eePy fine_tuned_global_pretrained_lstm/download_data.py
& $py fine_tuned_global_pretrained_lstm/prepare_data.py --config fine_tuned_global_pretrained_lstm/config.yaml
```

Preparation refuses to overwrite the prepared daily/static files. Downloads resume verified existing years; downloaded parent tensors/scalers are protected against mismatched replacement. See [RUN_RESULTS.md](RUN_RESULTS.md) for the executed commands and real run details.

## Retraining and new basins

Copy the config, choose a new basin ID and daily/static CSV paths, provide the same 14 predictors in the same physical units and the same 51 named attributes, and choose new chronological train/validation/test years and output folders. Static input order is alphabetically sorted, as in the original NeuralHydrology loader; dynamic order is the original config order. Catchment area must be known because it converts runoff to discharge. The current dataset selects one basin for local fine-tuning, while the unchanged parent weights remain global.

`freeze_recurrent` and `freeze_static_embedding` can be changed in config. By default each new local adaptation starts from the published parent. To continue an adapted checkpoint, pass `--checkpoint path/to/best.pt` to this folder's `finetune.py`, or set `training.initial_checkpoint` in the copied config. This starts a fresh optimizer, preserves the global normalization and inherits all prior training/selection year history. Later validation cannot reuse an earlier training year, and later test years cannot reuse any training or selection year. Lower the learning rates in the copied config and use new output folders. `evaluate.py` also accepts `--checkpoint`. The shared project's `../finetune.py` is for its separate encoder-decoder architecture and cannot load this different checkpoint.

## Limits of this comparison

Both models receive the same future rain and temperature from realized ERA5-Land with lead-dependent Gaussian noise. For the global model, all other twelve future predictors are persisted from the issue day. Actual future snow/soil moisture states are never supplied. This is a stand-in forecast experiment; it does not establish operational TIGGE/GFS forecast accuracy or source-latency feasibility.

The global model has more predictors, static attributes, a larger hidden state and a different objective than the existing local LSTM (14 vs 8 dynamic inputs; 256 vs 64 units; linear-runoff MSE vs log-flow pinball). A better score would not isolate pretraining as the cause. Marala is large relative to the parent training population, with regulation/diversions, limited independent floods, and daily aggregation differences. Scores on previously inspected 2022-2024 data are held out from this run, not an untouched project-wide research holdout. Additional basins, longer observed records and a genuinely new forecast archive/test period are needed before operational conclusions.

The eight unit tests check code correctness and source integrity only. Their synthetic training test is not evidence of real predictive accuracy. No generic percentage accuracy is claimed; NSE, KGE, bias and flow errors are reported against observed discharge.

<!-- REAL_RESULTS -->

## Real Marala results

Fine-tuning improved day-10 NSE over the existing local LSTM.

Day-10 peak-flow MAPE: existing local 16.507% versus fine-tuned global 19.026%. Check flood metrics separately from overall NSE; the existing local model also has higher NSE at leads 1 and 5 in this run.

| model | lead_day | n | NSE | KGE | PBIAS_pct | RMSE_cumecs | peak_MAPE_pct |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Existing_local_LSTM | 1 | 1084 | 0.886 | 0.902 | -2.371 | 263.760 | 17.520 |
| Global_zero_shot | 1 | 1084 | -0.846 | -0.316 | -88.912 | 1062.686 | 93.946 |
| Global_finetuned | 1 | 1084 | 0.879 | 0.918 | 4.203 | 272.268 | 17.707 |
| Existing_local_LSTM | 5 | 1080 | 0.878 | 0.928 | 0.503 | 273.180 | 16.081 |
| Global_zero_shot | 5 | 1080 | -0.854 | -0.319 | -88.940 | 1065.479 | 94.109 |
| Global_finetuned | 5 | 1080 | 0.876 | 0.927 | 3.724 | 275.641 | 17.011 |
| Existing_local_LSTM | 10 | 1075 | 0.857 | 0.910 | 5.644 | 295.702 | 16.507 |
| Global_zero_shot | 10 | 1075 | -0.862 | -0.329 | -88.980 | 1067.596 | 94.569 |
| Global_finetuned | 10 | 1075 | 0.876 | 0.931 | 3.182 | 275.453 | 19.026 |

Test: 2022-2024; 1084 observed days; 10795 observed issue/lead pairs. No missing discharge was filled or scored. These are noisy-reanalysis experiments, not operational forecast accuracy.

[Full observed-only comparison](reports/initial/comparison_report.md)
