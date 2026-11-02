# Daily Marala potential evaporation (PET)

Source: `ECMWF/ERA5_LAND/DAILY_AGGR`, band `potential_evaporation_sum`.
Period: 1980-01-01 through 2024-12-31, inclusive; 16,437 daily dates.

Run from this folder using the existing Earth Engine Python environment:

```powershell
& '../rainfall/google_earth_engine/.venv/Scripts/python.exe' -u extract_pet.py --project n8n-gmail-send-503521
```

The project's checked `marala_upstream_catchment.geojson` is loaded by default.
To use your file named `marala_catchment.geojson`, add
`--catchment 'PATH/marala_catchment.geojson'`.

- `1980.csv` through `2024.csv`: yearly exports containing daily `date,pet_mm` rows.
- `marala_daily_pet_1980_2024.csv`: merged full calendar; NaN for missing values.
- `quality_report.json`: missing days, valid count, min/max, and negative count.
- `run_manifest.json`: source, polygon checksum and settings for consistent resumes.
- `extraction.log` / `extraction_errors.log`: background download progress/errors.

The conversion is `potential_evaporation_sum * 1000 * -1`: metres to millimetres,
then reverse the ECMWF sign so evaporation becomes positive. Values are not
absolutized or clipped; any negative result after reversal is reported for review.
The source daily sum needs no additional division by time. Days are UTC calendar
days (05:00–05:00 next day Pakistan time), already labeled for the accumulated day.

As requested, the reduction is `reduceRegion(ee.Reducer.mean(), scale=11132)` in
the source CRS. Boundary fractions are weighted, masked cells excluded, and no
additional pixel-area weight or spatial coverage threshold is applied. This is
the requested plain grid mean, consistent with the dewpoint/solar extraction.

Completed years are reused on restart; downloads retry transient failures.
Use `--merge-only` to rebuild the final CSV and statistics from saved yearly files.
No precipitation, temperature, dewpoint or solar source files are altered.

[Source band documentation](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR).
