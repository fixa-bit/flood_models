# Original Marala catchment precipitation downloads

**New investigation, 26 October 2026:** The original NASA POWER `cells/` downloads remain unchanged. New request-range checks and fresh 2016–2024 responses are under `nasa_power/investigation_2026-10-26/`; independently acquired IMERG numeric subsets and source metadata are under `imerg/noaa_aoml/comparison_2026-10-26/`; original CHIRPS v3 GeoTIFFs are under `chirps_v3/rnl/comparison_2026-10-26/`. Each source response has an adjacent receipt with exact URL, retrieval time and SHA-256. See the [source investigation](../../../processed/marala/rainfall/source_comparison_2026-10-26/README.md) for findings and caveats.

This rainfall dataset was rebuilt from fresh downloads on 2026-10-23 using the [Marala upstream catchment](../../../processed/marala/catchment/marala_upstream_catchment.geojson). The previous annual regional JSON files and their processed regional table were deleted at the user's request.

`nasa_power/cells/` contains one original [NASA POWER daily point-API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) response per required native grid cell, plus its source URL, retrieval timestamps and SHA-256 receipt. The 21 cells cover the complete catchment; selection uses cell-footprint intersections rather than center points alone. [source_receipt.json](nasa_power/source_receipt.json) contains the aggregate source manifest.

Use the [processed catchment precipitation notes](../../../processed/marala/rainfall/README.md) for the daily basin-mean table, cell weights, missing-data rules and UTC/Pakistan time periods.
