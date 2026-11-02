# Daily Marala dewpoint and downward solar radiation

Script: `extract_dewpoint_ssrd.py`. Uses `ECMWF/ERA5_LAND/DAILY_AGGR` for
1980-01-01 through 2024-12-31, inclusive (16,437 daily rows).

From this directory, using the already installed Earth Engine environment:

```powershell
& './rainfall/google_earth_engine/.venv/Scripts/python.exe' -u extract_dewpoint_ssrd.py --project n8n-gmail-send-503521
```

The default polygon is the project's existing
`processed/marala/catchment/marala_upstream_catchment.geojson`. To use a file
named `marala_catchment.geojson`, add `--catchment 'PATH/marala_catchment.geojson'`.
No new catchment is delineated.

- `dewpoint_temperature/YYYY.csv`: `date,dewpoint_c`.
- `surface_solar_radiation_downwards_sum/YYYY.csv`: `date,ssrd_wm2`.
- `marala_daily_dewpoint_ssrd_1980_2024.csv`: `date,dewpoint_c,ssrd_wm2`.
- `dewpoint_ssrd_quality_report.json`: missing dates, valid-day counts, units,
  min/max and merged-file checksum. Missing dates and min/max are also printed.
- `dewpoint_ssrd_manifest.json`: catchment hash, source bands and settings.
- `dewpoint_ssrd_extraction.log` / `dewpoint_ssrd_errors.log`: background-job logs.

Each yearly export contains **daily** values. Completed years are reused on
restart. If an annual request reaches online limits, smaller requests are merged
back into the same yearly files. The final CSV retains the entire calendar and
uses NaN for missing values. Rebuild it from saved yearly files with `--merge-only`.
Precipitation and air-temperature jobs are independent and are not modified.

Conversions: dewpoint K minus 273.15 gives degrees C; negative dewpoints are valid.
Daily downward solar energy J/m2 divided by 86,400 seconds gives the **daily mean
flux in W/m2**, not an instantaneous flux. Source values are not clipped.

The requested `reduceRegion(ee.Reducer.mean(), scale=11132)` is used in the source
CRS. Boundary pixels receive fractional overlap weights; masked pixels are excluded.
Unlike the earlier precipitation/temperature scripts, this requested plain mean
does not add explicit pixel-area weighting for geographic cells of varying area,
and does not enforce a minimum valid spatial coverage fraction.

Days are 00:00–24:00 UTC, equivalent to 05:00–05:00 next day in Pakistan. The daily
solar `_sum` is already labeled for the accumulated day by Earth Engine; do not
shift it to the next date. Exact Pakistan-midnight aggregation requires hourly data.

[Earth Engine source and units](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR).
