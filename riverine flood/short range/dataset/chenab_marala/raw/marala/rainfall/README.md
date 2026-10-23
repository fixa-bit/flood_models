# Original Marala catchment precipitation downloads

This rainfall dataset was rebuilt from fresh downloads on 2026-10-23 using the [Marala upstream catchment](../../../processed/marala/catchment/marala_upstream_catchment.geojson). The previous annual regional JSON files and their processed regional table were deleted at the user's request.

`nasa_power/cells/` contains one original [NASA POWER daily point-API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) response per required native grid cell, plus its source URL, retrieval timestamps and SHA-256 receipt. The 21 cells cover the complete catchment; selection uses cell-footprint intersections rather than center points alone. [source_receipt.json](nasa_power/source_receipt.json) contains the aggregate source manifest.

Use the [processed catchment precipitation notes](../../../processed/marala/rainfall/README.md) for the daily basin-mean table, cell weights, missing-data rules and UTC/Pakistan time periods.
