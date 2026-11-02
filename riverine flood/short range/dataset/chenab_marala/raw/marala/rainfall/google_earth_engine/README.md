# Marala catchment daily precipitation

Precipitation only, inclusive dates **1980-01-01 through 2024-12-31** (16,437 rows).
The output directory is this directory:
`riverine flood/short range/dataset/chenab_marala/raw/marala/rainfall/google_earth_engine`.
It sits beside the existing `chirps_v3` and `nasa_power` provider folders.

## Run

Requires Python 3.10+ and an Earth Engine enabled Google Cloud project/account.
From this directory, in PowerShell:

```powershell
python -m pip install -r requirements.txt
python extract_precipitation.py --project YOUR_EE_CLOUD_PROJECT --authenticate
```

Later runs can omit `--authenticate`. `EE_PROJECT` may supply the project instead.
To extract, run QA, and rebuild the local portal in one command, use:

```powershell
.\run_precipitation.ps1 -ProjectId YOUR_EE_CLOUD_PROJECT -Authenticate
```

This helper uses the local `.venv` environment and rebuilds the portal only after
extraction and QA succeed. Then reload the portal's Summary view. Its four Earth
Engine series remain separate from the older CHIRPS v3 and POWER comparisons.
The script downloads CSV exports directly to local disk; no Drive folder or manual
download is required. Monthly chunks limit server workload; failures retry and
subdivide down to individual days. Rerun to resume. An expired login requires
reauthentication. Changed settings require a fresh `--output` directory.

To rebuild the merged file and QA from existing chunks without Earth Engine:

```powershell
python extract_precipitation.py --merge-only
```

Extraction requires an authorized Earth Engine project. Completed chunks are
preserved and reused on restart; final outputs appear after extraction and QA.

## Catchment and spatial mean

**Default: reuse the existing checked Marala catchment** at
`riverine flood/short range/dataset/chenab_marala/processed/marala/catchment/marala_upstream_catchment.geojson`.
Its saved geodesic area is **28,780.646 km2**, 1.41% below the 29,192 km2 PMD
reference recorded in the adjacent verification report. That report records valid
geometry, outlet and upstream-network consistency checks, and an identical polygon
for a nearby test point. These are useful research checks, not survey certification.
The original Global Watersheds service documents MERIT-Hydro/MERIT-Basins but did
not expose its exact snapped cell or precise software/data version.

The script loads this polygon directly, prints its Earth Engine area, saves a copy
in this rainfall folder, and records the source file hash and saved verification
report. It does not snap again or replace the existing boundary. The 26,000 km2
target is a rough expectation; it is not evidence that this checked polygon should
be reduced to match it. An Earth Engine area may differ slightly from the saved
ellipsoidal geodesic area due to geometry/area calculation conventions.

Use `--catchment PATH_TO_GEOJSON` to supply another single Polygon/MultiPolygon.
Use `--redelineate` to opt into the fresh delineation described below. The river
snap parameters and 26,000 km2 area gates apply only to fresh delineation. As with
other changed settings, switching catchments requires a fresh output folder if
rainfall chunks already exist.

### Optional fresh delineation (`--redelineate`)

The default point is **longitude 74.46, latitude 32.67**, taken from the existing
project's `collect_marala_catchment.py` (JICA/PMD station inventory). No coordinates
were present in this request. Override with `--lon` and `--lat` if another pour
point was intended. The nearest MERIT Hydro 3-arcsecond cell center with upstream
area >=1,000 km2 within 3 km defines the river snap; both thresholds are configurable.
This prevents snapping to a minor nearby tributary simply because it is closer.

The script finds the level-12 HydroBASINS polygon intersecting that snapped cell,
then traverses **NEXT_DOWN in reverse**, over the whole MAIN_BAS network. It unions
every contributing upstream polygon, including the outlet polygon. It does not
use a station buffer or stop at an arbitrary geographic bounding box.

**Resolution qualification:** this is an upstream HydroBASINS delineation at
level 12, not a cell-exact MERIT D8 delineation. The outlet subbasin includes its
entire area, including its portion downstream of the point. MERIT cells and
HydroSHEDS polygons use different source hydrographies. Review the exported
polygon, snapped point, outlet SUB_AREA/UP_AREA and MERIT upstream area before
scientific use. The outlet subbasin SUB_AREA indicates the maximum amount of
extra land contributed by including that whole subbasin, but other dataset
differences are not bounded by that number.

Area is printed in km2. A >10% departure from 26,000 km2 prints a warning; >20%
stops extraction after writing geometries for inspection. Existing project work
also cites a PMD Marala area of 29,192 km2, so the target is a plausibility check,
not a calibration constraint. `--allow-area-mismatch` explicitly overrides the
20% stop after review; no polygon is reshaped to match a target area.

Each product uses its own native projection **and affine transform**, including
pixel origin. Nominal scales are recorded dynamically (approximately ERA5-Land
11,132 m, CHIRPS 5,566 m, PERSIANN 27,830 m, IMERG 11,132 m). No resampling to a
common coarse grid or `bestEffort` resolution change is used.

The reduction is `reduceRegion(ee.Reducer.mean().splitWeights(), ...)` with
`ee.Image.pixelArea()` as the explicit second input. Ordinary `mean()` provides
fractional boundary weights but geographic cells vary in physical area, so the
explicit area weights are necessary. Effective weight for binary valid masks
is pixel area times polygon intersection fraction. Earth Engine approximates
boundary fractions at about 1/256 precision; very small intersections can vanish.
The script uses the native grid's polygon area sum to check spatial coverage and
rejects means below 99.9% coverage by default (`--min-coverage`). It does not treat
masked areas as zero precipitation. The small allowed coverage tolerance means
accepted means may represent slightly less than the full polygon.

## Products and day conventions

| Output | Collection / band | Period used | Conversion |
|---|---|---|---|
| era5land_mm | ECMWF/ERA5_LAND/DAILY_AGGR / total_precipitation_sum | 1980-01-01 onward | m × 1000 |
| chirps_mm | UCSB-CHG/CHIRPS/DAILY / precipitation | 1981-01-01 onward | already mm/day |
| persiann_mm | NOAA/PERSIANN-CDR / precipitation | 1983-01-01 onward | already daily mm |
| imerg_mm | NASA/GPM_L3/IMERG_V07 / precipitation | 2000-06-01 onward | each mm/hour rate × 0.5 hour, then sum |

All stop at 2024-12-31. IMERG V07 has since gained earlier reprocessed coverage;
this workflow deliberately uses the requested June 2000 start. Only IMERG assets
with `status=permanent` are selected, excluding provisional replacements.

The output uses nominal **00:00 inclusive to next 00:00 exclusive UTC** days.
ERA5-Land `_sum` uses the following day's 00 UTC accumulated field representing
the preceding day; the Earth Engine daily aggregate is already labeled for that
preceding day. Do not shift its dates again. PERSIANN daily records and CHIRPS
daily calendar labels are used as supplied in Earth Engine, selected by their UTC
timestamps. CHIRPS incorporates gauge reporting with heterogeneous observation
times and temporally disaggregated satellite information: its calendar label
does not establish exact midnight-to-midnight timing for every input gauge.
IMERG is explicitly aggregated over the 48 UTC half-hours, with timestamp-list,
image-count and per-pixel completeness checks. Missing intervals yield NaN.

Pakistan is UTC+5 with no seasonal adjustment in this workflow. A UTC daily total
spans **05:00 Pakistan time to 05:00 the next day**. A Pakistan local-midnight
day labeled D spans **19:00 UTC on D-1 to 19:00 UTC on D**. For an actual gauge
reading at H:00 Pakistan time, its preceding 24-hour window ends at H-5 hours
UTC; check whether the station labels observations by ending or starting date.

**Do not relabel a daily total or apply a five-hour index shift to claim local-day
rainfall.** Exact rebucketing needs subdaily data: aggregate 48 IMERG half-hours
over the local window, or 24 properly de-accumulated ERA5-Land hourly increments.
CHIRPS Daily and PERSIANN-CDR cannot be exactly shifted from their daily totals.
This script keeps a common UTC-date comparison; it does not manufacture local-day
values from daily inputs.

## Output and quality checks

- `marala_upstream_catchment.geojson` and `catchment_metadata.json`: copied/recorded
  from the existing catchment by default, with printed area. Fresh delineation also
  writes `marala_snapped_outlet.geojson`; reuse does not invent an unknown snap.
- `run_manifest.json`: settings, products and native projections; fingerprint
  prevents resuming chunks from a different extraction configuration.
- `chunks/<product>/<start>_<exclusive-end>.csv`: direct monthly or smaller
  exports containing values, raw minimum, negative area fraction, valid spatial
  fraction and image count. These diagnostics are separate from the final CSV.
- `marala_daily_precipitation_1980_2024.csv`: exactly
  `date,era5land_mm,chirps_mm,persiann_mm,imerg_mm`, full daily calendar and literal
  `NaN` for absent values, including expected pre-product periods.
- `quality_report.json`: expected unavailability distinguished from unexpected
  missing days; nonnegative values, counts and descriptive statistics.
- `annual_totals.csv`: full-year totals only when every calendar day exists;
  partial sums explicitly occupy a separate column. Both are printed.

ERA5-Land can have physically invalid negative precipitation from GRIB packing.
The script clips **negative ERA5 pixels only** to zero before averaging, while
preserving raw minimum and negative area fraction for review. This changes the
original source values and can add a small positive bias. Negative means from
other products become NaN and fail QA; any negative source pixels in those
products also fail QA. Extreme positive values are printed in maximum statistics
but not automatically removed. Missing days, duplicate chunks, invalid numbers,
and insufficient spatial coverage are detected. A failed QA exits nonzero after
writing the combined file and report so gaps can be inspected; do not interpret
that intermediate file as a complete validated dataset.

## Primary references

- [HydroBASINS level 12 and topology fields](https://developers.google.com/earth-engine/datasets/catalog/WWF_HydroSHEDS_v1_Basins_hybas_12)
- [MERIT Hydro](https://developers.google.com/earth-engine/datasets/catalog/MERIT_Hydro_v1_0_1)
- [ERA5-Land aggregation, units and negative-value caveat](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR)
- [CHIRPS v2 Daily](https://developers.google.com/earth-engine/datasets/catalog/UCSB-CHG_CHIRPS_DAILY)
- [PERSIANN-CDR](https://developers.google.com/earth-engine/datasets/catalog/NOAA_PERSIANN-CDR)
- [IMERG V07 units, status and cadence](https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_V07)
- [Earth Engine weighted reducers](https://developers.google.com/earth-engine/guides/reducers_weighting)

Respect and cite the source datasets' attribution/license requirements.
