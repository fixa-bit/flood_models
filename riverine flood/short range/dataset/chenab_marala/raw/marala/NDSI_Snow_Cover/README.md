# MODIS Terra daily snow-cover index at Marala

Source: `MODIS/061/MOD10A1`, band `NDSI_Snow_Cover`.
Period: 2000-03-01 through 2024-12-31 inclusive.

From this directory, use the existing Earth Engine Python environment:

```powershell
& '../rainfall/google_earth_engine/.venv/Scripts/python.exe' -u extract_modis_snow_cover.py --project n8n-gmail-send-503521
```

By default the project's checked catchment is loaded from
`processed/marala/catchment/marala_upstream_catchment.geojson`.
For your file, add `--catchment 'PATH/marala_catchment.geojson'`.

Yearly `2000.csv` through `2024.csv` contain daily rows; 2000 starts on 1 March.
The final `marala_daily_modis_snow_cover_2000_2024.csv` has exactly
`date,snow_cover_pct,valid_frac`. `quality_report.json` contains missing dates,
valid counts, min/max, and a checksum. Statistics are also printed to `extraction.log`;
background-job errors go to `extraction_errors.log`. Completed years are reused
on restart. Requests now default to seven days (`--chunk-days 7`) to reduce
concurrent aggregation errors. They are cached under `chunks/` before being
assembled into the yearly exports; completed chunks survive interruptions.
Smaller fallback requests are used if a chunk still exceeds online limits.
`--merge-only` rebuilds the combined CSV and report without authentication.

**Interpretation:** the requested column name `snow_cover_pct` is retained, but
MODIS V6.1 `NDSI_Snow_Cover` is an NDSI-based index scaled 0–100, **not fractional
snow-covered area percent**. No thresholding or fractional-area model is added.
`valid_frac` is the fraction of the entire catchment's 500 m grid with valid
0–100 values, using the same fractional polygon-boundary weights as the mean.
For example 0.4 means 40% valid coverage, not 40% snow.

Provider flags above 100 are already masked in Earth Engine's selected band;
the code explicitly enforces 0–100 as well. Validity is unmasked to zero across
the entire catchment (including missing image footprints), preventing cloud and
missing pixels from disappearing from the valid-fraction denominator. On days
with no valid pixels, `snow_cover_pct` is NaN and `valid_frac` is zero. Entirely
missing source days likewise have NaN/zero. No snow-free zeros are removed.

Reductions use `ee.Reducer.mean()`, scale 500 m, `maxPixels=1e13` and `tileScale=4`
in the original MODIS sinusoidal CRS. An explicit CRS prevents daily mosaics from
being reduced on the default one-degree geographic grid. MODIS sinusoidal cells
are equal-area; boundary coverage fractions are approximated by Earth Engine.
No temporal interpolation, cloud gap filling, or additional QA filtering is applied.
Dates use the source daily UTC labels; these optical observations are selected
daytime acquisitions, not 24-hour mean snow observations.

- [Earth Engine band and pre-masked flags](https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD10A1)
- [NSIDC: NDSI snow cover versus fractional snow cover](https://nsidc.org/data/user-resources/help-center/what-ndsi-snow-cover-and-how-does-it-compare-fsc)
