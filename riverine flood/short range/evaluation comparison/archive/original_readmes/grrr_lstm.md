# Marala GRRR comparison and controlled gap experiment

Run on 30 October 2026. **Selected: lagged GRRR as an input feature, with discharge gaps left as NaN. The lower-weight filling arm did not clearly win.** See [RESULTS.md](RESULTS.md) for measured results, seasonal bias/correlation/peak error, observed test scores and limits.

## Source and reach matching

Google Runoff Reanalysis & Reforecast (GRRR) is distinct from GloFAS. The [Google Research resources page](https://sites.research.google/gr/floodforecasting/resources/) links its [official access notebook](https://colab.research.google.com/drive/1FnXXSEQqU1TJhMPiNeWUTr9LnbJwZzMm). The original notebook and fetched chunks are preserved under `sources/`, with SHA-256 hashes in the source receipts. Attribute Google Research GRRR, CC BY 4.0. HydroBasins source attribution and terms: [HydroSHEDS](https://www.hydrosheds.org/products/hydrobasins).

The notebook's `model_id_8583a5c2_v0` actually ends on **2023-12-23** in the retrieved time coordinate. A direct public-bucket listing also found `distributed_model_2026_11`, with reanalysis metadata uploaded on **2026-10-28**. That release's actual time coordinate covers **1980-12-31 through 2025-12-30**. It is used for the main experiment, with the older version reported separately. No releases are spliced. There is **no 2026 GRRR coverage** here. The new release's units and daily-mean interval convention are inferred from the documented GRRR family; its own metadata do not independently confirm those conventions. This limits interpretation to a retrospective calendar-date comparison.

Nearest-outlet matching alone would select a tributary with only 2,912 km² upstream. Instead, `collect.py` selects the official HydroBasins level-12 polygon **containing the published Marala coordinate (32.67 N, 74.46 E)**: basin **4120686050**. Its upstream area is **29,080.8 km²**, 0.38% below the published Marala area of 29,192 km². The release IDs are `hybas_4120686050` and `subhybas_4120686050`. The new release's outlet coordinates independently match the old release. No observed flow score enters reach selection.

The modeled outlet is approximately **18.72 km downstream** of the station. It is a basin/reach proxy, not an exact gauge match. The unofficial outlet coordinates, containing polygon, area comparison, source ZIP, rejected nearest candidates, and version metadata are retained. Published station/area references are documented in the existing [catchment review](../../dataset/chenab_marala/processed/marala/catchment/README.md).

## Experiment design

`protocol.json` fixes thresholds before model training. The feature gate uses **2016-2021 observations only**: at least 365 paired days, overall Pearson r ≥0.5, at least three seasons with ≥60 pairs and r ≥0.3, and monthly-anomaly r ≥0.2. The GRRR feature has a fixed **two-calendar-day lag**; no lag is selected using test results. A value labeled T never enters a history feature at dates before T+2. This lag does not establish actual historical product publication availability.

Both arms are 16-unit LSTMs, with 30 days of inputs, 15 direct daily outputs, 15 epochs, Adam, and seed 42. Input features are discharge, observation flag, modeled-fill flag, seasonal sine/cosine and lagged GRRR with its availability flag. Both use the same input dimensions, initial weights, batch order, observed training normalization, forecast origins and observed scoring targets. NaN numeric inputs are encoded as standardized zero with explicit flags; missing targets never become numeric-zero observations.

Training targets: 2016-2021; validation: 2022; test: 2023-2026. Every complete target window remains inside its partition. The latest input must be observed, with at least 15 observed dates in its 30-day context. Earlier history may cross a partition boundary. Both checkpoints are selected only on **observed validation targets**.

- `nan_gaps`: discharge remains observed-only, with missing days NaN. Only observed training targets have weight 1.
- `weighted_fills`: missing discharge is experimentally estimated from seasonal affine regressions against two-day-lagged GRRR, fitted only on paired **training observations**. Predictions are clipped at zero. Fills may enter past input context and training targets at weight **0.2**. Observed values always retain weight **1** and are never overwritten. Filled validation/test values are never scoring targets or checkpoint-selection targets. No fill is allowed outside raw GRRR coverage, including all of 2026.

The pre-existing short interpolations are not used. Original observations, source files and the original baseline are unchanged. Experimental filled data remains labeled and separate. A rejected filled checkpoint is deleted; its predictions, calibration and evaluation remain as an experiment audit.

The frozen retention rule requires ≥5% validation and test RMSE reductions, a positive lower bound of a paired 95% test bootstrap interval, and no >2% deterioration by season, year, lead, high flow or sampled seasonal peaks. The bootstrap uses 2,000 paired circular 30-day blocks of the full target-date calendar, including unobserved calendar days; all leads for a target date stay together. Overall scores pool correlated origin/target/lead pairs. The uncertainty check approximates serial dependence, not independent flood-event uncertainty or training-seed uncertainty.

## Outputs

- `comparison/scores.csv`: same-date raw GRRR bias (GRRR minus observation), percent bias, Pearson r, MAE, RMSE, NSE, observed-peak error, paired-sample peak magnitude and timing. Includes overall, seasonal, year/season, split/season and source/basis summaries. Seasonal maxima/timing are restricted to identical paired dates and are **not complete-event peak estimates**. `coverage_by_year.csv` explicitly reports unavailable 2026.
- `comparison/aligned_daily.csv`: elapsed calendar dates in 2016-2026, retaining all original NaNs and source/basis fields; values for 2016 January-February are GRRR-only, not invented observations.
- `comparison/v0_seasonal_scores.csv`: older release, kept separate.
- `experiment/experimental_daily.csv`: unchanged observations, experimental fills, flags, GRRR source dates and training weights.
- `experiment/predictions_observed_days.csv`: one row per common observed scoring key with both arm predictions and persistence; no filled truth rows.
- `experiment/scores.csv`: lead, season, year, source/basis, GRRR availability and high-flow scores. High flow is the observed training 95th percentile, a diagnostic rather than an official warning threshold.
- `experiment/sampled_peak_scores.csv`: observed-date seasonal maxima and peak-day errors by year and lead.
- `experiment/report.json`: history, calibration, normalization, counts, hashes, frozen decision rule and bootstrap interval.
- `experiment/selected_model.json` and `nan_gaps.pt`: selected retrospective research model and preprocessing metadata. No deployment or operational validation is implied.
- `comparison/seasonal_comparison.png` and `experiment/observed_test_rmse.png`: standalone figures.

## Reproduce

From this directory in PowerShell, using the existing experiment environment:

```powershell
$pythonPath = '../marala_observed/.venv/Scripts/python.exe'
& $pythonPath -m pip install -r requirements.txt
& $pythonPath collect.py
& $pythonPath collect_current.py
& $pythonPath compare.py
& $pythonPath experiment.py
& $pythonPath -m unittest test_experiment -v
& $pythonPath summarize.py
```

Cached source chunks are reused. `collect.py` rebuilds the documented old release first; `collect_current.py` preserves that version separately before extracting the newer release. The dependency snapshot is in `requirements-lock.txt`.

Observed Marala mixes WAPDA dated readings with mostly unconfirmed times, FFD/PMD point readings and a few IRSA means. Calendar-date pairing cannot harmonize those measurements with daily modeled means. Global GRRR training overlap with local held-out years is unverified. The new release lacks confirmed interval documentation; the modeled outlet differs from the gauge. Historical issue-time availability is unverified. Results support a research feature experiment, not operational warning reliability. Both main arms contain GRRR, so their comparison establishes the effect of filling only, not a matched ablation of GRRR's incremental forecasting benefit.
