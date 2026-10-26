# Marala rainfall source investigation, 26 October 2026

**Status: comparison and quality investigation only. None of these rainfall series is approved for model training.** The original POWER cell downloads and the existing processed rainfall table remain unchanged. This folder contains a new, separately labelled NASA POWER candidate plus a ten-day comparison with IMERG and CHIRPS.

## What the NASA POWER check found

All POWER responses below describe `PRECTOTCORR` at the same grid point (32.5 N, 74.375 E), use the `AG` community, label daily output `mm/day`, and request the UTC time standard. The conflicting response is reproducible:

| UTC date | Single-day / shorter request | Saved long request through October 2026 | Sum of 24 hourly values |
|---|---:|---:|---:|
| 15 July 2016 | 42.79 mm | 1,026.96 mm | 42.77 mm |
| 6 August 2016 | 16.03 mm | 384.72 mm | 16.02 mm |
| 2 March 2024 | 35.47 mm | 851.28 mm | 35.47 mm |
| 8 August 2024 | 9.47 mm | 227.28 mm | 9.45 mm |

At this point, one-day, week, month, full-2024, and 2016–2024 requests return the smaller historical values and identify `MERRA2`. The longer request ending 22 October 2026 returns the larger historical values and identifies both `MERRA2` and `GEOSIT`. The test establishes a request-range-dependent inconsistency. It does **not** prove the internal cause of that inconsistency. Small differences of 0.01–0.02 mm between daily and summed hourly values are consistent with rounding of the 24 reported hourly numbers.

The full 2016-03-01 to 2024-12-31 overlap was independently requested again for all 21 catchment cells. Comparing **67,788** cell-days against the preserved original long-range responses gives **34,355 positive readings exactly 24 times the new values**, **5,681 equal positive readings**, **27,752 equal zeroes**, and **no other differences or missing values**. Four single-day, full-catchment checks agree with the freshly requested 2016–2024 series. This pattern affects 18 of the 21 cells on each of the four sampled days; three cells match. **Do not divide all saved basin averages by 24:** some cells were already correct. The separately saved [fresh historical candidate](nasa_power_fresh_historical_basin_candidate.csv) has 3,228 complete daily values but remains on hold pending independent validation across the full period.

Exact query URLs, original bytes, retrieval times and SHA-256 hashes are retained alongside each new response under `raw/marala/rainfall/nasa_power/investigation_2026-10-26/`. [Range-level observations](nasa_power_range_comparison.csv), [fresh single-day cell values](nasa_power_fresh_single_day_cells.csv), [sample cell differences](nasa_power_sample_cell_disagreements.csv), and [machine-readable report](source_comparison_report.json) make the finding auditable. The report verifies that all 21 earlier POWER source files were unchanged.

## Comparison over the same upstream catchment

All numbers are **daily catchment-average precipitation depth (mm)**, weighted by how much of each source grid cell intersects the saved Marala boundary. They are not a sum of grid-cell depths. The source comparison uses UTC date labels. The four fresh POWER means below are separately calculated from 21 new single-day responses, not obtained by dividing the saved mean.

| UTC date and example | Saved POWER | Fresh POWER | IMERG | CHIRPS v3 rnl |
|---|---:|---:|---:|---:|
| 15 July 2016, ordinary wet day | 290.45 | 13.41 | 6.00 | 12.18 |
| 6 August 2016, flood event | 358.39 | 16.84 | 29.40 | 22.85 |
| 2 March 2024, disputed day | 1,223.93 | 60.19 | 13.42 | 39.72 |
| 8 August 2024, disputed day | 70.73 | 3.13 | *withheld* | 3.36 |

The complete [10-day comparison](marala_precipitation_source_comparison.csv) includes additional dry/ordinary days and the 4–6 September 2014 and 5–7 August 2016 flood windows. The 2014 samples have no saved POWER values because the original POWER series starts in March 2016. Different precipitation products can disagree substantially in this mountainous catchment. Agreement with one product does not certify another.

**IMERG:** NASA IMERG half-hourly precipitation rates were read from [NOAA's publicly accessible mirror](https://erddap.aoml.noaa.gov/hdb/erddap/index.html), using the raw numeric DODS response. Each of 48 half-hour rates in `mm/hour` contributes `rate × 0.5 hour` to its UTC day. Gridded values were then area-weighted over the same boundary. Source versions and archive IDs are in the [report](source_comparison_report.json). The 2014 and 2016 downloads are v06 Final; 2 March 2024 is a v06 Early archive; 8 August 2024 is v07 Final. NOAA metadata for v06 marks zero as missing despite NASA's [v06 product specification](https://storm.pps.eosdis.nasa.gov/storm/data/docs/filespec.GPM.V1.3IMERGHH.pdf) using `-9999.9` for missing and allowing zero precipitation. For v07, NOAA marks **zero as both its fill and missing value**. Its zero intervals cannot be distinguished from missing intervals using this mirror, so the 8 August mean is withheld; only a [positive-only lower bound](imerg_daily_catchment_sample.csv) is retained. None of these IMERG samples is a complete historical training series.

**CHIRPS:** [CHIRPS v3 Final `rnl`](https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/readme.txt) GeoTIFFs were downloaded for the same ten dates, clipped using the full catchment, and area-weighted. Its pentad rainfall totals blend satellite and station information; **ERA5 distributes each pentad total among UTC dates**. Station reporting windows within a pentad can differ, so a CHIRPS daily label is not proof of one uniform station observation period. This also means that CHIRPS `rnl` daily timing is not fully independent from ERA5. CHIRPS is useful as a cross-check and candidate product, with timing caveats for a daily flood model. CRU TS supplies monthly precipitation and is therefore unsuitable for verifying these specific daily flood events ([CRU documentation](https://crudata.uea.ac.uk/cru/data/hrg/index.htm)).

## Reproduce

From the model's `scripts/` directory, install `requirements.txt`, then run:

```powershell
python audit_marala_precipitation_sources.py
```

The script verifies receipts and hashes on repeat runs, recomputes the area-weighted comparisons, checks the full 2016–2024 candidate against four separately downloaded single-day basin means, and stops if any original NASA cell file changes. It writes only under this investigation folder and dedicated new raw-source folders. The scientific hold remains in place until a more comprehensive product comparison and forecast-time data availability review are complete.
