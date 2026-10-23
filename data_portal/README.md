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
