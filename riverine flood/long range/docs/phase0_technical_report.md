# Phase 0 technical report: climate-informed long-range river-flow projections

**Scope:** Chenab system to Trimmu Barrage, horizon 2026–2040 (sub-periods 2026–2030, 2031–2035, 2036–2040).
**Date:** 2026-11-10. **Status:** Phase 0 (audit and design). No model was trained, no data was downloaded, and no file outside `riverine flood/long range/` was changed.

Evidence for every coverage number in this report comes from [`audit/data_readiness.md`](../audit/data_readiness.md), which `audit/audit_data_readiness.py` regenerates read-only from the short-range datasets.

---

## Summary of findings

1. **There are two codebases, not one.** The Flood Guard AI application (FastAPI + React) lives in `D:\projects\disaster_management\disaster_management`. This repository (`flood_model`) holds the research data and models. The long-range engine should be built here and **published to the app as versioned result artifacts**, the same way the app already consumes the Marala monthly outlook.
2. **The app's existing "10-Year Outlook" is a hand-authored hypothetical fixture** (`hypothetical-outlook-v2`). Its own documentation says so. The new engine should eventually give that workspace real content. Until it is validated, the two must not be merged visually.
3. **Marala is the only node with enough independent observations to calibrate and validate.** It has 9 complete observed years (2017–2025) from WAPDA and the Sindh rim-station bulletins.
4. **Trimmu has no year-round observations.** It has 350 flood-season days (FFD 06:00 readings, 2024–2026). A Trimmu projection can therefore only be an **unvalidated, scenario-labelled routing of upstream projections** until Punjab Irrigation, FFD or WAPDA records are obtained.
5. **Trimmu flow is dominated by regulation.** It combines the Chenab (after the Marala, Khanki and Qadirabad withdrawals) with the Jhelum (Mangla releases, Rasul withdrawals and the Chashma–Jhelum link), and diverts again at Trimmu itself. A live reading in the app's documentation shows Trimmu inflow of 15,359 cusecs against outflow of 1,159 cusecs.
6. **A calibrated, mass-conserving physical model already exists for Marala**: a lumped HBV in `short range/model/model_10 days/hbv_residual/physical.py`. Its reanalysis-forced test (2022–2024) gives NSE 0.73 and KGE 0.82 overall, but **NSE −1.98 on flood days**. It underestimates peaks, which matters directly for high-flow projections.
7. **GloFAS v5 is biased at Marala** (−41.6 % volume, NSE 0.45 against observations) and is not calibrated there. It may be used as a feature or comparator, never as ground truth.
8. **No climate-projection data exists locally.** There is no CMIP6, NEX-GDDP-CMIP6 or CORDEX data, and no ERA5-Land tasmin/tasmax, which is needed as a bias-correction reference.
9. **The near-term horizon limits what can be claimed.** For 2026–2040, the forced climate signal is small compared with internal variability and model spread, and SSP2-4.5 and SSP5-8.5 barely diverge before about 2040. A defensible product will mostly show a *plausible range* of 2026–2040 flow statistics. It must not imply a sharp scenario-dependent trend.

---

## 1. Current architecture and reusable components

### 1.1 Flood Guard AI application (`disaster_management/`)

| Layer | What exists (verified) | Reuse for projections |
|---|---|---|
| Backend | FastAPI app (`app/main.py`), routers under `/api/v1` (`app/api/router.py`), Pydantic schemas, service classes | Add one router, `projections`, following the same pattern |
| Database | SQLAlchemy. Default `sqlite:///./floodguard.db`; `docker-compose.yml` provides PostGIS 16. Table pattern: `model_forecast_points` | Use a separate `projection_runs` / `projection_results` table pair. Do **not** reuse `model_forecast_points`, which has `issued_at`/`valid_at` forecast semantics |
| Authentication | No authentication or security dependencies on any route (grep of `app/api` found none) | Match the current convention. Projection endpoints are read-only |
| Background work | Async refresh caches started on app startup (`upstream_forecast_cache`, `river_monitoring_cache`) | **Do not** run ensembles inside the app. Compute offline here and publish artifacts |
| Artifact-serving precedent | `app/api/routes/predictive_monthly.py` reads saved datasets and model cards and returns 503 when an artifact is missing | Same pattern: read a published, versioned projection bundle; return explicit "not available" states |
| ML | `app/ml/model.py`: `XGBoostRiskModel` named `xgboost_v1` (a risk probability from weather/river features, disabled by default via `ml_model_enabled=False`). `riverine_baseline.py` for Trimmu/Balloki is trained on **synthetic bootstrap data** (its model card says so) | Not reusable for projections. It is a different target, and its training data is synthetic |
| Live data | Open-Meteo weather and flood APIs, FFD bulletin service, Google Flood Hub, IRSA parser | Operational path only. Keep it separate |
| Stations/GIS | `app/gis/river_stations.py` defines TRIMMU (31.1448 N, 72.146 E) and the Chenab chain MARALA → KHANKI → QADIRABAD → TRIMMU → PANJNAD. Jhelum chain MANGLA → RASUL | Reuse station IDs exactly |
| Hydraulics | ANUGA Jhang pilot (explicitly not a forecast), TUFLOW Jhang trial (**withdrawn** because there is no surveyed bed), and HEC-RAS 2025 Beta tutorial replays (non-Pakistan) | No validated Chenab hydraulic model exists, so inundation mapping from projections is **not** possible now |
| Exposure | `flood_model/exposure_infrastructure`, active pilot `trimmu_jhang` | Later overlay for hazard indicators |
| Ten-year outlook | `frontend/src/components/TenYear*.tsx`, `features/ten-year-*.md`, plus a dataset audit (`features/ten-year-dataset-audit.md`) | UI shell and research notes are reusable. **Its scores are invented** and must not be mixed with engine output |

### 1.2 Research workspace (`flood_model/riverine flood/short range/`)

| Component | Location | Reuse |
|---|---|---|
| Marala catchment (MERIT/Global Watersheds, 28,781 km², verified) | `dataset/chenab_marala/processed/marala/catchment/` | Delineation method reused for the Trimmu, Mangla and intermediate catchments |
| Earth Engine extractors (ERA5-Land temperature, snow, dewpoint/SSRD, PET, MODIS snow, static attributes, elevation bands) | `dataset/chenab_marala/raw/marala/*/` | Parameterise by catchment GeoJSON; add tasmin/tasmax |
| CHIRPS v3 catchment precipitation 1990–2026 | `processed/marala/rainfall/chirps_v3_primary/` | Second reference dataset for precipitation bias correction |
| Unified daily table 1980–2026 (ERA5 and CHIRPS rain, temperature, snow, PET, observed Q) | `evaluation comparison/common/data/marala_daily.csv` | Reference forcing for HBV calibration |
| HBV physics (numba, mass-balance audited, differential-evolution calibration, 14 parameters) | `model/model_10 days/hbv_residual/physical.py` | **Core of the physical baseline.** Copy into the long-range package; do not import across modules |
| Quantile mapper | `hbv_residual/forcing.py` (`QuantileMapper`) | Starting point only. Projections need trend-preserving QDM |
| HBV + LightGBM / LSTM residual experiments | `model/model_30_days/HBV hybrids/` | Shows how residual correction was evaluated. Projection-mode features must exclude observed discharge |
| GloFAS-pretrained seasonal model | `seasonal/GloFAS_pretrained_finetuned/` | Its result (it does not beat observed climatology) is a useful caution |
| Evaluation metrics (NSE, KGE, PBIAS, flood/non-flood split) | `evaluation comparison/common/evaluate.py` | Reuse the definitions so scores are comparable |
| Python environment | `short range/experiments/marala_observed/.venv` (pandas 3, xarray, cfgrib, netCDF4, zarr, LightGBM, torch CPU, cdsapi, scipy) | Usable now. Missing: `xclim`/`xsdba`, `s3fs`/`fsspec`, `pytest` |

Not present anywhere: SWAT+, VIC, mizuRoute, xclim/xsdba, or any CMIP6 tooling.

---

## 2. Operational forecasting versus proposed projection architecture

| | Operational forecasting (existing) | Climate projection (new) |
|---|---|---|
| Question | What will the flow be on a specific date in the next 6 h to 7 days? | What range of flow *statistics* is plausible over 2026–2040 under a given scenario? |
| Inputs | Live gauges, NWP forecasts, current state | Bias-corrected GCM forcing, calibrated physical model, operation scenarios |
| Output | Dated values and warnings | Period statistics (seasonal/annual means, annual maxima, exceedance probabilities) as P10/P50/P90 with change versus a 1995–2014 or observed baseline |
| Day-to-day correspondence with reality | Yes | **No.** GCM weather sequences are not synchronised with real weather |
| Validation | Daily skill (NSE, CRPS, hit rate) | Distributional realism in hindcast; daily skill only for the reanalysis-forced hydrological core |
| Location | `short range/` and the app's live services | `long range/` and published artifacts |
| App surface | Monitoring, alerts, incidents | Planning workspace only. **Never** feeds alerts, incidents or `model_forecast_points` |

```text
             flood_model/riverine flood/long range/                      disaster_management/
 ┌─────────────────────────────────────────────────────────────────┐   ┌──────────────────────────┐
 │ source registry ─► climate connectors ─► catchment aggregation   │   │ /api/v1/projections/*    │
 │      (NEX-GDDP-CMIP6, ERA5-Land, CHIRPS)       │                  │   │  read-only, 503 if absent│
 │                                                ▼                  │   │           ▲              │
 │              bias correction (QDM, temporal validation)           │   │           │              │
 │                                                ▼                  │   │  published bundle:       │
 │  HBV-EB-G per sub-basin ─► routing + operations scenarios node   │──►│  manifest.json + Parquet │
 │  model (Marala, Mangla, intermediate)          ▼                  │   │  + model/data cards      │
 │              AI residual correction (Marala only, gated)          │   │           │              │
 │                                                ▼                  │   │  Long-Term Projection    │
 │      ensemble + uncertainty partition + validation report         │   │  workspace (frontend)    │
 └─────────────────────────────────────────────────────────────────┘   └──────────────────────────┘
```

---

## 3. Dataset availability and missing inputs

### 3.1 Available locally (measured by the audit)

| Series | Kind | Coverage | Independent truth? |
|---|---|---|---|
| Marala inflow (WAPDA) | observed | 2016-03-01 → 2024-12-19, 3,209 eligible days; daily-mean versus 06:00 basis unconfirmed | Yes |
| Marala inflow/outflow (Sindh rim-station bulletins) | observed | 2024-07-19 → 2026-11-03, 735 days | Yes |
| Marala combined | observed | 9 complete years (2017–2025) | Yes |
| Trimmu, Qadirabad, Khanki inflow (Trimmu outflow too) | observed | 350 days each, **June–October only**, 2024–2026 | Yes, but seasonal fragments |
| Marala flood peaks (PMD journal) | event maxima | 30 events, 1970–2016 | Yes, for extreme-value plausibility only |
| GloFAS v5 at Marala | simulated | 1980 → 2026-08, complete | **No** |
| ERA5 precipitation, ERA5-Land T, SWE, PET, dewpoint, SSRD (Marala catchment) | reanalysis | 1980–2024 complete | No (reference forcing) |
| CHIRPS v3 precipitation (Marala catchment) | satellite–gauge | 1990 → 2026-09 complete | No (reference forcing) |
| Static attributes: glacier fraction 11.9 %, snow/ice cover 13.8 %, mean elevation 3,021 m, four elevation bands | static | — | — |
| WAPDA workbook with **Mangla inflow and outflow** 2016–2024 | observed (raw) | Saved, **not yet extracted** | Yes |

### 3.2 Missing (searched for, not found)

| Missing input | Effect | Route to obtain |
|---|---|---|
| Year-round Trimmu inflow/outflow | No calibration or validation at Trimmu | Punjab Irrigation Department / FFD / WAPDA request (daily, 2000–2025) |
| Rasul and Mangla processed series | Jhelum branch cannot be modelled | Extract Mangla from the saved workbook; request Rasul |
| Canal and link withdrawals (UCC, MR link, LCC, QB link, LJC, RQ link, CJ link, Haveli, Rangpur, TS link) | Natural and managed flow cannot be separated | IRSA / Punjab Irrigation canal-head discharges |
| Indian upstream reservoir operations (Salal, Baglihar, Dul Hasti; Kishanganga/Uri on the Jhelum) | Unknown storage/flushing effects on Marala inflow | No public data. Represent as a labelled scenario dimension |
| Trimmu, Mangla and intermediate catchment polygons and forcings | Forcing exists only for Marala | Reuse the Marala delineation and GEE extractors |
| CMIP6 forcing (any) | No future scenario at all | Phase 2 connector |
| ERA5-Land tasmin/tasmax | Cannot bias-correct CMIP6 tasmin/tasmax | Extend the GEE temperature extractor |
| Glacier mass-balance projections | Glacier-melt trend is not represented in a lumped HBV | Candidate: published PyGEM-OGGM projections (Rounce et al., 2023). Confirm that per-basin runoff outputs are available before relying on them |
| River geometry / surveyed bathymetry near Trimmu–Jhang | No defensible inundation mapping | Survey data request; out of scope until available |
| Official FFD flood-category thresholds for Trimmu (values and effective dates) | Hazard indicators cannot use official categories | FFD |

### 3.3 Candidate climate sources (to be verified when each connector is built)

| Source | Why | Caveats |
|---|---|---|
| **NASA NEX-GDDP-CMIP6** (daily, 0.25°, historical 1950–2014, SSP2-4.5 / SSP5-8.5 2015–2100; pr, tas, tasmin, tasmax, hurs, huss, rsds, rlds, sfcWind; about 35 GCMs; public AWS bucket) | Primary forcing. Daily, all needed variables, both SSPs, open access | Already BCSD-corrected against GMFD, which is weak in high-mountain Asia, so it must be **re-corrected** to the catchment reference. Corrected file versions exist for some models; record version and per-model licence |
| CMIP6 raw (ESGF / Copernicus CDS) | Snow variables, cross-checks, models missing from NEX | About 100 km native grid; heavier access |
| ERA5-Land / ERA5 | Bias-correction reference for T, PET, radiation | Known wet bias over the Himalaya in ERA5 precipitation |
| CHIRPS v3 | Alternative precipitation reference (1990+) | Weak for high-elevation snowfall |
| CORDEX South Asia | Regional detail | Mostly CMIP5/RCP-driven, so not scenario-consistent with SSPs. Supplementary only, unless CORDEX-CMIP6 for South Asia is confirmed available |

Precipitation *reference* choice (ERA5 versus CHIRPS) changes bias-corrected projections. It is treated as an explicit ensemble dimension, not hidden.

---

## 4. Recommended hydrological model and reasoning

### 4.1 SWAT+ versus VIC for this system

| Criterion | SWAT+ | VIC 5 | Weight here |
|---|---|---|---|
| Snow | Degree-day snow with elevation bands | Energy-balance snow with elevation bands | High: SWE peaks above 1,000 mm |
| Glaciers | None native | None native (research forks only) | High: 11.9 % glacier area |
| Input data | HRUs need soil, land-use **and management** data. Indian-administered upstream areas have none locally | Global 0.0625°/0.25° parameter sets exist; forcing needs radiation, humidity and wind (available in NEX-GDDP) | High |
| Forcing robustness under GCMs | Needs mainly P and T, which are the most robust bias-corrected variables | Needs radiation, humidity and wind, whose CMIP6 biases are larger and less well constrained | Medium-high |
| Runoff/soil/ET outputs | Yes | Yes | Both fine |
| Routing | Built-in channel routing | Needs RVIC or mizuRoute | Medium |
| Regulation | Reservoir and water-allocation modules | None (coupling needed) | Medium. Trimmu operations are better handled by an explicit, auditable node model (4.3) |
| Calibration cost | High (many parameters, SWAT+ Toolbox) | High (computationally heavy, few calibration targets) | High: only ~10 observed years at one gauge |
| Installed here | No | No | — |

**Decision.** Neither SWAT+ nor VIC is the right *first* physical model for this data situation.

- **Primary physical baseline (Phase 3): HBV-EB-G.** This is an elevation-band HBV with a glacier component. It extends the HBV already calibrated at Marala and adds:
  - per-band lapse-rate temperature and precipitation gradients across the 4 existing elevation bands;
  - a glacier store per band with a simple area-scaling or Δh-parameterised retreat, constrained by published glacier projections where available;
  - outputs per sub-basin: snowmelt, glacier melt, rain runoff, soil moisture, actual ET, upper/lower storage (fast and baseflow), and total runoff.

  Reasons: it runs now, it is mass-conserving, it is already calibrated against independent Marala observations, and it is driven by the two most robust GCM variables (P and T). Conceptual degree-day models are standard in Upper Indus climate-impact studies.
- **Structural-uncertainty member (Phase 3b, conditional): VIC 5 (image driver) with mizuRoute.** Use it only if a global parameter set can be subset and a historical run reproduces the Marala seasonal cycle (KGE ≥ 0.5 uncalibrated) within the effort budget. If that gate fails, document it and use a second conceptual structure (for example GR4J with CemaNeige) for structural spread instead. **No VIC integration will be stubbed to look real.**
- **SWAT+ is not recommended** for this basin and phase. Its advantages (agricultural management, water quality, HRU detail) are not the binding constraints. Its data needs (Indian-side soil and management data) and calibration cost are.

### 4.2 Known physical-baseline weaknesses to carry forward

- Flood-day NSE −1.98 in the existing HBV test: peaks are underestimated. High-flow indicators therefore need peak-specific evaluation (annual-maximum bias) and must not inherit the overall NSE as a claim of skill.
- A lumped single-temperature model cannot represent elevation-dependent warming. This is the reason for the band extension.
- The 2016–2025 calibration window is short and may not span the climate of 2036–2040. Differential split-sample tests (§7) quantify this risk.

### 4.3 River-operations layer (Trimmu)

Represent the regulated system as an **explicit node–link water balance** rather than inside a hydrological model:

```text
Marala_in (HBV, natural) ─► [Marala: −UCC −MR link] ─► Khanki [−LCC] ─► Qadirabad [−QB link] ─┐
                                   + local inflow (Tawi, nullahs; HBV intermediate catchment)     ├─► Trimmu_in ─► [−Haveli −Rangpur −TS link] ─► Trimmu_out
Mangla_in (HBV, natural) ─► [Mangla storage rule] ─► Rasul [−LJC −RQ link (+ to Qadirabad)] ─┤
                                   + CJ link inflow + local inflow                              ┘
```

- **Natural flow** (HBV) and **managed flow** (withdrawals, storage rules) are separate stored variables.
- Withdrawals come from data where obtained. Otherwise they come from **named scenarios**: `ops_historical_median` (seasonal-median withdrawals from whatever canal data is obtained), `ops_high_diversion`, `ops_low_diversion`, and `ops_upstream_storage_shift` (an Indian run-of-river filling/flushing timing shift). Each is labelled `assumed` in output metadata. None is presented as measured.
- Routing between nodes: lag plus Muskingum, with parameters fitted only on the 2024–2026 flood-season days where Khanki, Qadirabad and Trimmu overlap. Flagged as `weakly_constrained`.
- **The 15-year horizon makes operations an irreducible scenario uncertainty**: possible new upstream storage (for example Ratle and Pakal Dul) and treaty-related operating changes after India's April 2025 decision to hold the Indus Waters Treaty "in abeyance". These are scenario dimensions only, with no invented release numbers.

---

## 5. Recommended AI correction method and baselines

### 5.1 Where correction is allowed

Only at **Marala** (and at Mangla if its inflow is extracted and validated), where independent observations exist. At Trimmu: **disabled**, because there are no observations to learn from or to test against.

### 5.2 Formulation for projection mode

`Q_corrected(t) = Q_HBV(t) + f(X(t), S(t), R(t), O(t))`

- `X`: bias-corrected forcing (P, T, rolling sums and means).
- `S`: HBV internal states (snowpack, glacier melt, soil moisture, storages).
- `R`: regime label.
- `O`: operations only where an observed or scenario series exists.
- **Excluded in projection mode:** lagged observed discharge and lagged residuals. They do not exist in the future, and using them in training would produce a corrector that cannot run.
- Training residuals come from the HBV run forced by the reference (ERA5-Land/CHIRPS). GCM runs are bias-corrected to that same reference, so feature *distributions* match. Daily sequencing does not, which is acceptable because `f` is a function of state, not of date.

### 5.3 Candidates and baselines (ablation ladder)

| # | Model | Purpose |
|---|---|---|
| B0 | Observed climatology (day-of-year) | Floor every projection model must beat in hindcast |
| B1 | HBV-EB-G alone | Physical baseline |
| B2 | HBV + flow-quantile mapping (QM of Q_sim against Q_obs) | Simplest statistical correction |
| B3 | HBV + LightGBM residual (no regime) | Conventional residual baseline |
| B4 | HBV + regime-conditioned quantile LightGBM (P10/P50/P90) | Proposed method |
| B5 | XGBoost on forcing only (no physics) | "ML alone" comparator |
| B6 | LSTM on forcing only | Temporal ML comparator. Expected to overfit with ~10 years; reported, not selected by default |

Temporal Fusion Transformer: **not recommended**. About 10 observed years at one gauge cannot support it, and published streamflow work shows no consistent gain over LSTMs.

### 5.4 Regime identification

Compare, on training years only:

1. **Rule-based hydrological regimes** from HBV states: snowmelt-dominated (melt share > x), monsoon-rain-dominated, low-flow (Q_sim < training P20), high-flow (Q_sim > training P90).
2. Gaussian mixture on (melt share, rain share, Q_sim percentile, day-of-year sin/cos).
3. Two- to four-state HMM on the same features.

Selection criteria, in this order: stability of assignments across leave-one-year-out folds, physical interpretability, and then validation gain over B3. If no regime method beats B3 out of sample, regime conditioning is **not** used, and that result is reported.

### 5.5 Leakage and extrapolation controls

- Blocked **leave-one-year-out** cross-validation, with a buffer around each held-out year longer than the HBV memory (snow/storage spin-up). The final test year(s) are never touched during model selection.
- **Differential split-sample test** (Klemeš 1986): train on the coolest/driest observed years and test on the warmest/wettest, and the reverse.
- **Extrapolation detector**: per-day Mahalanobis distance of `(X, S)` to the training cloud, plus per-feature range checks. Outside support, the corrector output is shrunk to zero (physical model only) and an `extrapolation` flag plus widened intervals are emitted. The share of projection days outside support is reported per scenario and period.
- Correction is retained only if it improves held-out CRPS **and** annual-maximum bias **and** does not degrade the differential split-sample test. Smoother curves alone are not a criterion.
- Status stays `experimental` until all of the above pass on independent observations.

---

## 6. Ensemble and uncertainty strategy

### 6.1 Ensemble dimensions

| Dimension | Members (initial) | How sampled |
|---|---|---|
| Scenario | SSP2-4.5, SSP5-8.5 | Reported separately, never pooled |
| GCM | 10–12 of the NEX-GDDP models, selected by an envelope approach (Lutz et al., 2016): first drop models failing monsoon-cycle realism over the catchment, then span the ΔP/ΔT space | Equal weights by default; performance weighting tested separately |
| Reference forcing for bias correction | ERA5(-Land) and CHIRPS for precipitation | Factorial |
| Hydrological parameters | 10 behavioural HBV-EB-G parameter sets (multi-seed differential evolution, KGE within a set tolerance of the best) | Factorial |
| Hydrological structure | HBV-EB-G (+ VIC or GR4J-CemaNeige if Phase 3b passes) | Factorial |
| AI correction | Quantiles from B4 (only if retained) | Sampled |
| Operations | 3–4 named scenarios (Trimmu only) | Reported per scenario *and* pooled |
| Internal variability | GCM-run variability across 5-year periods; optional block bootstrap of years | Quantified in the ANOVA residual term |

### 6.2 Outputs and probabilistic method

- Compute the statistics **per member per period** (seasonal/annual means, annual maximum daily flow, days above threshold, Q10/Q90 of the flow-duration curve, low-flow 7-day minimum). Then take P10/P50/P90 **across members**. Daily P10/P50/P90 curves are shown only as climatological day-of-year envelopes, never as dated forecasts.
- Report changes relative to (a) the 1995–2014 model-simulated baseline (consistent with each member's own historical run) and (b) observed 2016–2025 statistics at Marala.
- **Uncertainty partitioning**: a three- or four-way ANOVA (scenario × GCM × hydrological parameters/structure × operations), with subsampling to handle unbalanced designs (Bosshard et al., 2013). Contributions are reported per period.
- **High-flow probability**: per member, the empirical probability that the annual maximum exceeds threshold *T* in the period. Thresholds are the observed 2016–2025 P95 and P99 at Marala, plus official FFD categories once obtained. Pooling across members gives a probability with an explicit spread, not a single number.
- **Calibration of the ensemble** is evaluated, not assumed (§7.3). If coverage fails, intervals are labelled "uncalibrated spread", not "probability".

---

## 7. Independent-validation feasibility

### 7.1 What is feasible

| Node | Feasible now | Not feasible |
|---|---|---|
| Marala | HBV calibration 2016–2021; blocked validation 2022–2025; differential split-sample test within 2016–2025; peak plausibility against 30 PMD maxima (1970–2016); AI correction as `experimental` | Validation of multi-decadal trends; pre-2016 split-sample tests (no continuous data) |
| Mangla (Jhelum) | Same as Marala **after** extraction of the 2016–2024 workbook series | — |
| Trimmu | Flood-season plausibility checks of routed and operated flows against 350 FFD days | Calibration, independent validation, AI correction |

### 7.2 Two validation modes (must not be confused)

1. **Perfect-forcing mode.** The hydrological core is forced by ERA5/CHIRPS. Daily correspondence exists, so the following metrics apply: NSE, KGE, log-NSE, RMSE, MAE, PBIAS, peak error, peak timing, CRPS, Brier score, PI coverage, reliability and sharpness. Rolling-origin and blocked-year designs are used here.
2. **Climate-chain mode.** The core is forced by bias-corrected GCM historical/SSP runs. There is no daily correspondence, so only **distributional** metrics apply: flow-duration-curve error, seasonal-cycle KGE, annual-maximum distribution (KS test and quantile errors), and the fraction of observed 2016–2025 period statistics falling inside the ensemble P10–P90. Reporting NSE for GCM-driven runs would be a methodological error.

### 7.3 Ensemble calibration check

With only about 10 observed years, coverage tests have low power. They are reported with binomial confidence bounds and the explicit caveat that a pass is weak evidence.

### 7.4 GloFAS

Used only as (a) a comparator in perfect-forcing mode and (b) an optional feature. It is never a training target for the corrector, and never ground truth.

### 7.5 Data requests that change feasibility most

1. Trimmu daily inflow/outflow, 2000–2025.
2. Canal-head withdrawals at the six barrages and headworks.
3. Marala daily discharge before 2016.
4. Rasul series.
5. FFD official flood thresholds for Marala and Trimmu.

The short-range folder already holds a drafted historical-records request (`historical_search_1980_2016/historical_records_request_draft.md`) that can be extended.

---

## 8. Proposed API and frontend design

### 8.1 Publication contract (engine → app)

The engine writes an immutable bundle per run:

```text
projection_runs/<run_id>/
  manifest.json          # run_id, created_utc, engine version, git commit, config hash, status
  provenance.json        # every source: name, version, URL, licence, retrieval date, checksum
  results.parquet        # long format: station, scenario, period, statistic, aggregation, p10, p50, p90, mean, median, change_abs, change_pct
  uncertainty.parquet    # ANOVA shares per station/scenario/period/statistic
  validation.json        # metrics by mode, status per component (calibrated / experimental / disabled)
  model_cards/*.json
```

The app reads only bundles whose manifest marks them `published`. A copy step (not a cross-repo import) moves a bundle into `disaster_management/app/ml/projections/`, as with the Marala monthly artifacts.

### 8.2 Endpoints (FastAPI, `/api/v1/projections`, read-only, same conventions as `predictive_monthly`)

| Method and path | Returns |
|---|---|
| `GET /projections/catalog` | Basins, stations, scenarios, periods, operation scenarios and the **status** of each combination (`available`, `experimental`, `not_available` with reason) |
| `GET /projections/{station_id}/summary?scenario=&period=&ops=` | Headline P10/P50/P90 statistics, changes versus baseline, high-flow probabilities, warnings |
| `GET /projections/{station_id}/series?scenario=&aggregation=annual\|seasonal\|doy_climatology` | Period/annual/seasonal envelopes for charts |
| `GET /projections/{station_id}/uncertainty?scenario=&period=` | Variance shares by source |
| `GET /projections/runs/{run_id}` | Manifest, provenance and validation |
| `GET /projections/readiness` | The data-readiness audit (this module's `audit/data_readiness.json`) |

Missing bundle → HTTP 503 with a reason, never a fallback value. There is no compute endpoint. A later admin-only "request run" endpoint would enqueue a job, never compute in-request.

### 8.3 Result schema (per record)

```json
{
  "basin_id": "chenab", "station_id": "MARALA",
  "scenario": "ssp245", "period": "2031-2035", "baseline_period": "1995-2014",
  "aggregation": "jjas_mean", "statistic": "mean_daily_discharge", "unit": "m3/s",
  "p10": null, "p50": null, "p90": null, "mean": null, "median": null,
  "change_vs_baseline_pct": {"p10": null, "p50": null, "p90": null},
  "operations_scenario": "natural", "ensemble_size": null,
  "uncertainty_shares": {"gcm": null, "scenario": null, "hydro_params": null, "hydro_structure": null, "ai_correction": null, "operations": null, "residual_variability": null},
  "model_versions": {"hbv_eb_g": null, "bias_correction": null, "ai_correction": null},
  "data_sources": ["nex_gddp_cmip6@<version>", "era5_land@<version>"],
  "validation_status": "experimental",
  "quality_flags": ["extrapolation_share_12pct"],
  "warnings": ["Scenario-based climate projection, not a deterministic flood forecast."],
  "created_utc": null, "run_id": null
}
```

(Values are `null` here on purpose: no projection has been computed.)

### 8.4 Frontend: "Long-Term Projection" workspace

A **new tab, separate from the existing hypothetical 10-Year Outlook**. Once validated bundles exist, the 10-Year Outlook can switch its data source; until then it keeps its "hypothetical" label.

1. Selectors: basin, station, scenario, period, operations scenario (disabled where not supported).
2. A persistent banner: "Scenario-based climate projection, not a deterministic flood forecast." It also shows a status chip: `Experimental`, `Unvalidated`, or `Validated (hindcast)`.
3. Baseline versus future: observed 2016–2025 and simulated 1995–2014 baselines beside the period P10/P50/P90.
4. Probabilistic chart: day-of-year climatology envelopes (not dated series), with a distinct visual style from operational hydrographs.
5. Seasonal and annual panels: JFM/AMJ/JAS/OND or snowmelt/monsoon/post-monsoon/winter.
6. High-flow indicators: probability that the annual maximum exceeds the observed P95/P99 or FFD categories, shown with spread.
7. Uncertainty breakdown: stacked shares by source.
8. GIS: catchment polygons, station nodes, canal withdrawal nodes and hazard-indicator symbology per station. **No inundation extents.**
9. Provenance and validation: sources, versions, metrics by validation mode, and the readiness audit.

Trimmu is shown with status `Unvalidated — no year-round observations` until §7.5 data arrive.

### 8.5 Flood-hazard linkage

A HEC-RAS 1D/2D model of the Trimmu–Jhang reach is the correct route to inundation. It requires surveyed cross-sections or bathymetry, structure geometry, roughness calibration and an observed flood extent for validation (UNOSAT extents are already in the exposure pilot). None of the existing Jhang hydraulic trials meets this; the TUFLOW trial was withdrawn for exactly this reason. Until then, only discharge-based hazard indicators are shown.

---

## 9. Implementation milestones

| Phase | Deliverables | Exit criteria |
|---|---|---|
| **0 Audit** (this report) | Architecture review, readiness audit script and output, methodology | Report reviewed; data requests sent |
| **1 Foundation** | `projection_engine/` package; source registry (YAML) with the provenance fields required in the prompt; Pydantic schemas for sources, runs and results; storage layout; config for basins, stations, scenarios and periods; logging; unit tests | Schemas validate; registry rejects entries without licence/version; tests pass |
| **2 Historical and climate data** | NEX-GDDP-CMIP6 connector (catchment-mean extraction, checksums); ERA5-Land tasmin/tasmax; Mangla series extraction; Trimmu/Mangla/intermediate catchment delineation; QDM bias correction with split-sample validation (1985–1999 / 2000–2014) on extremes, wet-day frequency, monsoon cycle, interannual SD and trend | Bias-correction validation report; QC flags; no silent fills |
| **3 Physical baseline** | HBV-EB-G (bands and glacier); multi-seed calibration at Marala (and Mangla); behavioural parameter sets; node–link operations model; Phase 3b VIC feasibility gate | Perfect-forcing validation report incl. peak metrics; water-balance audit; VIC go/no-go documented |
| **4 AI correction** | B0–B6 ladder; regime comparison; extrapolation detector | Correction retained only if §5.5 criteria pass; otherwise disabled with the evidence recorded |
| **5 Probabilistic projection** | Ensemble runner (offline, resumable); period statistics; ANOVA partitioning; operations scenarios | Climate-chain validation report; coverage results |
| **6 API and GIS** | Bundle publisher; `/api/v1/projections` router plus tests in the app; Long-Term Projection workspace | Existing app tests still pass; 503 paths tested; banner and status chips present |
| **7 Research evaluation** | Full ablations, hindcasts, uncertainty evaluation, limitations write-up | Results reproducible from the manifest |

---

## 10. Scientific risks and unresolved assumptions

| Risk | Severity | Mitigation |
|---|---|---|
| Short observed record (~10 years at Marala, none year-round at Trimmu) | High | Data requests; experimental status; differential split-sample test |
| Near-term signal smaller than internal variability; SSPs indistinguishable before ~2040 | High (communication) | Show the variability share explicitly; no trend claims without significance |
| HBV underestimates floods (flood-day NSE −1.98) | High for high-flow indicators | Peak-focused calibration objective (KGE plus annual-max term); report peak bias separately |
| Glacier retreat not represented | Medium–high by 2040 (July–August flows) | Glacier store in HBV-EB-G; external glacier projections if available |
| Reference precipitation uncertainty in the mountains (ERA5 wet bias; CHIRPS snowfall weakness) | High | Two references as an ensemble dimension; PET/precipitation water-balance check against observed runoff |
| Bias correction distorting trends or extremes | Medium | QDM (trend-preserving); validate extremes indices; no random splits |
| Regulation and treaty uncertainty (Indian storage, IWT "in abeyance", canal policy) | High at Trimmu | Named, labelled operation scenarios only; never presented as measured |
| WAPDA observation basis unconfirmed (06:00 reading versus daily mean) | Medium | Keep the `measurement_basis` flag; test sensitivity on peaks |
| Non-stationary residuals (corrector learned in 2016–2025 applied to 2036–2040) | Medium | Extrapolation detector; shrink to physics outside support |
| GCM selection bias | Medium | Envelope selection documented; sensitivity to the full set |
| Cross-repository coupling | Low | One-way, immutable bundle publication; no imports across repositories |

**Unresolved assumptions requiring user or agency input:** the baseline period (1995–2014 model baseline versus the observed 2016–2025 baseline), the official flood thresholds, which agencies to approach for Trimmu and canal data, and whether Jhelum/Mangla is in scope for the first release (it is required for any physically meaningful Trimmu flow).

---

## First safe implementation milestone

**Milestone 1: "Marala climate-forcing foundation" (Phase 1 plus the first part of Phase 2). It involves no hydrological or AI model training.**

1. Create `long range/projection_engine/` with:
   - the source registry (`config/sources.yaml`) and Pydantic schemas for sources, runs and result records (the §8.3 schema);
   - a run manifest writer;
   - unit tests.
2. Build the NEX-GDDP-CMIP6 connector for the Marala catchment only:
   - variables pr, tas, tasmin and tasmax;
   - the historical period (1985–2014) plus SSP2-4.5 and SSP5-8.5 (2015–2040);
   - an initial subset of about 5 models, to test throughput;
   - area-weighted catchment means using the existing verified catchment polygon;
   - SHA-256 receipts and per-model licence and version recorded;
   - storage in `long range/dataset/climate/nex_gddp_cmip6/{raw,processed}/` per source.
3. Extend the ERA5-Land extractor for tasmin/tasmax (Marala) into `long range/dataset/reference/`. Short-range data is only read, never modified.
4. Produce a "raw GCM versus reference" diagnostic for 1985–2014: monsoon cycle, wet-day frequency, Rx1day and interannual SD per model. **No correction yet.**

This milestone is safe for four reasons: it adds new files in `long range/` only, it trains nothing, it changes nothing in the app, and every number it produces is a direct, provenance-tracked transformation of a published dataset. In parallel, the user can send the §7.5 data requests, because they take the longest to come back.

---

### References (methods)

Cannon, A. J., Sobie, S. R. & Murdock, T. Q. (2015), quantile delta mapping, *J. Climate*. · Hawkins, E. & Sutton, R. (2009), uncertainty in regional climate predictions, *BAMS*. · Lutz, A. F. et al. (2016), selecting representative climate models for High Mountain Asia, *Int. J. Climatol.* · Klemeš, V. (1986), operational testing of hydrological simulation models, *Hydrol. Sci. J.* · Bosshard, T. et al. (2013), quantifying uncertainty sources in hydroclimatic projections, *WRR*. · Gneiting, T. & Raftery, A. (2007), proper scoring rules, *JASA*. · Rounce, D. et al. (2023), global glacier change in the 21st century, *Science*. · Thrasher, B. et al. (2022), NASA NEX-GDDP-CMIP6, *Scientific Data*.
