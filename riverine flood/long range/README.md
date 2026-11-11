# Long-range riverine projections (2026–2040)

This module is the climate-informed, probabilistic river-flow **projection** engine for the Chenab system to Trimmu Barrage. It is kept separate from short-range operational forecasting.

Projections are scenario-based estimates of period statistics, such as seasonal means, annual maxima and exceedance probabilities. They are **not** forecasts of discharge on a particular future day, and they never feed alerts.

**Current status (2026-11-11): first Marala projections produced. Experimental.** The chain has been built and tested:
- a Temporal Fusion Transformer with 180-day quantile output and baselines, tested on 2024–2026
- conformally calibrated P10–P90 intervals
- a storm-rainfall flood-peak model, tested on the August 2025 flood
- 2026–2040 projections from 8 NEX-GDDP-CMIP6 GCMs under SSP2-4.5 and SSP5-8.5

Results and limits are in [model/README.md](model/README.md). Trimmu is not covered yet.

The local data portal scores these models from their saved predictions and shows them under **Models → Long range**: the TFT leaderboard, predictions against observations, the flood-peak model, the projections, and each model's version history. Retraining a model and saving new predictions records a new version automatically. See [the portal README](../../data_portal/README.md#models-and-performance-analyzer).

## Contents

| Path | What it is |
|---|---|
| [docs/phase0_technical_report.md](docs/phase0_technical_report.md) | Architecture review, dataset assessment, model choice, AI-correction design, ensemble and validation plan, API/UI design, milestones and risks |
| [audit/audit_data_readiness.py](audit/audit_data_readiness.py) | Read-only coverage audit of the short-range data this module will reuse |
| [audit/data_readiness.md](audit/data_readiness.md) / [.json](audit/data_readiness.json) | Generated audit output |
| `dataset/` | Downloads for this module only, one subfolder per source |
| [dataset/era5land_marala_extension/](dataset/era5land_marala_extension/README.md) | ERA5-Land Marala forcing for 2025-01-01 to 2026-11-02, with a 2024 overlap check |
| [dataset/nex_gddp_cmip6_marala/](dataset/nex_gddp_cmip6_marala/README.md) | NEX-GDDP-CMIP6 catchment precipitation and temperature: 8 GCMs, historical 1985–2014, SSP2-4.5/SSP5-8.5 2024–2040 |
| [model/](model/README.md) | Marala TFT (forecast, climate-conditioned and projection modes), baselines, calibration, flood-peak model, 2026–2040 projections |
| `.venv/` (git-ignored) | Python 3.11 with CUDA PyTorch for training |

## Data rules

- Short-range data under `../short range/` is **read only**. Derived products from it are written here.
- Observed, reanalysis and simulated series (for example GloFAS) stay in separate files and are combined only at run time.
- No fills, synthetic values or silent fallbacks. Missing data stays missing and is reported.

## Re-run the readiness audit

The audit needs pandas. The short-range environment already has it:

```powershell
& "riverine flood/short range/experiments/marala_observed/.venv/Scripts/python.exe" "riverine flood/long range/audit/audit_data_readiness.py"
```

Unit tests: `python -m pytest "riverine flood/long range/audit"` (requires pytest).

## Next milestone

1. Independent checks of the projection chain:
   - a physical comparator (HBV with elevation bands and glaciers) run on the same bias-corrected forcing
   - more observed years, especially pre-2016 WAPDA/IRSA daily flow
2. Flood-peak model: obtain FFD/WAPDA instantaneous peaks for 2017–2026, to test the model beyond 2025 and the assumption that the PMD list is complete.
3. Regulation scenarios (upstream operations, treaty status) as a labelled scenario dimension.
4. Extend to Trimmu once year-round observations exist.
