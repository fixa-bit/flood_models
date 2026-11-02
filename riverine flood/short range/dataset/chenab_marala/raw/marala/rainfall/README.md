# Original Marala catchment precipitation downloads

**Earth Engine extraction:** `google_earth_engine/chunks/` contains resumable
monthly precipitation exports for ERA5-Land, CHIRPS v2, PERSIANN-CDR and IMERG V07.
The merged 1980–2024 CSV and QA reports are written to `google_earth_engine/`
when extraction finishes. See [the extraction instructions](google_earth_engine/README.md).

**Preferred CHIRPS collection (28 October 2026):** Historical Final RNL compressed chunks, metadata and checksum receipts are under `chirps_v3/rnl/historical_1990_2026/compact_copy_zarr/`. The compact copy is a third-party, 0.1-mm-quantized conversion of the CHC original GeoTIFFs. September 2026 Final and October 2026 Preliminary were read directly from CHC GeoTIFFs; exact catchment raster windows and source-header receipts are under `chirps_v3/rnl/historical_1990_2026/official_final_clips/` and `chirps_v3/sat/preliminary_2026/official_clips/`. The saved windows are not full original global GeoTIFFs. Provider archive listings checked on each collection date are under `chirps_v3/source_indexes_YYYY-MM-DD/`. See the [preferred processed series](../../../processed/marala/rainfall/chirps_v3_primary/README.md) for coverage and quality checks.

**New investigation, 26 October 2026:** The original NASA POWER `cells/` downloads remain unchanged. New request-range checks and fresh 2016–2024 responses are under `nasa_power/investigation_2026-10-26/`; original CHIRPS v3 GeoTIFFs are under `chirps_v3/rnl/comparison_2026-10-26/`. Each retained source response has an adjacent receipt with exact URL, retrieval time and SHA-256. See the [source investigation](../../../processed/marala/rainfall/source_comparison_2026-10-26/README.md) for findings and caveats.

This rainfall dataset was rebuilt from fresh downloads on 2026-10-23 using the [Marala upstream catchment](../../../processed/marala/catchment/marala_upstream_catchment.geojson). The previous annual regional JSON files and their processed regional table were deleted at the user's request.

`nasa_power/cells/` contains one original [NASA POWER daily point-API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) response per required native grid cell, plus its source URL, retrieval timestamps and SHA-256 receipt. The 21 cells cover the complete catchment; selection uses cell-footprint intersections rather than center points alone. [source_receipt.json](nasa_power/source_receipt.json) contains the aggregate source manifest.

Use the [processed catchment precipitation notes](../../../processed/marala/rainfall/README.md) for the daily basin-mean table, cell weights, missing-data rules and UTC/Pakistan time periods.
