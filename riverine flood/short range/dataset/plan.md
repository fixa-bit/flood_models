# Short-range river discharge forecasting plan

Build two separate station forecasts:

1. **Chenab — Marala:** Use past Marala discharge to predict future Marala discharge.
2. **Ravi — Jassar:** Use past Jassar discharge to predict future Jassar discharge.

**Forecast target:** At each daily forecast time, predict discharge for **each of the next 15 days** at the same station (days 1 through 15). Report accuracy separately for each lead day and for high-flow events. A one-day model is only an initial baseline, not the final target.

Past discharge provides the river's current state. For a useful 15-day flood forecast, also add rainfall and temperature history over each upstream basin and weather forecasts issued at the forecast time for the next 15 days. Where relevant, add snow conditions and reservoir or barrage operation information. A discharge-only model may be used as a baseline, but its longer-range flood predictions must be compared against simple baselines and should not be assumed reliable.

## Data collection

- **Marala:** The [WAPDA River Flow workbook](https://wapda.gov.pk/wp-content/uploads/2024/12/GRAPH-DG-16-for-MAIL-2.xls) is saved under `chenab_marala/raw/marala/discharge/wapda/`. Its Marala inflow values have been extracted to `chenab_marala/processed/marala/discharge/marala_wapda_daily_inflow.csv`: 3,216 daily values from 1 March 2016 to 19 December 2024, with no missing dates inside that span. The zero value on 23 January 2021 is flagged. A [WAPDA daily report](https://wapda.gov.pk/wp-content/uploads/2024/12/Daily-DataPress-Release-19-12-2024.xls) labels Marala's 19 December 2024 reading as **at 0600 hrs** and matches the historical workbook value. The other WAPDA historical dates have no individually confirmed time. Use past Marala inflow to forecast future Marala inflow; keep FFD outflow as a separate variable. Preserve source-specific records and date conflicts until a training series is reviewed.
- **Jassar:** [FFD flood bulletins](https://ffd.pmd.gov.pk/bulletin/) publish Jassar discharge readings. Obtain a complete historical Jassar series before training and store it in `ravi_jassar/raw/jassar/`.
- **Additional Marala sources collected:** FFD bulletins provided 122 Marala inflow/outflow readings for 2024, 119 for 2025, and 122 for 2026, all explicitly at 06:00 Pakistan time. Some 2024/2025 PDFs disagree with their archive-listed dates or duplicate printed dates. A separate PMD paper provided 30 selected historical flood peaks. The [combined discharge catalog](chenab_marala/processed/marala/discharge/marala_discharge_all_sources.csv) retains dates, confirmed times, source URLs, and quality flags. See the [Marala discharge source notes](chenab_marala/raw/marala/discharge/README.md). Do not append event peaks to daily observations or assume flood-season bulletins fill the year-round gap after the WAPDA workbook.
- **Weather inputs:** Collect historical basin rainfall (for example, [NASA GPM IMERG](https://gpm.nasa.gov/data/imerg)) and archived 15-day weather forecasts with their original issue dates and lead times (for example, the meteorological forecasts used by [GloFAS](https://confluence.ecmwf.int/spaces/CEMS/pages/265028598/GloFAS%2Bmeteorological%2Bforecasts)). Confirm the archive's coverage and access before choosing a training period. Future observed rain must never be used as if it were a forecast.
- Put each station's cleaned data and forecast targets in its own `processed/<station>/discharge/` folder. Align timestamps and units, flag questionable readings, and split data by time so the same flood event does not span training and test sets.
- Train and test with forecast issue dates in the past, using only information available on each issue date. Reserve later years and separate flood events for testing; assess day 1, day 3, day 7, day 10 and day 15 explicitly.

Neither model uses Khanki, Shahdara, or Ravi Syphon data. See [historical_coverage.md](historical_coverage.md) for the source checks completed so far.

## Discharge preparation completed 2026-10-23

The [daily Marala inflow baseline](chenab_marala/processed/marala/discharge/marala_daily_inflow_clean.csv) retains all 3,216 WAPDA dates. Seven unresolved days (one numeric zero and six WAPDA-FFD differences) have blank modeling values and are excluded by `eligible_daily_training=0`; the original values remain in `source_inflow_cusecs`. Only 2024-12-19 has an individually confirmed WAPDA time. See the [quality review](chenab_marala/processed/marala/discharge/marala_inflow_quality_review.csv). Require continuous eligible input and 15-day target windows before training.

The recent-source search recovered 35 additional 2026 FFD dates, expanding that year to 122 consecutive dates from 16 June to 15 October. Eight recent IRSA reports (16-23 October 2026) contain daily means and are stored as a separate variable. WAPDA public pages still link the 2024 workbooks, and sampled older IRSA report URLs returned 404. A complete 2025 or 2026 year-round series remains unverified. The [coverage calendar](chenab_marala/processed/marala/discharge/marala_2025_2026_coverage.csv), [search report](chenab_marala/processed/marala/discharge/marala_recent_source_search_report.json), and [unsent request draft](chenab_marala/processed/marala/discharge/marala_recent_records_request.md) document the remaining acquisition work.

## Catchment precipitation rebuilt 2026-10-23

The previous regional rainfall files were deleted and replaced with fresh [NASA POWER catchment-selected precipitation](chenab_marala/processed/marala/rainfall/README.md). Only the 21 native grid cells intersecting the saved Marala catchment are downloaded. Full-catchment daily precipitation is calculated by weighting each cell by its area inside the catchment; spatial coverage is 100%. The [daily catchment series](chenab_marala/processed/marala/rainfall/marala_catchment_daily_precipitation.csv) has 3,887 complete days from 2016-03-01 through 2026-10-21; the requested 2026-10-22 row remains missing and flagged. Raw JSON responses, source URLs and retrieval timestamps are under `raw/marala/rainfall/nasa_power/`; weights, clipped cell geometry and processed values are under `processed/marala/rainfall/`.

NASA POWER returns MERRA2 and GEOSIT source headers. Retain this retrieved snapshot, keep UTC accumulation boundaries explicit and apply source-availability constraints before combining with discharge. The history does not replace archived 15-day weather forecasts. A day with any missing required source cell is not assigned a full-catchment mean.

## Marala upstream research boundary checked 2026-10-23

The [upstream catchment](chenab_marala/processed/marala/catchment/marala_upstream_catchment.geojson) and [verification evidence](chenab_marala/processed/marala/catchment/README.md) are saved under `processed/marala/catchment/`, with originals and references under `raw/marala/catchment/`. The high-precision Global Watersheds/MERIT-derived polygon is 28,780.646 km2. Nine checks passed, including the JICA/PMD station location, comparison with the PMD published area, valid geometry, nearby-outlet sensitivity and downstream exclusion. This is a source- and geometry-checked research delineation, not an agency-certified or surveyed polygon.

The rebuilt rainfall grid covers the entire catchment with 21 cells. The former western gap is filled, and the daily area-weighted catchment precipitation series has been calculated. Basin-boundary verification remains at the documented research level.

## Feature coverage audit and rainfall training hold, 2026-10-23

The [coverage audit](chenab_marala/processed/marala/metadata/marala_feature_coverage_audit.json) confirms a nonmissing catchment precipitation value for every WAPDA date from 2016-03-01 through 2024-12-19, with 3,209 structurally eligible discharge/rainfall pairs after the seven discharge exclusions. These dates do not establish intraday alignment or operational availability. Temperature, snow conditions, soil moisture, soil properties and archived future-weather forecasts are not yet collected.

Training with the saved rainfall values is on hold. Independent short-period NASA daily and summed-hourly checks disagree with the saved long-period response at sampled wet dates, with a factor of 24 in two examples. Repeating the original long-period request reproduces the discrepancy. Resolve source consistency using validated shorter-period downloads and multiple independent checks before rebuilding rainfall features; do not apply an assumed blanket scaling correction. Original data is preserved, with spot-check evidence under `raw/marala/rainfall/nasa_power/verification_2026-10-23/`. The local portal now displays this hold.
