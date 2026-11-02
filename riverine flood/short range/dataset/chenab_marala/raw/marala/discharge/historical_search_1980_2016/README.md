# Search for observed Marala discharge, 1980-2016

Checked 30 October 2026. Target: observed daily **upstream/inflow** discharge at Marala, Chenab, for the 10-day forecasting project.

**Result: historical records are documented, but a new public daily CSV/Excel series for 1980-2015 or January-February 2016 was not obtained.** Five public PDFs were downloaded as evidence. They do not add a validated daily target series to the project. No observations were filled, inferred from plots, corrected or merged.

## Strongest acquisition leads

| Period reported | Evidence | What was actually obtained | Follow-up custodian |
|---|---|---|---|
| April 1993-September 2014; 1994-2014 described as complete for inflows | [IRSA WCAP technical report](https://irrigation.sindh.gov.pk/files/books/Final-Report-Volume-I-WCAP.pdf), section 2.8.1, printed pp. 2-71 to 2-72 | Availability matrices covering Marala; no daily-value export or embedded database | IRSA, specifically its WCAP MIS/GIS historical discharge database |
| 1980-2007 | [NEPRA Lucky Hydropower filing](https://nepra.org.pk/tariff/Tariff/Petitions/2011/Tariff%20Petition%20of%20Olympus%20Energy%2020MW%20Lucky%20Hydropower%20Project.pdf), printed PB-3, PDF page 36 | Statement that daily downstream flows were supplied by Marala Barrage Division; no daily time-series table found | Executive Engineer, Marala Barrage Division, Punjab Irrigation Department |
| 2003-2014 | [IHE repository page 14](https://ihedelftrepository.contentdm.oclc.org/digital/api/collection/masters2/id/84848/download), section 3.2.6 | A one-page thesis excerpt identifies Punjab Irrigation as the discharge provider for Marala and Qadirabad; it references a daily hydrograph, not a downloadable daily data file | Punjab Irrigation Department; original thesis author if the agency permits redistribution |
| Study analysis period 1998-2012 | [Dahri et al. (2016)](https://pure.iiasa.ac.at/id/eprint/11829/1/An%20appraisal%20of%20precipitation%20distribution%20in%20the%20high-altitude%20catchments%20of%20the%20Indus%20basin.pdf), section 3.3, printed p. 293 / PDF page 5 | Paper lists Marala among gauges sourced from WAPDA; no Marala daily rows or embedded data file | WAPDA; original research authors for source/access clarification |
| 2005-2018 (secondary lead) | [Droppers thesis](https://edepot.wur.nl/569432), search-indexed Table C.3 | Indexed table lists Marala as daily, but figure C.4 describes some related series as monthly. PDF download failed certificate verification; do not count this as a verified daily dataset | WAPDA / corresponding researchers; clarify actual native cadence |

The IRSA report describes **daily means**, separately for upstream and downstream, in cusecs. A visual inspection of Table 2-44 confirms Marala is marked available across its displayed years. The report establishes historical custody, not a current public download or a guarantee about every individual observation. The saved `irsa_daily_availability_page_2_71.png` shows the matrix.

The NEPRA lead is specifically **downstream release**, whereas the existing model target is inflow. It cannot be appended directly as inflow. The filing calls 1980-2007 a 27-year record; exact endpoints and completeness need confirmation from delivered data.

## Older numeric data found at coarser cadence

The downloaded [World Bank/WAPDA drainage-sector document](https://documents1.worldbank.org/curated/en/454701468775827683/pdf/multi-page.pdf) contains upstream and downstream Marala flow tables for **1977-1991**, on PDF pages 137-138. They are explicitly **10-daily discharge in thousands of cusecs**. These tables are useful historical context, but each entry is a ten-day reporting period, not an observed daily value. Periods labeled Apr 1, Apr 2 and Apr 3 must not be mistaken for April 1st, 2nd and 3rd daily readings. No daily values were manufactured from these tables.

Existing PMD historical flood peaks are also retained in the project's separate peak catalog. Peak dates/maxima do not supply complete flood hydrographs or non-flood days.

## What is already available in 2016

`processed/marala/discharge/marala_wapda_daily_inflow.csv`, relative to the `chenab_marala` folder, already has **306 observed Marala dates from 2016-03-01 through 2016-12-31**. The requested 1980-2016 calendar contains 13,515 dates, so 13,209 dates in that interval remain without a verified daily inflow series in the current collection, principally 1980-2015 and January-February 2016. The raw workbook and its extract were not altered.

## Search scope and limitations

- Public searches covered WAPDA/FFD/IRSA/Punjab sources, research repositories, Excel/CSV keywords, and repository/data-archive terms. References to monthly flows, ten-day aggregates, downstream flows, model simulations and event maxima were distinguished from daily inflow records.
- A fresh WAPDA media search for `graph` returned the known `GRAPH-DG-16-for-MAIL-2.xls`, whose local verified Marala daily coverage begins in March 2016, plus an unrelated personnel PDF. No older historical workbook was exposed by this query.
- The public GitHub repository search `Marala discharge` returned zero repositories. This narrow query does not establish that no repository exists under other names.
- A Wayback CDX query for pre-2017 `wapda.gov.pk/*graph*.xls` returned no entries. This specific filename-pattern query does not rule out other archived paths, subdomains or formats.
- The GRDC portal returned HTTP 403 in the browsing tool. No Marala station series was verified there. Access controls were not bypassed.
- The WUR thesis download failed TLS certificate verification. The World Bank PDF was obtained via a normal verified-TLS requests download; its exact bytes and SHA-256 are now recorded in the main download receipts. No insecure certificate setting was used.

`api_search_checks.json`, `wapda_graph_media.json`, `github_repositories.json` and `wayback_old_graphs.json` preserve the direct API checks. `download_receipts.json` records five saved PDFs and the unsuccessful WUR download, with URLs, checksums, page counts and embedded-file checks. The IHE file is explicitly named as a single-page source excerpt; it is not a complete thesis.

## Concrete next step

Request the **original machine-readable daily upstream and downstream series separately** from IRSA, WAPDA and the Marala Barrage Division. Prioritize IRSA's documented 1993-2014 mean-inflow database, then the earlier records held by Punjab Irrigation. Ask specifically for the missing bridge from October 2014 through February 2016 as well. Confirm units, timestamps/daily averaging bounds, original observation flags, any interpolation already performed by the provider, and release terms before ingestion.

A ready-to-send draft is in `historical_records_request_draft.md`. It has **not been sent**. No agency or researcher was contacted during this search.
