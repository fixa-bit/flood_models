# Original Marala catchment precipitation downloads

**Preferred CHIRPS collection (28 October 2026):** Historical Final RNL compressed chunks, metadata and checksum receipts are under `chirps_v3/rnl/historical_1990_2026/compact_copy_zarr/`. The compact copy is a third-party, 0.1-mm-quantized conversion of the CHC original GeoTIFFs. September 2026 Final and October 2026 Preliminary were read directly from CHC GeoTIFFs; exact catchment raster windows and source-header receipts are under `chirps_v3/rnl/historical_1990_2026/official_final_clips/` and `chirps_v3/sat/preliminary_2026/official_clips/`. The saved windows are not full original global GeoTIFFs. Provider archive listings checked on each collection date are under `chirps_v3/source_indexes_YYYY-MM-DD/`. See the [preferred processed series](../../../processed/marala/rainfall/chirps_v3_primary/README.md) for coverage and quality checks.

**New investigation, 26 October 2026:** The original NASA POWER `cells/` downloads remain unchanged. New request-range checks and fresh 2016–2024 responses are under `nasa_power/investigation_2026-10-26/`; independently acquired IMERG numeric subsets and source metadata are under `imerg/noaa_aoml/comparison_2026-10-26/`; original CHIRPS v3 GeoTIFFs are under `chirps_v3/rnl/comparison_2026-10-26/`. Each source response has an adjacent receipt with exact URL, retrieval time and SHA-256. See the [source investigation](../../../processed/marala/rainfall/source_comparison_2026-10-26/README.md) for findings and caveats.

This rainfall dataset was rebuilt from fresh downloads on 2026-10-23 using the [Marala upstream catchment](../../../processed/marala/catchment/marala_upstream_catchment.geojson). The previous annual regional JSON files and their processed regional table were deleted at the user's request.

`nasa_power/cells/` contains one original [NASA POWER daily point-API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/) response per required native grid cell, plus its source URL, retrieval timestamps and SHA-256 receipt. The 21 cells cover the complete catchment; selection uses cell-footprint intersections rather than center points alone. [source_receipt.json](nasa_power/source_receipt.json) contains the aggregate source manifest.

Use the [processed catchment precipitation notes](../../../processed/marala/rainfall/README.md) for the daily basin-mean table, cell weights, missing-data rules and UTC/Pakistan time periods.



NASA IMERG, NOAA CPC gauge-based analysis, and ERA5-Land reanalysis



ERA5-Land provides total precipitation as one of its standard variables.

What it is

ERA5-Land is a land-surface reanalysis from ECMWF, produced by running a land model forced with atmospheric data from ERA5.
Its precipitation is not directly measured. It comes from the underlying ERA5 atmospheric model, which assimilates observations but computes rainfall itself.
Resolution is about 9 km (0.1°), hourly, with a global record going back to 1950.

How it differs from IMERG and CPC

IMERG: based on satellite observations, so it is a more direct estimate of actual rainfall.
CPC: based on rain gauge measurements, so it is good where gauges are dense.
ERA5-Land: model-derived, so it is available everywhere and for a long period, but it can have more bias in some regions, especially for intense or localized rain.


Dont:
Not directly. The NOAA source I mentioned for Flood Hub’s rainfall inputs is CPC (Climate Prediction Center), which produces gauge-based global precipitation analyses. AOML is a research lab focused on oceans and hurricanes, not a rainfall data provider for that model.



CHIRPS can underestimate extreme precipitation in complex terrain. 
Source: https://chc.ucsb.edu/data/chirps

IMERG precipitation is less certain in mountains, and V07 has deficient snowfall estimates. NASA documentation
Source: https://gpm.nasa.gov/data/imerg


Google Earth Engine hosts the data; it doesn’t produce the precipitation estimates. We’re downloading four separate products through it:
Product	Producer and underlying source

ERA5-Land	ECMWF — weather-model reanalysis driven by ERA5 atmospheric data

CHIRPS v2	UC Santa Barbara Climate Hazards Center — satellite infrared estimates combined with rain-gauge observations

PERSIANN-CDR	UC Irvine / NOAA archive — satellite infrared estimates adjusted using monthly GPCP precipitation

IMERG V07 Final	NASA — combined satellite microwave and infrared estimates, adjusted using monthly rain-gauge analyses


| Column | Value | Meaning |
|---|---:|---|
| `date` | 1996-07-31 | Day represented |
| `value_mm` | **12.4309** | Area-weighted catchment-mean precipitation: **12.43 mm that day** |
| `raw_min_mm` | 3.9085 | Lowest original precipitation value among the included grid pixels |
| `negative_area_fraction` | 0.0 | No included area had negative precipitation |
| `coverage_fraction` | 1.0 | Full catchment coverage |
| `n_images` | 1 | One daily source image was used |