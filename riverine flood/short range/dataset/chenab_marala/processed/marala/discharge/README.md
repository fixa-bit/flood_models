# Marala inflow preparation

Use [marala_daily_inflow_clean.csv](marala_daily_inflow_clean.csv) for the initial **date-level daily Marala inflow** research baseline. It contains one row for each day from 2016-03-01 to 2024-12-19: 3,216 dates. The source is WAPDA throughout. This file retains the full daily calendar, including seven withheld values; 3,209 dates currently pass the implemented source-consistency checks. This eligibility does not establish hydrological certification or operational data availability.

`source_inflow_cusecs` retains every original value. `inflow_cusecs` and `inflow_m3_s` are blank when `eligible_daily_training=0`. No values were imputed or averaged between sources. The original files and [all-source catalog](marala_discharge_all_sources.csv) remain available for review.

## Quality decisions

The [quality review](marala_inflow_quality_review.csv) documents seven unresolved dates with source links and excerpts. Direct comparison with the workbook confirms the zero on 2021-01-23 is a numeric zero, not an empty cell. The workbook alone cannot establish whether it is real or an error. All 122 overlapping 2024 FFD bulletin values were compared with WAPDA using exact decimal arithmetic: 116 match and six differ. The six differences also match their original PDFs, so they were not extraction mistakes.

| Date | WAPDA inflow (cusecs) | FFD inflow (cusecs) | Decision |
|---|---:|---:|---|
| 2021-01-23 | 0 | unavailable | Withhold pending source confirmation |
| 2024-07-16 | 48,100 | 48,200 | Preserve both; withhold |
| 2024-08-02 | 99,600 | 99,400 | Preserve both; withhold |
| 2024-09-19 | 24,600 | 52,000 | FFD archive lists 2 September; withhold |
| 2024-10-02 | 21,100 | 21,200 | Preserve both; withhold |
| 2024-10-13 | 14,700 | 21,500 | FFD archive lists 3 October; withhold |
| 2024-10-15 | 10,700 | 37,500 | Possible FFD date/template issue; withhold |

The PDF-date conflicts do not establish that WAPDA is wrong. Withholding is a conservative research policy until these differences are resolved; it is not a correction to either source. See [marala_daily_inflow_quality_report.json](marala_daily_inflow_quality_report.json) for counts and coverage.

## Times and variables

`time_pakistan` and `datetime_pakistan` remain blank for 3,215 WAPDA dates. Only 2024-12-19 has companion-report confirmation of 06:00 PKT. A matching FFD value does not establish the time of an individual WAPDA row. Daily training may use the date label, but this dataset does not support claiming a confirmed 06:00 historical forecast issue time or subdaily validation. Discharge conversion uses 1 cusec = 0.028316846592 m3/s; the modeling column is rounded to six decimal places.

The newly collected [IRSA table](marala_irsa_daily_mean_discharge.csv) contains eight daily means for 2026-10-16 through 2026-10-23. Their averaging-period bounds are not stated, so time is blank. These means have a distinct record kind in the all-source catalog and are not appended to the WAPDA baseline or used to fill missing FFD 06:00 readings. PMD historical event peaks are also kept separate.

## Recent coverage search

The [2025-2026 calendar](marala_2025_2026_coverage.csv) has one row per day through **2026-10-23**. In 2025 it identifies 115 dates with unique, date-consistent FFD readings, two duplicate/date-conflict dates, and 248 missing dates. In 2026 it identifies 122 consecutive FFD readings from 16 June through 15 October and 174 missing point-reading dates through the check date. Eight of the latter have separate IRSA means. Blank values represent missing or unresolved records, not zero discharge. This is coverage of the collected sources, not proof that no other records exist.

WAPDA's [river-flow](https://wapda.gov.pk/river-flow/) and [water-situation](https://wapda.gov.pk/water-situation/) pages still link the December 2024 files. Public search and media API checks did not establish a newer complete archive. [IRSA's daily-data page](http://pakirsa.gov.pk/DailyData.aspx) linked eight recent PDFs; 12 distributed historical PDF URL checks returned 404. This limited sample does not prove every other older PDF is unavailable. The [search report](marala_recent_source_search_report.json) records the checked URLs, responses, snapshot paths and checksums. **Complete daily coverage for 2025-2026 has not been verified.** A [request draft](marala_recent_records_request.md) is prepared for the owning agencies; it has not been sent.

## Reproduce

Install the dependencies from `../../../scripts/requirements.txt`, then run the following from the model's `scripts/` directory:

```powershell
python extract_wapda_marala.py
python collect_ffd_marala_archive.py 2024
python collect_ffd_marala_archive.py 2025
python collect_ffd_marala_2026.py
python collect_pmd_marala_peaks.py
python check_marala_recent_sources.py --as-of 2026-10-23
python build_marala_discharge_catalog.py
python prepare_marala_daily_inflow.py --as-of 2026-10-23
python validate_marala_discharge.py
```

Collectors access the live sources; the saved files and reports record this run's evidence. Before training a 15-day model, require consecutive calendar dates and eligible readings throughout each input window and every one of its 15 target days. Removing withheld rows and treating the remaining rows as consecutive would create false time intervals. Define chronological training, validation and test periods before fitting models or preprocessing.
