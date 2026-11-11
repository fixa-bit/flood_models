# NEX-GDDP-CMIP6 for the Marala catchment

Daily catchment-mean precipitation and 2 m air temperature from NASA's NEX-GDDP-CMIP6 (0.25°, BCSD-downscaled CMIP6; Thrasher et al. 2022). They were read through Google Earth Engine (`NASA/GDDP-CMIP6`). These files drive the 2026–2040 projections in [`../../model/projection`](../../model/projection/).

| Item | Value |
|---|---|
| GCMs | ACCESS-CM2, CNRM-CM6-1, EC-Earth3, GFDL-ESM4, MIROC6, MPI-ESM1-2-HR, MRI-ESM2-0, NorESM2-MM |
| Experiments | `historical` 1985–2014 (bias-correction reference period); `ssp245` and `ssp585` 2024–2040 (2024–2025 = model spin-up) |
| Catchment | `short range/dataset/chenab_marala/processed/marala/catchment/marala_upstream_catchment.geojson` |
| Reduction | `ee.Reducer.mean()` at the native 27 830 m scale (fractional boundary weights) |
| Units | `pr_mm` = pr × 86 400 (mm/day); `tas_c` = tas − 273.15 (°C) |
| Versions | Where a model has several dataset versions for a day, the highest `version` is kept (recorded per row) |

Files: `<GCM>_<experiment>.csv` (`date, pr_mm, tas_c, version`), plus `source_receipt.json` (row counts, versions, hashes, catchment hash) and `download.log`.

The values here are **raw GCM output** at catchment scale. Bias correction to ERA5-Land happens at run time in `model/projection/run_projection.py`, using quantile mapping for historical runs and quantile delta mapping for scenarios. Nothing in this folder is corrected or filled.

## Re-run

```powershell
cd "riverine flood/long range/dataset/nex_gddp_cmip6_marala"
../../.venv/Scripts/python.exe extract_nex_gddp_cmip6.py --project <earth-engine-project>
```

The script skips files already listed in the receipt. One model is about 7 minutes (4 parallel requests).
