# Daily Marala snow features, 1980–2024

Script: `extract_snow.py`. Run from `raw/marala` using the installed environment:

```powershell
& './rainfall/google_earth_engine/.venv/Scripts/python.exe' -u extract_snow.py --project n8n-gmail-send-503521
```

The default polygon is the project's checked
`processed/marala/catchment/marala_upstream_catchment.geojson`. To select your
file named `marala_catchment.geojson`, add `--catchment 'PATH/marala_catchment.geojson'`.

| Source band / yearly export folder | Output column | Conversion |
|---|---|---|
| snow_depth_water_equivalent | swe_mm | metres of water × 1000 → mm |
| snow_depth | snow_depth_m | metres of snow, unchanged |
| snowmelt_sum | snowmelt_mm | daily metres of water × 1000 → mm/day |

Each folder holds `1980.csv` through `2024.csv`, with **daily rows**. On completion,
the script writes `marala_daily_snow_1980_2024.csv` alongside the script, with
`date,swe_mm,snow_depth_m,snowmelt_mm`. The full 16,437-day calendar is retained;
missing values are NaN. `snow_quality_report.json` records missing days and min/max
for each variable, also printed to `snow_extraction.log`. Errors go to `snow_errors.log`.
`snow_manifest.json` records source bands, units, polygon hash and settings.

All variables use the requested `reduceRegion(ee.Reducer.mean(), scale=11132)` in
the source CRS. This weights boundary pixel fractions and excludes masked cells;
it does not add a separate physical pixel-area weight or coverage threshold.
Valid zero-snow cells remain in the catchment average. No snow-cover mask,
division by snow fraction, negative-value clipping or gap filling is applied.

SWE and snow depth represent daily mean states from the daily collection;
snowmelt is a daily accumulated flux. Dates are 00:00–24:00 UTC (05:00–05:00 next
day Pakistan time). Earth Engine already labels `_sum` for the accumulated day.

Completed years are reused on restart. If a yearly request exceeds online limits,
smaller requests are combined back into yearly files. `--merge-only` rebuilds the
combined CSV and report from existing exports without Earth Engine authentication.

[Source definitions](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR).
