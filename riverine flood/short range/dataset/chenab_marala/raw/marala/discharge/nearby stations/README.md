# Nearby Chenab station discharge

Collected 30 October 2026 from the official [Pakistan Meteorological Department Flood Forecasting Division](https://ffd.pmd.gov.pk/bulletin/). This is data collection and extraction only; no correlation, regression fitting, filling, or accuracy analysis has been performed.

| Station folder | Eligible observed days | 2024 | 2025 | 2026 |
|---|---:|---:|---:|---:|
| [Khanki](Khanki/nearby.csv) | 350 | 111 | 117 | 122 |
| [Qadirabad](Qadirabad/nearby.csv) | 350 | 111 | 117 | 122 |
| [Trimmu](Trimmu/nearby.csv) | 350 | 111 | 117 | 122 |

Each station's `nearby.csv` has the requested `date,q_cumecs` schema. Values are observed **inflow at 06:00 Pakistan time**, converted from the provider's thousands of cusecs to m3/s using 28.316846592 m3/s per thousand cusecs. Daily calendars run from 2024-06-16 to 2026-10-15, with 350 accepted values and 502 NaNs per station. They contain the available flood-season records, not year-round observations. The October-March season is represented only by collected October dates; April and May are absent. This limits a later three-season validation.

Each station folder also contains:

- `observations_with_provenance.csv`: all 363 extracted bulletin records, with inflow, outflow, printed and archive dates, flags, URLs and source hashes.
- `selected_daily_provenance.csv`: source records for accepted daily inflows.
- `collection_report.json`: dates, counts, exclusions and units.

Thirteen bulletin records per station have disagreements between printed and archive-listed dates. They are retained in the full observation table but withheld from `nearby.csv`. Missing observations are never interpolated or replaced with modeled values. Inflow and outflow remain separate. A few PDF labels truncate Qadirabad as `Qadiraba`; the collector recognizes that spelling while retaining exact source PDFs.

All **363 source documents were freshly downloaded from official FFD URLs**: 241 archive PDFs for 2024-2025 and 122 HTML bulletins for 2026. Historical URLs were obtained from the existing Marala collection catalogs. Exact documents are saved once in `_sources/2024`, `_sources/2025` and `_sources/2026`, shared by the station folders. Each has a receipt with URL, retrieval time, byte count and SHA-256; `source_manifest.csv` indexes them. `validation_report.json` records successful checksum, date, unit-conversion and provenance checks, including a 24 July 2026 spot comparison against the [published FFD bulletin](https://ffd.pmd.gov.pk/b/cdd9825c-8311-4d28-9fc3-1b377c4c9345).

These are candidate Chenab proxy stations, not validated substitutes for Marala. Station operations, tributary contributions, flow direction, and appropriate lag direction must be assessed during the later analysis. Daily bulletin readings are not daily means or a complete hourly series.

To rebuild, install `requirements.txt` and run `python 'riverine flood/short range/dataset/chenab_marala/raw/marala/discharge/nearby stations/collect_ffd.py'` from the project root. The script reuses this folder's exact saved downloads on reruns. Collection errors and any network fallback are explicit in the reports; the completed collection had no parsing/download failures and required no fallback.
