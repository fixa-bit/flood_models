# Preferred Marala catchment rainfall: CHIRPS v3

This is the new **preferred historical rainfall source** for the saved Marala upstream catchment. It is a catchment-area-weighted rainfall depth, not a rain-gauge reading at Marala and not a sum of rainfall depths across pixels. The older NASA POWER files remain in their own folders for a later comparison; they were not used to build this series.

## Coverage and files

| Series | Dates available in this collection | Daily method | Status |
|---|---|---|---|
| [Final RNL daily catchment rainfall](marala_chirps_v3_final_rnl_daily_1990_2026.csv) | 1990-01-01 through 2026-09-30; **13,422 of 13,422 days complete** | ERA5 allocates CHIRPS pentad totals among days | Preferred historical candidate |
| [Preliminary SAT daily catchment rainfall](marala_chirps_v3_preliminary_sat_2026.csv) | 2026-10-01 through 2026-10-20; **20 of 20 available days complete** | IMERG Late V07 allocates pentad totals among days | Separate provisional series; replace with Final when released |

The provider's archive had no later daily values when checked on **28 October 2026**. The Final and Preliminary series must not be silently joined because their daily allocation methods differ. All rows carry the product edition, source representation, source URL, UTC period label, area-coverage fraction, quality flag and training status. [Collection report](collection_report.json) gives counts by year and the saved source-index receipts.

The [1,266 intersecting CHIRPS cells and area weights](chirps_v3_marala_cell_weights.csv) cover the entire [saved upstream catchment](../../catchment/marala_upstream_catchment.geojson). Each cell is weighted by its intersection area in an equal-area projection. If any contributing cell is missing on a day, the catchment value is blank instead of reweighting the remaining cells. No days in this collection needed that rule.

## What was downloaded

For 1990 through August 2026, the collector saved compressed chunks from a [public compact CHIRPS v3 Final RNL copy](https://huggingface.co/datasets/aaguilar90/chirps-v3-daily-rnl). That copy is a **third-party conversion** of the [CHC original GeoTIFF archive](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/final/rnl/), rounded to 0.1 mm per grid cell. Its exact downloaded chunk bytes, metadata, URLs, retrieval times and SHA-256 receipts are in `raw/marala/rainfall/chirps_v3/rnl/historical_1990_2026/compact_copy_zarr/`. The historical series therefore does not claim bit-for-bit precision of every original CHC GeoTIFF.

For September 2026 Final and October 2026 Preliminary, the collector read the [CHC provider's original daily GeoTIFFs](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/), saved exact float32 windows over the catchment, and recorded original URLs, file size, modification headers and checksums of each saved window. Those windows are in the separate `official_final_clips/` and `official_clips/` source folders. Their receipts clearly state that the saved window is **not** a full original GeoTIFF.

As a precision check, [ten catchment dates](compact_copy_official_geotiff_check.csv) were independently calculated from full original CHC GeoTIFFs saved in the earlier source audit. Every compact-copy catchment mean was within **0.0015 mm** of the corresponding original GeoTIFF mean (maximum absolute difference: 0.001444 mm). This checks the conversion on sampled dates; it does not prove every pixel or day is identical.

Two additional [graph validation dates](graph_precipitation_official_checks_2024.csv) were checked against full original CHC GeoTIFFs: 30 January 2024 differs by **0.000651 mm** and 13 March 2024 by **0.000873 mm** from the compact-copy catchment means. The downloaded TIFFs and checksum receipts are saved under `raw/marala/rainfall/chirps_v3/rnl/comparison_2026-10-26/`. These checks verify plotted CHIRPS values against the official raster for those dates; they do not establish that CHIRPS matches ground rain gauges.

## How to interpret a daily value

CHIRPS v3 is fundamentally blended at pentad and monthly steps; daily RNL uses ERA5 to distribute a pentad's rainfall among UTC dates. Daily SAT uses IMERG Late V07 instead. CHC cautions that contributing stations may use different observation windows, so a daily date is a consistent **UTC label**, not proof that every station measured exactly 00:00–00:00 UTC. [CHC daily documentation](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/readme.txt)

The values are observed or analyzed **historical** rainfall. A future 15-day discharge forecast will need a separate future-rainfall forecast or a model that does not require future rainfall input. Before using any historical day as a predictor, check that the relevant CHIRPS edition would actually have been published by the forecast issue time.

## Reproduce

Install `scripts/requirements.txt`, then run from any directory:

```powershell
python "riverine flood/short range/dataset/chenab_marala/scripts/collect_marala_chirps_v3.py"
```

The collector checks saved download hashes on reruns, recomputes the catchment means, checks date continuity and coverage, and validates the compact copy against the ten original CHC samples. It does not modify NASA POWER data.
