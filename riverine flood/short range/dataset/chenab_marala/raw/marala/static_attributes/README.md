# Static Marala catchment attributes

Run from this folder with the installed Earth Engine environment:

```powershell
& '../rainfall/google_earth_engine/.venv/Scripts/python.exe' -u extract_static_attributes.py --project n8n-gmail-send-503521
```

The checked project catchment is used by default. To use your named polygon,
add `--catchment 'PATH/marala_catchment.geojson'`. No delineation is performed.
The final `marala_static_attributes.csv` contains **one row** and all requested
columns. `landcover_*` names map to the 11 WorldCover classes in the script.
Section JSON files cache intermediate results for restart after network failures;
`run_manifest.json` prevents reusing them for a different polygon/method.
`quality_report.json` records fraction/soil sums and the final CSV checksum.
`extraction.log` and `extraction_errors.log` track the background extraction.

Methods:

- Area is Earth Engine geodesic polygon area in km2.
- MERIT DEM `dem` provides elevation in metres and slopes in degrees at 90 m.
  Slope is derived before clipping to avoid creating a catchment-edge artifact.
  Elevation percentiles use Earth Engine's histogram percentile reducer at 90 m.
  Mean elevation and slope use pixel-area weights and boundary intersection
  weights; their common valid mask is retained.
- Elevation bands are `<1500`, `1500 <= z < 3000`, `3000 <= z <= 4500`, `z > 4500`
  metres. Fractions use physical area at 90 m and the full catchment grid area as
  denominator. No-data cells are not silently renormalized into the valid bands.
- The glacier source is **GLIMS/current**, not RGI. `GLIMS/GLACIERS` is not the
  catalog ID. Records are restricted to glacier boundaries, the latest analysis
  timestamp per glacier ID is selected, and rows sharing those analysis IDs are
  retained. Their union is dissolved and clipped to the catchment before its
  vector area is divided by catchment area. Historical overlaps are not summed.
  GLIMS contains heterogeneous outline dates; this is not a uniform-year RGI
  inventory. The catalog's current snapshot is documented as June 2023.
- ESA WorldCover v200 represents **2021**. Class fractions use physical area at
  the requested 90 m sampling scale, with nearest-neighbor class sampling from
  native 10 m data. These are 90 m approximations; small classes can be missed.
  Full-catchment denominator is used, so unclassified/missing cells can make the
  class fractions sum to less than one.
- OpenLandMap supplies numeric **sand/clay percentages**, rather than USDA
  categorical texture-class codes. Its depths are point predictions at 0, 10,
  30 cm, not a precomputed 0–30 cm layer. Trapezoidal integration gives
  `(b0 + 3*b10 + 2*b30)/6`. Silt is the residual `100 - sand - clay`.
  Inconsistent predictions with negative residual silt are masked for all three
  variables; area-weighted means over remaining valid soil pixels use 250 m.
  They describe available modeled soils, not measured soil beneath glaciers.
- Climate is calculated independently from Earth Engine daily ERA5-Land,
  1980-01-01 through 2024-12-31. The script checks for 16,437 images. Daily
  precipitation sums are converted m -> mm and summed over the period, then
  divided by **45**, giving mean annual precipitation in **mm/year** (column
  `precip_mean_mm`). PET is likewise multiplied by -1000 and divided by 45.
  Means use physical pixel-area weights at the native ERA5-Land scale.
  `aridity` is mean annual PET / mean annual precipitation, dimensionless.
  Source values are not clipped or taken in absolute value. This climate
  calculation does not depend on completion of the separate daily download jobs.

The requested features combine datasets from different epochs. For forecast
validation, climate normals should be recomputed using only the training period
if they are used as predictors; the requested 1980–2024 normal includes that
entire period.

Primary sources:

- [MERIT DEM](https://developers.google.com/earth-engine/datasets/catalog/MERIT_DEM_v1_0_3)
- [GLIMS/current and its historical rows](https://developers.google.com/earth-engine/datasets/catalog/GLIMS_current)
- [WorldCover 2021 v200](https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200)
- [Sand percentages and depth bands](https://developers.google.com/earth-engine/datasets/catalog/OpenLandMap_SOL_SOL_SAND-WFRACTION_USDA-3A1A1A_M_v02)
- [Clay percentages and depth bands](https://developers.google.com/earth-engine/datasets/catalog/OpenLandMap_SOL_SOL_CLAY-WFRACTION_USDA-3A1A1A_M_v02)
- [ERA5-Land daily aggregation and units](https://developers.google.com/earth-engine/datasets/catalog/ECMWF_ERA5_LAND_DAILY_AGGR)
