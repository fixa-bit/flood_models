# Hybrid physics-ML: differentiable snow/water bucket + LSTM

This is a trained PyTorch hybrid model for 10-day Chenab discharge at Marala.
A differentiable snow/soil/groundwater bucket supplies six physical features to
the project's hindcast-forecast LSTM. Its measured test scores appear below.

The bucket conserves its own water inventory. **The final LSTM discharge head
is statistical and is not constrained to conserve water.** This implements the
snow-bucket-feeding-an-LSTM option, rather than the MC-LSTM architecture. It is a
custom conceptual module, not a complete HBV implementation. See research on
[differentiable hydrological hybrid models](https://hess.copernicus.org/articles/27/2357/2023/)
and the separate [MC-LSTM architecture](https://neuralhydrology.readthedocs.io/en/stable/api/neuralhydrology.modelzoo.mclstm.html)
for background. Benefit in extreme floods is measured here, not assumed.

<!-- ACCURACY_START -->
## Measured accuracy on Marala

At lead 10, hybrid NSE is **0.816**, lower than the matched-input plain LSTM (**0.857**); NSE difference: -0.0416. This single-seed experiment does not establish general improvement in extreme floods.

Observed test years: **[2022, 2023, 2024]**. Unique observed test days across leads: **1084**; observed issue/lead/target pairs: **10795**. Individual missing targets were excluded.

**These results use realized future ERA5-Land weather plus noise. They are not operational TIGGE/GFS forecast accuracy. NSE is a skill score, not an accuracy percentage.**

| model | lead_day | n | NSE | KGE | PBIAS_pct | RMSE_cumecs |
| --- | --- | --- | --- | --- | --- | --- |
| Hybrid | 1 | 1084 | 0.823 | 0.832 | 10.276 | 329.437 |
| plain_LSTM | 1 | 1084 | 0.886 | 0.902 | -2.371 | 263.760 |
| persistence | 1 | 1084 | 0.870 | 0.935 | 0.000 | 282.358 |
| climatology | 1 | 1084 | 0.784 | 0.849 | 7.793 | 363.415 |
| gradient_boosting | 1 | 1084 | 0.875 | 0.916 | 2.670 | 276.755 |
| Ensemble | 1 | 1084 | 0.891 | 0.912 | -0.231 | 258.621 |
| Hybrid | 10 | 1075 | 0.816 | 0.851 | 11.003 | 335.983 |
| plain_LSTM | 10 | 1075 | 0.857 | 0.910 | 5.644 | 295.702 |
| persistence | 10 | 1075 | 0.652 | 0.826 | 0.364 | 461.403 |
| climatology | 10 | 1075 | 0.790 | 0.850 | 8.144 | 358.575 |
| gradient_boosting | 10 | 1075 | 0.851 | 0.877 | 0.541 | 302.424 |
| Ensemble | 10 | 1075 | 0.866 | 0.916 | 4.630 | 286.462 |

### Hybrid seasonal results at lead 10

| model | lead_day | season | n | NSE | KGE | PBIAS_pct | RMSE_cumecs | MAE_cumecs | peak_MAPE_pct | peak_n | flood_hit_rate | false_alarm_rate | false_alarm_ratio |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Hybrid | 10 | Apr-Jun | 273 | 0.534 | 0.733 | 15.466 | 316.333 | 241.274 | 8.947 | 3 | 1.000 | 0.000 | 0.000 |
| Hybrid | 10 | Jul-Sep | 276 | 0.447 | 0.648 | 13.137 | 538.820 | 437.292 | 15.713 | 47 | 0.617 | 0.179 | 0.586 |
| Hybrid | 10 | Oct-Mar | 526 | 0.201 | 0.513 | -2.091 | 162.576 | 87.205 | 83.703 | 1 | 0.000 | 0.000 | NA |

### Hybrid quantile calibration

| lead_day | n | nominal_coverage | actual_coverage |
| --- | --- | --- | --- |
| 1 | 1084 | 0.900 | 0.878 |
| 2 | 1083 | 0.900 | 0.850 |
| 3 | 1082 | 0.900 | 0.839 |
| 4 | 1081 | 0.900 | 0.826 |
| 5 | 1080 | 0.900 | 0.833 |
| 6 | 1079 | 0.900 | 0.814 |
| 7 | 1078 | 0.900 | 0.821 |
| 8 | 1077 | 0.900 | 0.815 |
| 9 | 1076 | 0.900 | 0.798 |
| 10 | 1075 | 0.900 | 0.786 |

High-flow errors and flood exceedances use a training-derived peak threshold of **2494.71 cumecs** and flood threshold of **2494.71 cumecs**. Defaults use training Q95, not official flood categories or return-period floods. Positive PBIAS means overprediction. False-alarm rate = false alerts/non-exceedance days; false-alarm ratio = false alerts/all alerts.

### Training and physics checks

| seed | epochs_run | selected_epoch | validation_pinball | training_seconds | train_samples | validation_samples |
| --- | --- | --- | --- | --- | --- | --- |
| 42 | 16 | 10 | 0.081 | 234.176 | 1767 | 356 |

| seed | maximum_water_balance_residual_mm | minimum_state_or_flux_mm | forecast_missing_pct | negative_noisy_precipitation_clipped_in_bucket |
| --- | --- | --- | --- | --- |
| 42 | 0.000 | 0.000 | 0.000 | 2191 |

Maximum measured daily bucket residual: **0.00035048 mm**, within the configured **0.002 mm** tolerance.

Water balance is checked inside the conceptual bucket, including its initial water stores. Final LSTM discharge is not constrained to this balance. Internal conservation is not proof of accurate or physically correct basin runoff. Negative precipitation caused by Gaussian forecast noise is clipped only inside the physical module, and is counted above; source values are unchanged.

All 15 shared and 5 hybrid synthetic correctness tests passed. They check implementation, not real accuracy. Observed targets and their NaN positions were not modified. The saved daily-file hash matches both training checkpoints.

[Full evaluation](<reports/initial/evaluation_report.md>) | [Prediction CSV](<reports/initial/predictions.csv>) | [Training history](<runs/initial/seed_42/history.json>)

<!-- ACCURACY_END -->

## Files in this model folder

```text
config.yaml                         # Data, training, architecture and physics options
data.py                             # Shared-loader interface and physical-input checks
model.py                            # Differentiable buckets and hybrid encoder/decoder
train.py                            # Seeded training or hybrid fine-tuning
evaluate.py                         # Scores, water audit, plots and README update
tests/test_hybrid.py                 # Synthetic physical/code correctness tests
runs/initial/ensemble.json           # Selected seed checkpoint paths
runs/initial/seed_42/best.pt          # Trained hybrid weights and full normalization
runs/initial/seed_42/config.yaml
runs/initial/seed_42/normalization.json
runs/initial/seed_42/years.json
runs/initial/seed_42/history.json
reports/initial/predictions.csv
reports/initial/scores_by_lead.csv
reports/initial/scores_by_season_and_lead.csv
reports/initial/quantile_calibration.csv
reports/initial/water_balance_audit.csv
reports/initial/learned_physics_parameters.csv
reports/initial/evaluation_manifest.json
reports/initial/evaluation_report.md
reports/initial/skill_by_lead.png
RUN_RESULTS.md
```

The original source table is shared at `../data/marala_daily.csv`; it is read only.
The shared daily loader, masked loss, trainer and metric definitions remain in the
parent project. New model implementation, config, checkpoints and reports are all
in this subfolder. No extra Python packages are required beyond the parent's
`requirements.txt`.

## Physical computation

Each sample starts 364 days before issue day t. Initial snow is SWE from that
first historical day; initial soil and groundwater stores are configurable
assumptions (100 mm and 25 mm by default). They are modeled water inventories,
not discharge observations. The bucket then runs through all 365 historical days
and carries its final snow/soil/groundwater states into the 10 forecast days.
It never initializes from future SWE or discharge.

For precipitation P and temperature T, each day performs:

1. Split P into snow and rain with a smooth temperature threshold.
2. Melt at a learned degree-day rate above that threshold, capped by available snow.
3. Put rain and melt into soil storage; overflow becomes quickflow.
4. Remove temperature-based evaporation, capped by available soil water.
5. Move a learned fraction of remaining soil water into groundwater.
6. Release a learned fraction of groundwater as baseflow.

All stores/fluxes stay nonnegative. The identity checked each day is:

```text
previous snow + soil + groundwater + precipitation
    = next snow + soil + groundwater + evaporation + runoff
```

Runoff here is quickflow plus baseflow in mm/day. Six features are passed to the
LSTM: snow storage, soil storage, groundwater storage, melt, runoff and evaporation.
They use fixed physical unit scales and `log1p`, with no test statistics. Six
trainable coefficients have explicit bounds in `config.yaml`: rain/snow threshold,
degree-day factor, soil capacity, recharge fraction, groundwater recession and
evaporation coefficient. The learned coefficients are written to CSV. Their values
are not independently validated physical parameter estimates.

Historical physics uses CHIRPS precipitation, ERA5-Land temperature and initial
ERA5-Land SWE. The LSTM also receives the existing historical temperature, snow,
rainfall, radiation, dewpoint and potential-evaporation channels. Forecast physics
uses only forecast precipitation and temperature; it does not read realized
future SWE or observed future flow. ERA5 SWE/snowmelt are reanalysis products,
not independent ground snow measurements. Evaporation in the bucket is a simple
temperature-based demand, not a complete energy-balance calculation.

Gaussian forecast noise can make precipitation negative. The physical module clips
that noisy predictor to zero internally and reports how often this happened.
Original data and the shared LSTM predictor channels are unchanged. When input
data are missing, the shared training-mean values and missing indicators apply;
internal conservation then concerns those imputed predictor forcings.

The initial experiment differentiates through the full 365-day physical history
and the 10-day forecast. `physics.gradient_history_days` can shorten physical
backpropagation for a later CPU experiment while retaining full forward state
spin-up. This option does not shorten the LSTM's history. CPU
`training.flush_denormal: true` treats extremely tiny floating-point values as
zero to avoid slow subnormal arithmetic; it does not fill missing data.

## Training data and settings

The hybrid is trained from scratch on Marala, with no donor-basin pretraining.
Default splits are train 2016-2020, validation 2021 and test 2022-2024. Every target
date in a sample must stay in its partition. The hindcast length is 365, horizon
10, hidden size 64, one layer, dropout 0.15 and seed 42. Training uses masked
quantile loss on standardized log flow, AdamW, gradient clipping and early stopping
on validation loss. Quantiles are 0.05, 0.25, 0.5, 0.75 and 0.95, with positive
increments preventing crossing. All settings are in YAML.

Normalization uses training years only. Missing predictors receive transformed
training means inside model samples, with missing indicators. Missing discharge
stays NaN. Individual missing target days do not contribute to loss or metrics;
only entirely missing target windows are removed within the calendar/split limits.
No regression filling, interpolation, synthetic discharge or GloFAS targets enter
this experiment. Past discharge is off as a model input.

The reference plain LSTM checkpoint was trained earlier using the same source
table, input variables, split, normalization, hidden size and quantiles. It is
reused, not retrained after seeing hybrid test scores. Physics adds derived
features and a few coefficients, so parameter counts differ. Existing gradient
boosting and ensemble prediction files are aligned and checked against the same
observed target values before reuse. No comparison model is fitted on test data.

## Run or retrain

Run from the parent `model` directory:

```powershell
$python = "../experiments/marala_observed/.venv/Scripts/python.exe"
& $python -m unittest discover -s tests -v
& $python -m unittest discover -s hybrid_physics_ml/tests -v
& $python -u hybrid_physics_ml/train.py --config hybrid_physics_ml/config.yaml
& $python -u hybrid_physics_ml/evaluate.py --config hybrid_physics_ml/config.yaml
```

Training refuses to overwrite existing checkpoints. For another experiment, choose
a new `training.output_dir` and `evaluation.output_dir`, then adjust seed, sizes,
physics bounds or year ranges in YAML. `training.ensemble_size` and the seed list
support multiple independently trained members; evaluation averages their
non-crossing quantile predictions. The initial result uses one seed, not an unrun
ensemble. For new periods/inputs, supply a compatible control and baseline files,
or clear `evaluation.baseline_predictions` when they are unavailable.

Fine-tuning uses the same command with a hybrid checkpoint:

```powershell
& $python hybrid_physics_ml/train.py --config hybrid_physics_ml/config.yaml --checkpoint hybrid_physics_ml/runs/initial/seed_42/best.pt
```

Set a new `finetuning.output_dir` and compatible new chronological splits first.
Keep old normalization by default; if recomputing it, physical-unit conversion
buffers are refreshed as well. Freezing the hindcast LSTM is supported. Inherited
training and validation years cannot become test years. Forecast-input mode also
supports archived forecasts when a compatible input file is supplied.

The 5 hybrid tests check internal water conservation, zero-water behavior,
nonnegative stores, finite gradients, non-crossing quantiles, historical/forecast
alignment and state carryover, unchanged targets/files, and checkpoint fine-tuning
with updated normalization and frozen encoder weights. The 15 parent tests cover
the shared loader/trainer. **Synthetic tests establish code behavior, not accuracy.**

## Interpretation and known limits

Temperature and snow are basin averages; elevation bands, glacier energy balance,
routing networks, canal diversions and barrage operations are not resolved.
Initial inventories and physical coefficient bounds are assumptions. The model
can learn to ignore the added physical features, and the final neural head can
violate water balance even while the bucket's audit passes. This is not a fully
mass-conserving forecast model and is not a tested extreme-event guarantee.

The discharge record is short, independent extreme floods are sparse and forecast
windows overlap. The test years were inspected in earlier workspace experiments;
they are excluded from this run's fitting but are not a globally untouched research
holdout. Reanalysis publication latency and WAPDA observation timing also need
review for operational use. Archived weather forecasts remain unavailable, so the
reported skill does not establish real 10-day flood-warning accuracy.
