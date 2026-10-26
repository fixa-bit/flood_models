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

## Refresh after adding project data

```powershell
python build_dashboard.py
```

Then use **Reload snapshot** in the local portal. No upload or deployment is needed. The displayed check timestamp is always the snapshot build time, not an assertion of a live agency feed.

The supported scientific inputs currently come from the existing Marala collectors. Newly added files appear in model collection counts, but a new station's series and verification schema need an explicit adapter in `build_dashboard.py` before charts can be shown for it. The portal never invents data for an empty case and does not execute collector scripts or alter source/QC files.

## Views

- Overview: date/year filters, eligible and withheld Marala inflow, separate FFD readings, catchment precipitation, monthly usability, distributions and exploratory annual-maximum windows.
- Summary: stacked inflow, outflow, precipitation, IRSA mean-flow and PMD peak panels. **Feature graph year** selects a full January–December calendar year for all six aligned panels (default: 2024). Each variable has its own y-axis. Choose a full-year chart fitted to the screen or a wider chart that scrolls horizontally. Years and variables without saved readings are explicitly labeled; no data is filled in. Changing the feature year clears the previous selected/locked date and leaves the availability chart and Overview filters untouched.

Summary hover cards use the selected point's exact calendar date, with plain source labels and a short explanation. Matching inflow records say “Both sources report the same flow.” Withheld readings say “Needs checking — excluded from training,” and date-conflicted FFD bulletins identify the printed and website dates. Nearby dates are never combined into one observation box. Hover or tap a point to inspect it; use scrollable mode to distinguish individual days on small screens.

Moving across a plot or tapping a date places one continuous vertical crosshair across the variable panels. Circles mark the actual saved readings at that date, with source names and values beside them. Flow curves also show small circles at individual readings. Matching sources share a point; different or flagged readings stay separate and retain their warnings. Panels without a reading have no point. The selected date stays visible when the pointer leaves, when scrolling and when switching display modes. **Clear date line** removes the crosshair and selected points.

**Double-click a plot to lock its selected date**, or use **Lock date line** above the graphs. While locked, mouse movement cannot change the date or reading markers; hovering over another variable shows that variable's readings for the locked date. The lock survives scrolling and switching display modes. Click **Unlock date line** or press **Esc** to resume following the pointer. **Clear date line** removes both the selection and its lock.

The Summary has two explicit display modes. **Full [selected year] — one screen** fits January–December across the chart width. **Full [selected year] — scrollable** draws the entire year on one wide chart; scroll horizontally using the top control, the small scrollbar under any variable, Earlier/Later buttons or a trackpad/swipe. The duplicate native scrollbar beneath the full stack is hidden. The x-axis always spans all 365 or 366 days in both modes; scrolling changes only which part of the wide canvas is visible. The independent y-axis scales and variable names stay pinned at the left. There are no 30/90-day windows. It opens in scrollable mode. Both modes retain source flags and exact-date hover cards.

In scrollable mode, a small horizontal scrollbar also sits below **each variable panel**. All six bars, the top slider and the full chart share the same scroll position. Moving any bar moves every variable together while preserving the selected date and reading markers. The small bars are hidden in one-screen mode, where the whole year already fits.

The bottom **Data availability across variables** chart covers **all collected years**, from the earliest saved event to the latest saved record (currently 1970-07-02 through 2026-10-23). Its **Availability year** selector independently chooses one full calendar year or **All collected years** (the default). A selected year includes every January–December date, with missing dates shown in grey. The independent scrollbar labeled **Scroll this availability chart independently** sits above it. Changing this selector leaves the feature graphs, their scrolling and any locked date untouched. The duplicate native scrollbar below this chart is hidden. Early PMD entries are selected flood events; regular WAPDA daily inflow starts in March 2016. One variable color per row means at least one saved reading exists, grey means none is saved, and small dots mark readings needing review. A valid zero counts as present. Hover shows dates, sources and known reading times/periods, without measurement values. Unconfirmed times remain unknown. Chart width is bounded for browser rendering; the underlying calendar retains every day and every saved year.
- Sources: all saved provider groups, exact source URLs and local checksum results.
- Integrity & quality: freshly recomputed SHA-256 ledger, measurement uncertainties, seven withheld WAPDA dates, time certainty and recent coverage gaps.
- Catchment: interactive boundary, upstream river network, clipped precipitation cells, weights and boundary checks.
- Data library: downloadable principal series, quality reports, original-source manifests and geospatial evidence. The large source-cell CSV stays in the local workspace and is identified as such.

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
