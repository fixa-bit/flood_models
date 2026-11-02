# Encoder-decoder LSTM (seq2seq), 7-15-day range

This folder trains a distinct **15-day whole-horizon seq2seq** model. A 365-day
encoder hands its hidden/cell states to a forecast LSTM. One forward call returns
all leads 1-15 and five ordered quantiles (P05, P25, P50, P75, P95). Days **7-15**
are reported separately, so the same weights also supply a 7-day prefix.
The decoder consumes future weather, without teacher-forced future discharge or
recursively fed predicted discharge.

Actual results are written to [RUN_RESULTS.md](RUN_RESULTS.md) after both training
stages and evaluation finish. Source selection is in
[pretrained_search.json](pretrained_search.json).

## Pretrained model used

A compatible local checkpoint exists at
`../pretrained_multibasin_lstm/runs/pretrained/seed_42/best.pt`. It was trained in
this workspace on eight observed snow-influenced CAMELS-US basins, using 1985-1994
for fitting and 1995-1996 for selection. It is a donor-only model, rather than a
Marala-trained checkpoint or official global foundation model.

The pretrained architecture has separate encoder/decoder LSTMs (hidden size 32),
the same rainfall/temperature meaning, missing indicators, history calendar
features and ordered quantile head. We preserve recurrent/head weights and the
first ten lead embeddings. Five additional lead embeddings start as copies of
day 10. Two new historical inputs, observed log discharge and its missing flag,
start with zero encoder weights; calendar weights move to their new columns.
All parameters are then fine-tuned. The parent is copied and never overwritten.
Tests establish that the adapted network reproduces the parent's first ten leads
before normalization is changed and fine-tuning begins.

The [public global Fine Flood Forecasts model](https://github.com/EmilRyd/Fine-Flood-Forecasts)
was also reviewed; its [paper](https://ccai-papers.s3.us-east-1.amazonaws.com/iclr2025/50/paper.pdf)
describes a single next-day prediction. The compatible local encoder-decoder is
used here instead. A matching network is trained from scratch to measure transfer.
This is not an assertion that no public seq2seq checkpoint exists anywhere.

## Data and split

- Derived input: `data/marala_daily.csv`, using the existing observed-only Marala
  discharge and ERA5-Land rain/temperature, 2015-2024. Original data are read-only.
- Train 2016-2020; validation 2021; test 2022-2024. Every target date remains
  inside the assigned whole-year partition. Early 2015 provides historical context.
- No target filling, regression estimates or GloFAS targets. Missing discharge is
  masked individually in loss and scores. Past observed discharge is a causal
  encoder input, with missing indicators; future observed discharge is never input.
- Normalization uses Marala training years only. Recomputing donor normalization
  changes coordinates and requires the transferred weights to readapt.
- Future weather currently uses realized ERA5-Land plus reproducible artificial
  noise, since archived forecasts are unavailable. Noise is **not** a genuine
  meteorological ensemble. This training/operations mismatch limits interpretation.
- CPU, seed 42, 60-epoch cap and patience 12; fine-tuning LR 0.0003, scratch LR
  0.001. Best validation masked quantile loss selects each checkpoint. Deployment
  selection between alternatives also uses validation only.

## Train and evaluate

Run from the parent `model` directory:

```powershell
$python = '../experiments/marala_observed/.venv/Scripts/python.exe'
& $python -m unittest discover -s encoder_decoder_lstm/tests -v
& $python -u -m encoder_decoder_lstm.train --config encoder_decoder_lstm/config.yaml
```

The training command prepares a separate dataset, copies/adapts the pretrained
checkpoint, fine-tunes it, trains the matched scratch control, selects by validation
loss and evaluates held-out observations. `--resume` reuses completed stages.
For another experiment choose new training/finetuning output directories, prepared
data file and report directory. Existing trained weights are preserved by default.

To regenerate evaluation with existing weights:

```powershell
& $python -m encoder_decoder_lstm.evaluate --config encoder_decoder_lstm/config.yaml
```

## Saved artifacts

```text
pretrained/camels_us_original_10day.pt
pretrained/camels_us_adapted_15day.pt
pretrained/transfer_manifest.json
data/marala_daily.csv
data/preparation_report.json
runs/finetuned/seed_42/best.pt
runs/scratch/seed_42/best.pt
runs/*/seed_42/{config.yaml,normalization.json,years.json,history.json}
runs/{stages.json,selected_model.json,source_hashes.json,artifact_manifest.json}
reports/initial/predictions.csv.gz
reports/initial/scores_by_lead.csv
reports/initial/scores_monsoon_by_lead.csv
reports/initial/scores_leads07_15.csv
reports/initial/mean_scores_leads07_15.csv
reports/initial/transfer_comparison.csv
reports/initial/quantile_calibration.csv
reports/initial/verification.json
reports/initial/skill_by_lead.png
reports/initial/monsoon_*_lead15.png
training.log
requirements-lock.txt
RUN_RESULTS.md
```

Evaluation compares fine-tuned/scratch seq2seq, persistence and training-day
climatology on identical issue dates. It reports KGE, NSE, MAE, RMSE, peak MAPE,
POD/FAR/CSI/Brier at training Q95, and P05-P95 coverage. These statistical thresholds
are not official flood categories. No conceptual HBV model is retrained for this
15-day experiment. Single-seed transfer gains and uncertainty calibration are
reported as measured, without assuming pretraining must help.

## Reload and predict all 15 days

History CSV needs `date,precipitation_mm,temperature_c,q_cumecs` for at least the
365 consecutive days through issue. Canonical `rain_era5_mm` is accepted as the
rainfall column. Missing historical values get training-mean inputs plus missing
flags; discharge observations themselves are never filled in the source table.

Forecast CSV needs exactly fifteen dated rows starting issue+1 with
`date,precipitation_mm,temperature_c`; optional `available_at` timestamps are
checked against the end-of-issue-day UTC cutoff. A historical replay or synthetic
weather fixture must not be described as an archived issued forecast.

```powershell
& $python -m encoder_decoder_lstm.predict `
  --history path/to/history.csv `
  --forecast path/to/forecast_15days.csv `
  --issue-date 2026-10-30 `
  --output encoder_decoder_lstm/forecasts/2026-10-30.csv
```

The default checkpoint comes from validation-only selection; `--checkpoint` can
choose another saved model. Output is fifteen rows of quantile hydrographs and a
manifest retaining the reanalysis-training warning. No artificial weather noise is
added to a supplied operational forecast at inference.
