# Flash-flood dataset: Pakistan 20 km grid

Inputs and labels for the short-range flash-flood model in [`../model`](../model/README.md). Each source sits in its own folder and is combined only at training time. Nothing is filled: missing source values stay missing (NaN).

## Grid

A fixed **20 km × 20 km grid** in EASE-Grid 2.0 (EPSG:6933, equal area), snapped to multiples of 20 km. The project's dataset plan specifies this cell size.

- **Cells:** the 2,306 cells with at least 10 % of their area inside Pakistan.
- **Boundary:** `USDOS/LSIB_SIMPLE/2017`, which includes Azad Jammu & Kashmir and Gilgit-Baltistan. Cell shares inside it are exact polygon intersections.
- **Chenab scoring area:** cells at least 25 % inside the GAUL 2025 districts the Chenab crosses between Marala and Trimmu: Sialkot, Gujrat, Gujranwala, Mandi Bahauddin, Hafizabad, Chiniot and Jhang. There are 67 such cells.

## Contents

| Path | What it is | In git |
|---|---|---|
| `raw/groundsource/` | Original Groundsource release (`groundsource_2026.parquet`, 667 MB) and `source_receipt.json` | receipt only |
| `raw/gee/grid/` | `grid_definition.json`, `cells.csv` (id, row/col, centre, Pakistan and Chenab shares, province), boundary GeoJSONs | yes |
| `raw/gee/static/` | `static_features.npz`: terrain, land cover, built-up share, population density per cell, with receipt | yes |
| `raw/gee/imerg_v07/` | One `.npz` per month: daily rainfall total and wettest 3-hour accumulation per cell, Pakistan local days | receipt only |
| `raw/gee/era5land_daily/` | One `.npz` per month: topsoil moisture, maximum temperature, snowmelt per cell (UTC days) | receipt only |
| `processed/groundsource_pakistan_events.csv` | Every Groundsource event mostly inside Pakistan, with dates, size and the grid cells it overlaps | yes |
| `scripts/` | Collectors (below) | yes |

Large files are ignored by git. Their receipts list checksums, and the scripts regenerate them.

## Sources

| Source | Use | Notes |
|---|---|---|
| [Groundsource](https://zenodo.org/records/18647054) (Google Research, 2026, CC-BY-4.0, DOI 10.5281/zenodo.18647054) | Labels | 2.6 million flood events worldwide, extracted from news by Gemini, 2000–2026-02-03. Each event has a location polygon and start/end dates; there is **no flood-type field**. Google's own checks found roughly 60–75 % of events correct in both place and timing. |
| `NASA/GPM_L3/IMERG_V07` (Final run, half-hourly) | Rainfall | Summed to Pakistan local days (00–24 PKT). Per cell: area-mean total and the largest 3-hour block total in any IMERG pixel. |
| `ECMWF/ERA5_LAND/DAILY_AGGR` | Antecedent state | Soil water 0–7 cm, daily maximum 2 m temperature, snowmelt. |
| `MERIT/DEM/v1_0_3`, `MERIT/Hydro/v1_0_1` | Terrain | Elevation mean, range and spread, slope, share steeper than 15°, largest upstream drainage area in the cell. |
| `JRC/GHSL/P2023A` (BUILT_S, POP; 2020), `MODIS/061/MCD12Q1` (2020) | Exposure, land cover | Built-up share, population density, cropland, barren, snow/ice and forest shares. Population also reflects where floods get reported. |

## Re-run

From `scripts/`, with the module environment `../../../.venv`:

```powershell
$py = '../../../.venv/Scripts/python.exe'
& $py build_grid_static.py                                  # grid, boundaries, static features (~10 min)
& $py extract_daily_gee.py --source imerg                   # 2009-12 to 2026-01, resumes
& $py extract_daily_gee.py --source era5land
& $py extract_groundsource_pakistan.py                      # needs raw/groundsource/groundsource_2026.parquet
```

Earth Engine needs a login and the project set in `gee_common.py`. To recreate the Groundsource original, download it from the Zenodo record and check its MD5 against the receipt.
