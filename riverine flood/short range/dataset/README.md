# Short-range riverine flood datasets

This folder holds only the data for the short-range riverine flood model. The current target is to predict daily station discharge for each of the next 15 days. See [historical coverage findings](historical_coverage.md) for verified daily WAPDA coverage and unresolved hourly/downstream access.

The selected pilot models forecast **future Marala discharge from earlier Marala readings (Chenab)** and **future Jassar discharge from earlier Jassar readings (Ravi)**. Their data belongs in separate station folders. See [plan.md](plan.md) for the 15-day forecast plan.

```text
dataset/
|-- chenab_marala/
|   |-- raw/
|   |   `-- marala/                 # Historical Marala discharge
|   `-- processed/
|       `-- marala/
|           `-- discharge/          # Extracted Marala discharge tables and reports
`-- ravi_jassar/
    |-- raw/
    |   `-- jassar/                 # Historical Jassar discharge
    `-- processed/                  # Future Jassar training data and targets
```

The tree below is the planned layout, not a list of downloaded files. Collect data for the target river reach **and its upstream contributing catchment**, including cross-border upstream areas where relevant.

## Planned dataset tree

```text
dataset/
|-- README.md
|-- raw/                              # Preserve original provider files
|   |-- river_observations/           # REQUIRED: target and upstream stations
|   |   |-- discharge/                # Timestamped discharge (m3/s)
|   |   |-- water_level/              # Stage (m), with gauge datum
|   |   `-- station_metadata/         # IDs, coordinates, units, QC, thresholds
|   |-- rainfall/                     # REQUIRED: upstream rainfall history
|   |   |-- gauges/                   # PMD station observations, if obtainable
|   |   `-- imerg/                    # Satellite rainfall; keep run/version
|   |-- weather_forecasts/            # For rainfall-driven forecasts
|   |   `-- precipitation/            # Archived forecast runs + issue times
|   |-- catchment/                    # REQUIRED: catchment/reach definition
|   |   |-- basin_boundaries/         # Upstream catchment polygons
|   |   |-- river_network/            # Reach IDs and upstream connectivity
|   |   `-- elevation/                # DEM for delineation/terrain features
|   |-- land_state/                   # OPTIONAL: antecedent conditions
|   |   |-- soil_moisture/
|   |   `-- temperature_snow/         # Useful for snow-fed upstream basins
|   |-- river_operations/             # Where dams/barrages regulate the reach
|   |   `-- releases_levels_gates/    # Releases, reservoir levels, gate logs
|   |-- flood_events/                 # REQUIRED for flood classification
|   |   |-- official_thresholds/      # Station-specific flood categories
|   |   `-- event_catalog/            # Event dates, peaks, evidence/source
|   `-- glofas/                       # OPTIONAL: modeled discharge baseline
|-- processed/                        # Generated from this model's raw data
|   |-- aligned_timeseries/           # Consistent timestamps, units, QC flags
|   |-- catchment_features/           # Basin rainfall, terrain, connectivity
|   |-- targets/                      # Future discharge/stage/flood labels
|   `-- splits/                       # Train/validation/test date manifests
`-- metadata/
    |-- sources.csv                   # URL, provider, version, license, retrieval
    |-- stations.csv                  # Station IDs, coordinates, gauge datum
    |-- data_dictionary.csv           # Variables, units, missing-value codes
    |-- coverage.csv                  # Spatial/time coverage, gaps, cadence
    `-- quality_report.md             # Checks, exclusions, limitations
```

## Dataset sources and collection requirements

| Dataset | Source | What to obtain / limitations |
|---|---|---|
| River discharge, stage, station flood thresholds and bulletins | [PMD Flood Forecasting Division (FFD)](https://ffd.pmd.gov.pk/index.php) | Target and upstream station records, observation times, station locations, official thresholds and their effective dates. Prefer hourly/subdaily observations for the proposed horizons. Public bulletins do not establish availability of a complete historical archive; request records from the owning agency if necessary. Collect discharge or stage at minimum; both are preferable. |
| Gauge rainfall | [Pakistan Meteorological Department](https://www.pmd.gov.pk/) | Timestamped upstream station precipitation, accumulation interval, coordinates and quality flags. Confirm historical access with PMD; do not assume a public bulk archive. |
| Satellite rainfall | [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg) | Half-hourly precipitation estimates over the upstream basin. Record Early/Late/Final run and product version. Final products can support retrospective research; operational evaluation must use data available at the forecast issue time. Earthdata access may require registration. |
| Forecast precipitation | [PMD SMRFC forecast products](https://www.pmd.gov.pk/rnd/rndweb/rnd_new/smrfc.php) | Forecast rain over the prediction horizon, with initialization time, valid time and lead time. Confirm whether historical numerical forecast files are obtainable; a current display is not a training archive. Required if the chosen model uses future forecast rainfall; otherwise begin with a gauge/rainfall-history baseline and document that limitation. |
| Catchment boundaries and connected river reaches | [HydroSHEDS products](https://www.hydrosheds.org/about), including [HydroRIVERS](https://www.hydrosheds.org/products/hydrorivers) | Basin polygons and river connectivity for the selected stations. Validate station-to-reach matching; retain product IDs and versions. |
| Elevation / drainage terrain | [HydroSHEDS](https://www.hydrosheds.org/about) | Hydrologically conditioned elevation and drainage layers appropriate to basin delineation. Terrain-derived features are optional for a simple single-station time-series baseline. |
| Soil moisture, temperature and snow state | [Copernicus ERA5-Land hourly data](https://cds.climate.copernicus.eu/datasets/reanalysis-era5-land?tab=documentation) | Optional antecedent land-state features. These are reanalysis estimates; record release/availability times and do not treat delayed reanalysis as live input. CDS access and license acceptance may be needed. |
| Dam/barrage releases, levels and gate operations | [FFD](https://ffd.pmd.gov.pk/index.php), plus the relevant reservoir/barrage operator | Obtain timestamped operating records for regulated upstream reaches. Confirm access with the operator; archive availability is not guaranteed. Never use future realized releases as forecast inputs unless they were issued as schedules before prediction time. |
| Historical modeled discharge | [Copernicus GloFAS historical discharge](https://ewds.climate.copernicus.eu/datasets/cems-glofas-historical?tab=overview) | Optional daily modeled discharge for comparison or pretraining. It is not observed ground truth and does not replace subdaily gauge records for 6- or 12-hour validation. Record model version and match river reaches carefully. |

## Minimum collection before training

1. Select upstream reporting stations and downstream prediction reaches, then delineate their contributing basins. No downstream location is predetermined.
2. Obtain overlapping target/upstream discharge or stage records and basin rainfall, with station metadata and quality flags. Include several years where feasible, multiple independent flood events, and non-flood periods; actual sufficiency depends on record quality and model complexity.
3. Obtain official station thresholds for flood classification. Discharge/stage regression can start without classification thresholds. Add operating records where flow regulation materially affects predictions.
4. Match prediction resolution to actual measurements. Daily observations cannot support genuine subdaily verification; do not interpolate them and present the result as hourly ground truth.
5. Define each sample by station/reach, forecast issue time and lead time. Use only inputs available by that issue time; retain both observation/valid time and availability/issue time.
6. Split chronologically, keeping flood events and overlapping forecast windows from leaking across training, validation and test sets. Fit scalers and imputers on training data only.

## File conventions and isolation

- Store tabular observations as CSV/Parquet, gridded data as NetCDF/GRIB/GeoTIFF, and boundaries/networks as GeoPackage/GeoJSON where practical. Keep original downloads under `raw/`.
- Normalize processed timestamps to UTC while preserving original timezone information. Record discharge in m3/s, stage in m with datum, and rainfall as either mm per stated interval or mm/hour; convert explicitly.
- Record source URL, provider, license, product/version, retrieval date, spatial extent, time coverage, units and checksum in the source manifest. Keep missing values and quality flags explicit.
- Keep this model's data and generated features here. Do not move datasets from `exposure_infrastructure/` or another flood model into this folder. Population/buildings/roads are exposure inputs and are not required for the initial river-flow forecasting task.
- Satellite inundation masks, channel geometry and hydraulic boundary conditions would need a separate specification if the output is later expanded to flood extent or depth maps.

Source links checked on 2026-10-23. See the [Marala discharge source notes](chenab_marala/raw/marala/discharge/README.md) for collected files and their provenance.

Marala now has a [source- and geometry-checked upstream catchment](chenab_marala/processed/marala/catchment/README.md) for initial basin feature extraction. The rebuilt [catchment precipitation dataset](chenab_marala/processed/marala/rainfall/README.md) covers its full area and provides a daily area-weighted series.
