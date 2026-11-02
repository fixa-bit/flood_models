# Marala daily temperature, 1980–2024

Independent temperature extraction that can run alongside the precipitation job.
Source: `ECMWF/ERA5_LAND/DAILY_AGGR`, band `temperature_2m` (daily mean),
converted from kelvin to degrees Celsius by subtracting 273.15.
This is 2 m air temperature, not surface skin temperature or daily minimum/maximum.

Reuses the existing checked catchment and Earth Engine environment in
`raw/marala/rainfall/google_earth_engine/.venv`. Example from this directory:

```powershell
& '../../rainfall/google_earth_engine/.venv/Scripts/python.exe' extract_temperature.py --project n8n-gmail-send-503521
```

`chunks/era5land_temperature_2m/` holds monthly files with **daily rows** and
coverage/image-count diagnostics. Completed exports are reused on restart.
The final `marala_daily_temperature_1980_2024.csv` has columns
`date,era5land_temperature_2m_c` and all 16,437 daily dates. Missing values are NaN.
`quality_report.json` records missing dates, descriptive statistics and CSV hash;
`annual_temperature_means.csv` reports full-year average temperature, not totals.
Negative Celsius temperatures are valid and are never clipped.

Native affine grid and physical pixel-area weights are retained. Boundary pixels
are weighted by their intersection fraction using the Earth Engine weighted mean
reducer (approximately 1/256 fraction precision). Days with less than 99.9% valid
catchment coverage or without exactly one source daily image become NaN.
Each daily mean represents 00:00–24:00 UTC (05:00–05:00 next day Pakistan time).
Exact local-midnight means require hourly data, not relabeled daily values.

The precipitation files remain precipitation-only. Temperature is separate and
can later be joined to training inputs by date, respecting forecast availability.
This script does not yet add temperature to portal charts.

[Source and band documentation](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR).
