# Marala upstream catchment

Use [marala_upstream_catchment.geojson](marala_upstream_catchment.geojson) as the project's **source- and geometry-checked research catchment** for Marala. It represents upstream topographic drainage to the published Marala inflow station location, including the contributing cross-border headwaters. It is not a WAPDA/PMD-issued polygon or a field-surveyed boundary. The checks support its use for initial basin feature extraction while retaining these limits.

| Property | Value |
|---|---|
| Station / river | Marala / Chenab |
| Published station coordinate | 32.67 N, 74.46 E |
| WGS84 geodesic catchment area | 28,780.646 km2 |
| Geographic bounds | 74.05041-77.80625 E; 32.08875-34.21208 N |
| Coordinate reference | WGS84 longitude, latitude; GeoJSON CRS84 |
| Delineation source | Global Watersheds, high-precision mode, MERIT-Hydro/MERIT-Basins |
| Nominal source raster resolution | 3 arc-seconds, about 90 m at the equator |
| Geometry changes | None; raw polygon retained without repair or simplification |
| Verification date | 2026-10-23 |

The [review map](marala_catchment_review.png) shows the boundary, returned upstream river network, published station coordinate and downloaded rainfall grid. The [station point](marala_outlet.geojson) and [river network](marala_upstream_rivers.geojson) are separate layers. The station point is the rounded published coordinate, not a surveyed pour point or a claim about the service's exact snapped outlet.

## Verification evidence

The [verification report](marala_catchment_verification.json) records nine passing checks and source checksums. They cover valid polygon geometry; documented outlet coordinates; outlet proximity and inclusion; area consistency; nearby-outlet sensitivity; high-/low-precision agreement; and exclusion of the downstream Khanki station.

1. **Station identity and location:** [JICA's report](https://openjicareport.jica.go.jp/pdf/12395935.pdf), PDF page 36 (printed page 2-14), lists Marala on the Chenab at 32.67 N, 74.46 E. The station table identifies PMD as its source. The original PDF is saved under `raw/marala/catchment/references/`.
2. **Published upstream area:** The [PMD journal paper](https://www.pmd.gov.pk/rnd/rndweb/rnd_new/journal/vol13_issue26_files/5_Flood_Forecasting_of_an_Ungauged_Trans-boundary_Chenab_River_Basin_Using_Distributed_Hydrological_Model_Integrated_Flood_Analysis_System_%28IFAS%29.pdf), PDF page 4, reports 29,192 km2 upstream of Marala. The downloaded boundary is 1.41% smaller. Published catchment areas vary with delineation and outlet definitions; this comparison establishes consistency, not identical boundaries or field accuracy.
3. **Outlet geometry:** The rounded station point is inside the polygon, about 60 m from its boundary. The returned vector river network is about 558 m away and intersects the +/-0.005-degree rounding box implied by a two-decimal coordinate. The API does not expose its exact snapped pour point; the nearest boundary coordinate in the report is not labeled as one.
4. **Sensitivity:** A high-precision request at 32.671 N, 74.461 E produces an identical polygon. The low-precision result is 28,868.039 km2 and has 99.57% intersection-over-union with the selected high-precision result. These checks use the same underlying hydrography and do not constitute an independent field survey.
5. **Downstream exclusion:** Khanki at 32.41 N, 73.97 E, from the same JICA station table, lies outside the polygon. Its data is not used as a Marala model input here.

The [Global Watersheds documentation](https://mghydro.com/watersheds/help.html) describes high-precision delineation, river snapping and its limitations. The service documents MERIT-Hydro/MERIT-Basins as its inputs but does not expose exact live software/data versions in the returned GeoJSON. Original responses, requests and checksums are preserved under `raw/marala/catchment/global_watersheds/`.

## Rainfall coverage

The [coverage report](marala_rainfall_grid_coverage.json) checks the actual native MERRA2 cell footprints, not just whether their center points fall inside the basin. [NASA POWER documents](https://power.larc.nasa.gov/docs/methodology/meteorology/) a 0.5-degree latitude by 0.625-degree longitude meteorological grid.

The rainfall dataset was rebuilt from fresh catchment-selected downloads. All **21 intersecting cells** now cover **100%** of the saved catchment, with **zero uncovered area**. The [footprints](marala_rainfall_grid_footprints.geojson) contain intersection areas; the [uncovered geometry](marala_rainfall_grid_uncovered.geojson) is an empty FeatureCollection. The [daily catchment precipitation](../rainfall/marala_catchment_daily_precipitation.csv) uses equal-area intersection weights and leaves a day blank if any required source-cell value is missing. See the [rainfall preparation notes](../rainfall/README.md) for the reproducible calculation and source snapshots.

## Attribution, terms and reproducibility

Cite Heberger, Matthew (2022), *Global Watersheds*, https://mghydro.com/watersheds/, together with Yamazaki et al. (2019), *MERIT Hydro*, https://doi.org/10.1029/2019WR024873, and Lin et al. (2019), *Global reconstruction of naturalized river flows at 2.94 million reaches*, https://doi.org/10.1029/2019WR025287.

The service's [derived-data page](https://mghydro.com/watersheds/data/) states CC BY-NC-SA 4.0 for its MERIT-derived data. The [MERIT-Hydro project](https://global-hydrodynamics.github.io/MERIT_Hydro/) separately documents a dual-license scheme. Both pages are saved as source evidence; retain the service's derived-data attribution/terms with this research boundary rather than treating it as unrestricted data.

Install `../../../scripts/requirements.txt`, then run `python collect_marala_catchment.py` from the model's `scripts/` directory. Saved responses are reused and checked against their hashes. New Global Watersheds requests run sequentially with five-second spacing as requested by the provider. A failed verification stops processing rather than repairing or substituting a polygon automatically.

The boundary models topographic drainage. It does not encode changing reservoir operations, canal diversions or groundwater transfers, and its source and consistency checks do not make it an agency-certified boundary.
