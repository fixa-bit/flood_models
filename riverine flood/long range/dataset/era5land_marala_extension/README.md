# ERA5-Land Marala forcing extension (2025 onward)

The short-range dataset has ERA5-Land catchment means for 1980-01-01 to 2024-12-31. Observed Marala inflow (Sindh rim-station bulletins) continues to 2026-11. This folder extends the forcing so the long-range models can be tested after 2024.

| File | What it is |
|---|---|
| `extract_era5land_extension.py` | Earth Engine extractor (`ECMWF/ERA5_LAND/DAILY_AGGR`), 2024-01-01 to the latest available day |
| `marala_era5land_daily_<start>_<end>.csv` | Daily catchment means: `precip_era5land_mm, temperature_c, dewpoint_c, pet_mm, snowmelt_mm, snow_depth_m, swe_mm, ssrd_wm2` |
| `source_receipt.json` | Methods, conversions, catchment hashes, missing days, file hash |
| `verify_overlap.py` / `overlap_verification.json` | 2024 re-extraction compared with the stored short-range 2024 values |

## Method

The extractor copies the two short-range methods exactly, each with the catchment file that method used:

- **Precipitation, 2 m temperature:** native-grid area-weighted mean (`Reducer.mean().splitWeights()` with `pixelArea`). Catchment is `raw/marala/rainfall/google_earth_engine/marala_upstream_catchment.geojson`. Negative ERA5 precipitation is clipped to 0, as in short range.
- **Dewpoint, PET, snowmelt, snow depth, SWE, solar radiation:** `Reducer.mean()` at 11 132 m. Catchment is `processed/marala/catchment/marala_upstream_catchment.geojson`.

2024 is extracted only to verify the method. The models use the short-range files up to 2024-12-31 and this file only for dates after that. Days with no source image are left out, never filled.

## 2024 overlap check

Temperature, dewpoint, snow depth and SWE match the stored series exactly. Snowmelt and solar radiation agree to within 0.006 (units as stored).

Precipitation and PET fail the strict tolerance:

- **Precipitation:** mean absolute difference 0.19 mm/day, maximum 4.8 mm/day.
- **PET:** maximum difference 0.024 mm/day, against a tolerance of 0.02.

For precipitation, the differences come in day pairs: one day gains what the next day loses (for example 2024-08-06 +4.78 and 2024-08-07 −4.57 mm). There is no date shift, and the 2024 totals agree (1275.16 vs 1275.12 mm). Earth Engine's current daily aggregate therefore assigns rain to days slightly differently from the copy downloaded for short range. Use this file from 2025-01-01 onward only, and keep that boundary in mind when comparing 2025+ results with earlier years.

## Re-run

```powershell
cd "riverine flood/long range/dataset/era5land_marala_extension"
../../.venv/Scripts/python.exe extract_era5land_extension.py --project <earth-engine-project>
../../.venv/Scripts/python.exe verify_overlap.py
```
