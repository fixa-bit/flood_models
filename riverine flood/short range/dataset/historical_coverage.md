# Pakistan discharge availability check

Checked 2026-10-23. This is an access and structural coverage check, not a completed hydrological quality audit.

## Directly inspected WAPDA records

The [WAPDA river-flow page](https://wapda.gov.pk/river-flow/) links to this publicly downloadable [Excel workbook](https://wapda.gov.pk/wp-content/uploads/2024/12/GRAPH-DG-16-for-MAIL-2.xls). Its `GHRAPH` sheet contains the following numeric daily rows:

| Variable | First date | Last date | Unique numeric dates | Internal missing dates |
|---|---|---|---|---|
| Tarbela inflow and outflow, each | 2016-03-01 | 2024-12-19 | 3,216 | 0 |
| Nowshera inflow | 2016-03-01 | 2024-12-19 | 3,216 | 0 |
| Mangla inflow and outflow, each | 2016-03-01 | 2024-12-19 | 3,216 | 0 |
| Marala inflow | 2016-03-01 | 2024-12-19 | 3,216 | 0 |

The sheet states discharge in thousands of cusecs. There are 102 trailing date rows without these numeric observations; the date column's 2025 endpoint is therefore not actual observation coverage. A heading says `PERIOD 2023` despite the longer Excel-date span. Nowshera contains two zero values and Marala one: investigate these as possible missing/error codes before using them. No hourly observations or Khanki/Jassar/Shahdara time-series columns were established in this workbook. Numeric completeness does not prove measurement accuracy or flood-event hydrograph completeness.

The [WAPDA water-situation page](https://wapda.gov.pk/water-situation/) also links a [19 December 2024 workbook](https://wapda.gov.pk/wp-content/uploads/2024/12/Daily-DataPress-Release-19-12-2024.xls). Its `Press` sheet explicitly distinguishes Marala's 0600-hour reading from 24-hour means at Tarbela, Nowshera and Mangla. Confirm historical definitions rather than assuming every daily series is a daily mean. Its comparative averages are not additional historical observations.

## Hourly collection versus access

WAPDA's [2022-23 annual report](https://wapda.gov.pk/wp-content/uploads/2025/12/Annual-Report-2022-23_compressed-latest.pdf) describes hourly discharge/rainfall collection and transmission and annual hydrological publications. This establishes institutional collection, not publicly downloadable hourly histories for every named station. Station IDs, years, native cadence, quality flags, access terms and a sample extract still need confirmation from WAPDA Surface Water Hydrology/Hydrology & Water Management and the relevant provincial irrigation department.

## FFD and flood-event evidence

- The [FFD archive](https://ffd.pmd.gov.pk/bulletins/archive) lists 267 bulletins/advisories at inspection. The oldest bulletin listed on [page 9](https://ffd.pmd.gov.pk/bulletins/archive?page=9) is 15 June 2024; [page 5](https://ffd.pmd.gov.pk/bulletins/archive?page=5) shows the transition between the 2024 and 2025 seasons. The latest listed archive bulletin is 15 October 2025. These are catalog observations, not verified continuous station series. Other live/publication pages also contain 2026 material.
- An [NDMA report dated 3 September 2025](https://www.ndma.gov.pk/storage/sitreps/September2025/PWP8IuKr86mspMHHFeIi.pdf) includes a timestamped FFD discharge annex. This confirms historical report availability, not multi-year hourly access.
- [NDMA's 2014 flood publication](https://www.ndma.gov.pk/storage/publications/July2024/x8gir6gBtqDBjP7DTfMk.pdf) documents flood peaks at Marala and Khanki. Peak values alone do not provide training hydrographs.
- An [official Ravi warning dated 26 August 2025](https://www.ndma.gov.pk/storage/advisories/August2025/cFV0MPpU1L7kzVd5fu8v.pdf) records high flood at Jassar and warns for Shahdara/Balloki. This event is later than the inspected WAPDA workbook. A full event time series still needs acquisition.

No complete overlapping historical hourly series was verified for Marala-Khanki or Jassar-Shahdara. Do not describe either routing pair as ready for hourly training.

### Subsequent Marala collection

The Marala folder now contains FFD's original 2024 and 2025 bulletin PDFs and 2026 bulletin HTML pages. The extracted 06:00 Pakistan time readings comprise 122 bulletins in 2024 (120 unique printed dates, 16 June to 15 October), 119 in 2025 (117 unique printed dates, 15 June to 15 October), and 122 consecutive dates in 2026 (16 June to 15 October). Within those printed-date spans, 2024 lacks 2 September and 3 October; 2025 lacks 30 June, 6 August, 1-2 September, 4 October, and 12 October. Some archive-listed dates disagree with the PDF dates; both are retained and flagged. These seasonal records do not provide a continuous series from the WAPDA workbook's 19 December 2024 endpoint. A separate [PMD paper](https://www.pmd.gov.pk/rnd/rndweb/rnd_new/journal/vol13_issue26_files/5_Flood_Forecasting_of_an_Ungauged_Trans-boundary_Chenab_River_Basin_Using_Distributed_Hydrological_Model_Integrated_Flood_Analysis_System_%28IFAS%29.pdf) contributes 30 selected historical Marala flood peaks (1970-2016), which are event maxima rather than daily training rows. The [combined catalog](chenab_marala/processed/marala/discharge/marala_discharge_all_sources.csv) preserves dates, confirmed times, and sources; see the [source notes](chenab_marala/raw/marala/discharge/README.md) and collection reports for details.

## Selection decision

The current pilot choices are **Marala (Chenab)** and **Jassar (Ravi)** as separate same-station forecasts. The inspected WAPDA workbook establishes a daily Marala history but not a comparable complete Jassar history; Jassar training remains contingent on acquiring one. Nowshera appears in the WAPDA workbook, but is not a selected pilot station.

The selected pilot models forecast future discharge at **Marala** and **Jassar** from each station's own earlier discharge readings. Marala has the verified daily history above. A complete historical Jassar series still needs to be obtained. Downstream routing to Khanki or Shahdara can be considered as a separate future task.

Begin with a daily one-step-ahead research baseline if using the verified workbook. A 6- or 12-hour model needs actual subdaily observations. Request 2010-2025 records where available, especially complete rising/peak/recession hydrographs across multiple independent floods, plus non-flood periods. Ask for daily and original hourly/3-hourly/6-hourly data, timestamps/timezone, inflow/outflow definitions, station changes, quality flags and reuse terms. Determine usable overlap and event counts from delivered records before finalizing stations or horizons. No agency was contacted during this check.

## Daily-series preparation and recent-source search

On 2026-10-23 the [WAPDA baseline](chenab_marala/processed/marala/discharge/marala_daily_inflow_clean.csv) was prepared with 3,209 eligible daily values and seven withheld dates, preserving the source values and unknown times. The review confirmed 116 exact matches and six discrepancies across the 122 overlapping 2024 FFD bulletins. IRSA yielded eight daily-mean reports for 16-23 October 2026, not a comparable replacement for 06:00 readings. Six WAPDA page/API checks still exposed the 2024 historical/daily workbooks; 12 sampled older IRSA PDF URLs returned 404. Complete daily 2025-2026 coverage is still unverified. See the [preparation notes](chenab_marala/processed/marala/discharge/README.md) and [source-check receipts](chenab_marala/processed/marala/discharge/marala_recent_source_search_report.json).
