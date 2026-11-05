# Flood Data Observatory

A portal for source provenance, data quality and visual exploration of the four flood-model folders. The collected Marala riverine data is populated. Jassar, long-range forecasting, flash flooding, seasonal flooding and urban flooding show explicit collection states while their datasets are empty. The exposure/infrastructure module is separate from these model inputs.

**Local-only personal use. No login, account or authentication is required.** The server binds to this computer's loopback address. Future changes should stay local unless hosting is explicitly requested.

The dark theme uses a cleaned reconstruction of the user's fox-and-lantern reference. The saved image is `dist/assets/fox-doorway-background.png`; [asset notes and generation prompt](background-image-notes.md) record its origin. Dashboard and chart colors are adjusted for the dark background.

## Run locally

No Python dependencies are needed for the portal builder/server. Plotly 4.1.1 is bundled locally, so charts do not depend on a third-party CDN at runtime.

```powershell
cd data_portal
python serve.py
```

Open http://127.0.0.1:8787. You can also double-click `start_portal.cmd`, or run `start_portal.ps1`. The launcher rebuilds the snapshot and recomputes source-file hashes first. Keep the launcher running while using the portal; Ctrl+C stops it. To choose another port, use `python serve.py --port 8788`.

## Automatic refresh after adding project data

When started with `python serve.py` or either launcher, the local server watches
the Marala `raw` and `processed` data folders. After files stop changing for a
few seconds, it rebuilds the portal snapshot. Open tabs check for the new
snapshot about every 12 seconds, reload the data, and redraw the current view;
Overview, Summary, availability, sources, quality, and downloads use the same
updated snapshot. The server terminal reports successful rebuilds or errors.
Keep the server running for automatic refresh. `python serve.py --no-watch`
disables monitoring, and `--watch-interval 10` changes the folder scan interval.

The station selector is registered for Chenab Marala, Khanki, Qadirabad and
Trimmu. Each has a matching `raw/<station>` workspace with `catchment`,
`dewpoint_temperature`, `discharge`, `NDSI_Snow_Cover`,
`potential_evaporation_sum`, `rainfall`, `snow_depth`,
`snow_depth_water_equivalent`, `snowmelt_sum`, `static_attributes`,
`surface_solar_radiation_downwards_sum`, and `temperature/google_earth_engine`
folders. The three nearby-station workspaces start empty; their downloaded
comparison files remain in Marala's existing `discharge/nearby stations`
archive and are not counted as station observations. For those workspaces, CSVs
with a `date` (or `day`, `datetime`, `time`) column and numeric value columns
appear in the station Summary chart and folder coverage table. Files are listed
in Sources, Quality, Catchment or Rainfall views according to the selected tab.
Static and geospatial files are indexed even if they do not form a daily series.
New station directories placed directly under the Chenab `raw` directory are
also registered automatically and get the same empty folder template at build
time. Use a lowercase or underscore folder name for a clear selector label.
On Marala Summary, daily weather and snow features are aligned as individual
panels in the same vertically stacked, shared-date chart as discharge and
rainfall. Each panel has its own scale and follows the same crosshair and
scrolling controls. Static attributes and catchment geometry appear as tables
because they do not have daily time-series values.

Registered weather and snow daily CSVs are re-read on each rebuild. New files
in those existing folders appear as separate series in Overview, Summary,
availability, Sources, and Data library. A new variable or a different CSV
schema still needs an adapter in `build_dashboard.py`; PDFs, spreadsheets and
archives trigger a snapshot rebuild but are not automatically extracted into
daily series. The portal does not fill gaps or change source data.

## Manual refresh

The Summary catchment precipitation panel also supports ERA5-Land, CHIRPS v2
Daily, PERSIANN-CDR and IMERG V07 Final from
`riverine flood/short range/dataset/chenab_marala/raw/marala/rainfall/google_earth_engine`. The existing checked
Marala catchment is reused, with native pixel-area and boundary-fraction weights.
These four series are plotted for visual comparison when the exported CSV matches
the checksum recorded by `quality_report.json`; failed QA checks stay visible as
warnings, and invalid negative daily means remain gaps. These exploratory values
are not marked training-ready. CHIRPS v3 and NASA POWER comparisons remain
separate. Download the extraction
script/instructions from Data library, or run them directly in that folder.
After extraction, rebuild the snapshot using the command below if the watcher
is disabled. Earth Engine login and a project are required for extraction, not
for viewing this local portal.

```powershell
python build_dashboard.py
```

With the watcher enabled, the portal refreshes itself. Otherwise use **Reload
snapshot** after rebuilding. No upload or deployment is needed. The displayed
timestamp is the snapshot build time, not an assertion of a live agency feed.

The supported scientific inputs currently come from the existing Marala collectors. Newly added files appear in model collection counts, but a new station's series and verification schema need an explicit adapter in `build_dashboard.py` before charts can be shown for it. The portal never invents data for an empty case and does not execute collector scripts or alter source/QC files.

## Views

- Overview: date/year filters, eligible and withheld Marala inflow, separate FFD readings, CHIRPS Final catchment precipitation, monthly usability, distributions and exploratory annual-maximum windows.
- Summary: aligned panels for inflow, outflow, rainfall, IRSA mean-flow, PMD peaks and each daily weather/snow feature. The rainfall row compares CHIRPS Final, Google Earth Engine products, and the fresh NASA POWER candidate on one mm/day scale; QA and training holds are identified in the Summary notice and date hover. The inconsistent historical NASA POWER request is omitted. Feature year selects a full January–December calendar year across all panels. Original flow-panel size is retained as added features extend the chart vertically, with horizontal date scrolling unchanged. Missing values remain gaps.
- Rainfall sources: one combined precipitation comparison and separate catchment-rainfall plots for CHIRPS v3 Final RNL, CHIRPS v3 Preliminary SAT, four Google Earth Engine products when the checked export exists, the fresh NASA POWER historical candidate, and original CHIRPS GeoTIFF check samples. QA warnings remain attached to exploratory series; negative daily means are gaps. The inconsistent historical POWER request remains downloadable for audit.

Summary hover cards use the selected point's exact calendar date, with plain source labels and a short explanation. Matching inflow records say “Both sources report the same flow.” Withheld readings say “Needs checking — excluded from training,” and date-conflicted FFD bulletins identify the printed and website dates. Nearby dates are never combined into one observation box. Hover or tap a point to inspect it; use scrollable mode to distinguish individual days on small screens.

Moving across a plot or tapping a date places one continuous vertical crosshair across the variable panels. Circles mark the actual saved readings at that date, with source names and values beside them. Flow curves also show small circles at individual readings. Matching sources share a point; different or flagged readings stay separate and retain their warnings. Panels without a reading have no point. The selected date stays visible when the pointer leaves, when scrolling and when switching display modes. **Clear date line** removes the crosshair and selected points.

**Double-click a plot to lock its selected date**, or use **Lock date line** above the graphs. While locked, mouse movement cannot change the date or reading markers; hovering over another variable shows that variable's readings for the locked date. The lock survives scrolling and switching display modes. Click **Unlock date line** or press **Esc** to resume following the pointer. **Clear date line** removes both the selection and its lock.

The Summary has two explicit display modes. **Full [selected year] — one screen** fits January–December across the chart width. **Full [selected year] — scrollable** draws the entire year on one wide chart; scroll horizontally using the top control, the small scrollbar under any variable, Earlier/Later buttons or a trackpad/swipe. The duplicate native scrollbar beneath the full stack is hidden. The x-axis always spans all 365 or 366 days in both modes; scrolling changes only which part of the wide canvas is visible. The independent y-axis scales and variable names stay pinned at the left. There are no 30/90-day windows. It opens in scrollable mode. Both modes retain source flags and exact-date hover cards.

In scrollable mode, a small horizontal scrollbar also sits below **each variable panel**. All six bars, the top slider and the full chart share the same scroll position. Moving any bar moves every variable together while preserving the selected date and reading markers. The small bars are hidden in one-screen mode, where the whole year already fits.

The bottom **Data availability across variables** chart covers **all collected years**, from the earliest saved event to the latest saved record (currently 1970-07-02 through 2026-10-23). Its **Availability year** selector independently chooses one full calendar year or **All collected years** (the default). A selected year includes every January–December date, with missing dates shown in grey. The independent scrollbar labeled **Scroll this availability chart independently** sits above it. Changing this selector leaves the feature graphs, their scrolling and any locked date untouched. The duplicate native scrollbar below this chart is hidden. Early PMD entries are selected flood events; regular WAPDA daily inflow starts in March 2016. One variable color per row means at least one saved reading exists, grey means none is saved, and small dots mark readings needing review. A valid zero counts as present. Hover shows dates, sources and known reading times/periods, without measurement values. Unconfirmed times remain unknown. Chart width is bounded for browser rendering; the underlying calendar retains every day and every saved year.
- Sources: all saved provider groups, exact source URLs and local checksum results.
- Integrity & quality: freshly recomputed SHA-256 ledger, measurement uncertainties, seven withheld WAPDA dates, time certainty and recent coverage gaps.
- Catchment: interactive boundary, upstream river network, clipped precipitation cells, weights and boundary checks.

- Data library: downloadable principal series, rainfall source samples, source-cell values, quality reports, original-source manifests and geospatial evidence. Raw CHIRPS Zarr chunks and GeoTIFFs remain in the local source folders and appear in the integrity ledger.

**Rainfall source update (28 October 2026):** CHIRPS v3 Final is the preferred historical Marala catchment rainfall candidate, with separate recent Preliminary dates. Overview, Summary and Rainfall sources plot CHIRPS Final and the other retained comparison series. The inconsistent saved NASA POWER request is excluded from value charts and retained in the Data library for audit. Two plotted CHIRPS dates were checked against original CHC GeoTIFFs; see [the CHIRPS collection notes](../riverine%20flood/short%20range/dataset/chenab_marala/processed/marala/rainfall/chirps_v3_primary/README.md).

IRSA daily means and the PMD journal's selected event peaks have separate charts and measurement labels. FFD date conflicts are identified separately. WAPDA historical date labels are not turned into invented observation times. Annual maximum windows are exploratory and are not presented as official flood categories. The catchment is a checked research delineation, not agency-certified.

## Integrity and limitations

The builder discovers checksum claims in source receipts, collection reports and FFD CSVs, deduplicates them by resolved path, hashes each local file, and reports matches, mismatches, missing files or conflicting claims. A checksum match proves consistency with a saved claim, not agency authenticity, measurement accuracy, or that the original live source has not changed. Untracked files are identified in the downloadable data snapshot.

Plots are historical visualizations, not predictions or live flood warnings. Precipitation uses UTC daily intervals; discharge retains each source's own reading definition. The quality and source verification reports are displayed as recorded, with a separate fresh file-integrity check. No claims of new hydrological certification are made by the portal.

## Tests and build

```powershell
python -m unittest discover -s tests -v
node --check dist/assets/app.js
python build_dashboard.py
```

The static output is `dist/`, including the checked snapshot at `dist/data/portal.json` and its build manifest. `.openai/hosting.json` retains the private Site identity. Browser QA checks desktop/mobile layout, case and station changes, year filters, chart rendering, source search, integrity ledger, catchment grid controls and downloads.

Chart software: [Plotly.js](https://plotly.com/javascript/getting-started/), bundled pinned release 4.1.1; its license notice is retained in `dist/assets/plotly.min.js`.

The portal also applies an advisory precipitation screen at >=100 mm/day of catchment mean. It displays the flagged count and extreme values for scientific review without modifying, rejecting or certifying the source dataset. This is not an official flood threshold.
