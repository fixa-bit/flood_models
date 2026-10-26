# Marala catchment precipitation

**October 2026 quality update:** A [separate source investigation](source_comparison_2026-10-26/README.md) confirmed that the original long-range NASA POWER request gives request-dependent historical values. Across 67,788 overlapping 2016–2024 cell-days, 34,355 positive original values were 24 times fresh historical requests while 5,681 positive values already matched. The original series is preserved and remains **on hold for training**. The investigation also saves a fresh 2016–2024 POWER candidate and limited catchment comparisons with IMERG and CHIRPS; none is a validated replacement training input yet.

The previous regional rainfall download was deleted at the user's request and replaced with fresh NASA POWER downloads selected using the saved Marala upstream catchment. The main model input is [marala_catchment_daily_precipitation.csv](marala_catchment_daily_precipitation.csv): one area-weighted precipitation value per UTC day for the full catchment.

| Property | Current dataset |
|---|---|
| Parameter | NASA POWER `PRECTOTCORR`, corrected precipitation |
| Units | mm/day, averaged over the catchment area |
| Requested history | 2016-03-01 through 2026-10-22 |
| Complete daily values | 3,887, through 2026-10-21 |
| Missing daily value | 2026-10-22, retained blank and flagged |
| Required source cells | 21, all intersecting the catchment |
| Spatial coverage | 100% of the saved catchment |
| Equal-area catchment size | 28,780.646 km2 |
| Source headers | MERRA2 and GEOSIT; exact per-date transition is not exposed |

## How the catchment is used

The [checked research boundary](../catchment/marala_upstream_catchment.geojson) determines which source cells are needed. NASA's meteorological grid is 0.5 degrees latitude by 0.625 degrees longitude. Each native grid footprint is intersected with the catchment. Cells that contribute any positive area are retained, including edge cells whose center lies outside the polygon. Other cells are excluded.

Geographic edges are densified to at most 0.005 degrees before projection into a WGS84 Lambert azimuthal equal-area CRS centered at 33 N, 76 E. Each weight equals the area of the cell/catchment intersection divided by the complete catchment area. The weights sum to one, and their union covers the full boundary. This includes the small western area omitted by the previous download.

For a given day, the catchment mean is the sum of each cell's precipitation multiplied by its area weight. This treats the gridded precipitation estimate as uniform within its source cell. No precipitation outside the catchment contributes area to the weights. The data are coarse gridded estimates, rather than direct rain-gauge measurements or rainfall-only phase observations.

## Files

- [Daily catchment mean](marala_catchment_daily_precipitation.csv): the main time series, including UTC and Pakistan period start/end boundaries, valid-area fraction and quality flags.
- [Grid weights](marala_rainfall_grid_cells.csv): the 21 cell centers, catchment intersection areas and weights.
- [Clipped grid geometries](marala_rainfall_catchment_cells.geojson): cell/catchment intersections for GIS review.
- [Daily source-cell values](marala_catchment_grid_daily_precipitation.csv): 81,648 cell-days, including source URLs and original filenames; 21 values are missing on 2026-10-22.
- [Collection report](marala_rainfall_collection_report.json): boundary checksum, area method, coverage, units, source headers, missing dates, download timestamps and original-file checksums.
- [Validation report](marala_rainfall_validation_report.json): all daily means recomputed from the raw source values, receipt and boundary hashes, temporal checks, and removal of the previous regional files.

Original point-API JSON responses and individual receipts are saved under `../../../raw/marala/rainfall/nasa_power/cells/`. A [source manifest](../../../raw/marala/rainfall/nasa_power/source_receipt.json) records the exact requests and retrieval times in UTC and Pakistan time. All cells were freshly downloaded during this rebuild; later reproduction reuses these hash-checked files.

If any required cell is missing on a day, the full-catchment mean remains blank with `missing_grid_precipitation`. The calculation never fills missing data with zero or silently reweights the remaining cells. A valid zero remains a zero.

## Time and source interpretation

Each daily value covers `[00:00 UTC, next 00:00 UTC)`, equivalent to `[05:00 Pakistan time, next 05:00 Pakistan time)`. This is an accumulation period, not a point observation time. A full day's precipitation must not be used for a forecast issued at 06:00 Pakistan time on that same date. Completed periods also need to satisfy publication-latency constraints; source download timestamps do not establish historical issue-time availability.

[NASA's source documentation](https://power.larc.nasa.gov/docs/methodology/data/sources/) explains that recent GEOS-IT estimates can be appended to MERRA2 and later superseded. The saved responses list both sources without providing their exact per-date transition. Preserve the retrieved snapshot when reproducing an experiment. These observed/reanalysis histories are not archived forecasts for the next 15 days.

The catchment remains a source- and geometry-checked research delineation, not an agency-certified or surveyed boundary. Its full geometric coverage does not certify precipitation accuracy in this mountainous basin.

## Reproduce and validate

Install `../../../scripts/requirements.txt`. From the model's `scripts/` directory:

```powershell
python collect_marala_rainfall.py --start 2016-03-01 --end 2026-10-22
python test_marala_rainfall.py
```

The tests cover conservation of uniform precipitation, boundary cells with centers outside the catchment, unequal area weights, and missing-cell handling. The collector checks complete spatial coverage and source units, requested coordinates, day boundaries, date range and checksums before publishing the daily series.

Sources: [NASA POWER daily API](https://power.larc.nasa.gov/docs/services/api/temporal/daily/), [meteorological grid and spatial averages](https://power.larc.nasa.gov/docs/methodology/meteorology/), and [precipitation methodology](https://power.larc.nasa.gov/docs/methodology/meteorology/precipitation/). Retrieved 2026-10-23.

## Training hold from source-consistency audit

The [feature coverage audit](../metadata/marala_feature_coverage_audit.json), checked on 2026-10-23, establishes complete date coverage for WAPDA 2016-03-01 through 2024-12-19 but does **not** clear the rainfall values for training. At grid center 32.5 N, 74.375 E, the saved long-range response gives 851.28 mm on 2024-03-02, whereas independent daily and hourly-sum checks both give 35.47 mm. Another wet-date sample is 227.28 versus 9.47 mm. Repeating the same long-range request reproduces the saved values, so request-period-dependent source inconsistency must be resolved. Keep originals and audit snapshots; do not infer a universal correction factor from these samples. The previous hash/arithmetic validation did not establish meteorological accuracy.
