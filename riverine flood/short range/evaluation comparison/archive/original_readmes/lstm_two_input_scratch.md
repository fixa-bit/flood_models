# Pretrained multi-basin LSTM, fine-tuned on Chenab at Marala

This folder contains a real-data transfer-learning pilot: pretrain the project's
PyTorch hindcast-forecast LSTM on eight observed CAMELS-US catchments, then
fine-tune the pretrained weights on Marala. A separate, otherwise matched network
is trained from scratch to measure whether transfer helps here.

It follows the [NeuralHydrology pretraining/fine-tuning workflow](https://neuralhydrology.readthedocs.io/en/latest/tutorials/finetuning.html).
It uses the shared PyTorch implementation in `../lstm/`, rather than claiming to
be an official NeuralHydrology pretrained checkpoint. All model weights in this
experiment were trained in this workspace.

## Files

```text
config.yaml                    # Download sources, basin list, stage config paths
config_pretrain.yaml           # Full donor training/data/model configuration
config_marala.yaml             # Full Marala fine-tuning configuration
config_scratch.yaml            # Matched from-scratch control configuration
download_data.py               # Original CAMELS archive, selective verified download
prepare_data.py                # Observed targets, unit conversion, common predictors
model.py                       # Shared hindcast-forecast LSTM import
train.py                       # Pretrain, fine-tune and scratch stages
evaluate.py                    # Observed Marala comparison, calibration and plots
data/raw/camels_us/             # Original forcing, discharge, attributes, receipts
data/camels_daily.csv           # Eight basins, common variables, observed Q or NaN
data/marala_daily.csv           # Same observed Marala targets as ../data/marala_daily.csv
data/preparation_report.json
runs/pretrained/seed_42/        # Pretrained weights, config, normalization, history
runs/marala_finetuned/seed_42/  # Adapted weights and inherited training-year history
runs/marala_scratch/seed_42/    # Independent matched control
runs/stages.json               # Paths to the three selected checkpoints
reports/initial/                # Scores, prediction CSVs, calibration, PNG and report
RUN_RESULTS.md                 # Actual commands, counts, times and key results
```

The canonical model architecture and training loop remain shared, so fixes apply
to both the original LSTM and this model without duplicating implementation code.
Each stage has its own saved config, statistics, year history and checkpoint.

## What was downloaded

Observed USGS discharge and NLDAS weather were downloaded from the original
[CAMELS-US publisher archive](https://zenodo.org/records/15529996)
([dataset DOI](https://doi.org/10.5065/D6MW2F4D), CC BY 4.0).
This uses full original station files, not synthetic data or a small tutorial fixture.
Only selected ZIP members were retrieved through HTTP byte ranges; CRC32 and
SHA256 values are recorded. The roughly 3.4 GB archive was not downloaded in full.
Publisher metadata and station names/attributes are stored with the raw files.

The donor gauges are:

| USGS gauge | Catchment |
| --- | --- |
| 13340000 | Clearwater River at Orofino, Idaho |
| 06191500 | Yellowstone River at Corwin Springs, Montana |
| 12358500 | Middle Fork Flathead River near West Glacier, Montana |
| 12414500 | St Joe River at Calder, Idaho |
| 06043500 | Gallatin River near Gallatin Gateway, Montana |
| 11528700 | South Fork Trinity River below Hyampom, California |
| 12189500 | Sauk River near Sauk, Washington |
| 13235000 | South Fork Payette River at Lowman, Idaho |

The donor selection emphasizes snow-influenced catchments, with snow fractions
above 0.25 in published CAMELS attributes, and was made before test scoring.
This is a limited US-domain donor set, not a representative global training set.
The donor record contains 3,652 observed discharge days per basin during the chosen
1985-1994 pretraining period, approximately 80 basin-years in total. Nearby donor
climates are correlated; these are not 80 independent annual flood realizations.
Original daily source files span 1980-2014.

No discharge is filled, interpolated or invented. CAMELS missing-discharge sentinel
`-999` becomes NaN; cusecs are converted to cumecs. Marala observations and NaN
positions exactly match the existing observed-only source table. Source files are
read-only during preparation/training/evaluation and their hashes are checked.

## Experiment settings

Both the transferred and matched scratch models use:

- 365 historical days and 10 future lead days;
- one encoder and one forecast LSTM, hidden size 32, dropout 0.15;
- precipitation and temperature, missingness indicators and calendar channels;
- quantiles 0.05, 0.25, 0.5, 0.75 and 0.95, structurally non-crossing;
- masked pinball loss with individual missing targets excluded;
- static attributes and past discharge disabled, seed 42.

The smaller hidden size keeps this first CPU experiment modest and is adjustable
in the stage configs. Donor NLDAS temperature is `(Tmax + Tmin) / 2`; Marala uses
ERA5-Land mean temperature and precipitation, so forcing definitions differ.
Precipitation is mm/day and temperature is degrees C in both stages.

| Stage | Train | Validation | Test |
| --- | --- | --- | --- |
| Donor pretraining | 1985-1994 | 1995-1996 | 1997-1998 reserved, not scored here |
| Marala fine-tuning | 2016-2020 | 2021 | 2022-2024 |
| Matched Marala scratch | 2016-2020 | 2021 | 2022-2024 |

Pretraining has a 10-epoch cap, learning rate 0.001 and patience 3. Fine-tuning has
a 30-epoch cap, learning rate 0.0003 and patience 6. The scratch model uses learning
rate 0.001, a 30-epoch cap and patience 6. Checkpoint selection uses validation
pinball only. No test scores are used to retry training or choose settings.

Fine-tuning recomputes normalization on Marala training years because basin flow
scales and weather products differ. The old weights are retained and allowed to
readapt; this coordinate change is explicitly warned about. Set
`finetuning.recompute_normalization: false` to retain donor statistics in a future
experiment. Training/validation year history is inherited, and evaluation refuses
test years used by either earlier stage. Inputs receive training-mean imputation
inside tensors only; target NaNs stay masked and are never imputed.

## Running and retraining

From the parent `model` directory, using the environment already available here:

```powershell
$python = "../experiments/marala_observed/.venv/Scripts/python.exe"
& $python pretrained_multibasin_lstm/prepare_data.py --config pretrained_multibasin_lstm/config.yaml
& $python pretrained_multibasin_lstm/train.py --config pretrained_multibasin_lstm/config.yaml --stage all
& $python pretrained_multibasin_lstm/evaluate.py --config pretrained_multibasin_lstm/config.yaml
```

These commands were run for the included experiment. The preparation command and
stage trainer refuse to overwrite existing datasets/checkpoints. For another run,
choose new prepared data paths and stage `output_dir` paths, plus a new manifest
and report directory. Change the basin IDs, year ranges, feature mappings, sizes
and rates in YAML; no source-code edits are required for compatible data.

To reuse an existing pretraining stage, run only fine-tuning:

```powershell
& $python pretrained_multibasin_lstm/train.py --stage finetune --checkpoint pretrained_multibasin_lstm/runs/pretrained/seed_42/best.pt
```

Point `config_marala.yaml` to a new output directory first. Keep the feature schema,
hidden sizes, quantiles and variable meaning compatible with the parent checkpoint.
Additional basin data can be appended using `basin_id` and the same columns.
For actual archived forecasts, both stages must use a compatible forecast schema;
the shared loader also supports `forecast_mode: archived_forecast`.

The scripts use the shared masked-target loader and training loop. The root test
suite includes checkpoint loading/fine-tuning, masking, alignment, non-crossing
quantiles, unchanged observations and preservation of leading-zero basin IDs:

```powershell
& $python -m unittest discover -s tests -v
```

Synthetic correctness tests are not evidence of forecasting accuracy.

## Reading the results

[RUN_RESULTS.md](RUN_RESULTS.md) records what actually ran. The full
[evaluation report](reports/initial/evaluation_report.md) compares:

- `finetuned`: the requested multi-basin pretrained model adapted to Marala;
- `scratch`: the matched two-input model trained on Marala alone;
- `pretrained_only`: donor weights applied without Marala fine-tuning;
- `original_8input_LSTM`: the earlier, larger eight-input model, for context;
- persistence and training-period climatology.

In the initial real run, day-10 overall NSE was **0.814** after fine-tuning and
**0.810** for the matched scratch model. Day-10 monsoon NSE was **0.506** versus
**0.507**, so there was no monsoon NSE improvement. The earlier eight-input LSTM
scored **0.857** overall. The new model's nominal 90% day-10 interval covered
**85.0%** of observed targets. This is a modest transfer result, with no basis for
claiming that the pilot is the best model. All 15 code-correctness tests passed.

Scores use observed test days only, per lead and season, with high-flow errors,
Q95 exceedance hits/false alarms and quantile coverage. The original eight-input
model is not a matched transfer ablation. Prediction CSVs keep observed and
predicted discharge in separate columns and can support a later ensemble analysis.

The forecast inputs are realized future weather with noise, not archived TIGGE/GFS.
Scores measure a stand-in-weather hindcast experiment, not operational 10-day
forecast accuracy. The short Marala record, regulation, donor-domain mismatch,
missing static embedding, global flow scaling, sparse independent floods and
publication latency remain limitations. The test years were inspected in earlier
workspace experiments, so they are held out from fitting here but are not a
globally untouched research holdout. No conceptual models were tested, and no
claim of outperforming them or benefiting from transfer is assumed in advance.
