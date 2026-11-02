# Desktop discharge folder: usefulness assessment

Inspected 30 October 2026, read-only: `C:\Users\PC\Desktop\discharge`. There are five historical daily discharge workbooks and one questionnaire workbook. Original files were not moved, edited, converted or merged into Marala.

## Finding

**Potentially valuable for separate Upper Indus forecasting studies, but not usable to fill or directly train the current Marala daily-discharge model.** The gauges belong to the Upper Indus system rather than the Chenab at Marala. Their coverage ends in 2007 or 2008; there are **zero overlapping daily dates** with the project's 2016-2026 Marala target. A paired nearby-gauge regression cannot be fitted or validated from these records against that target.

An independent [Upper Indus research paper](https://doi.org/10.3390/su12041283) identifies Hunza/Dainyor, Shigar/Shigar, Shyok/Yugo and Indus/Shatial as Upper Indus gauges. This supports station identification, not certification that the Desktop copies are original provider files or unchanged observations.

## What the files contain

Counts were recomputed from the date/value sheets, not inferred from filenames. “Numeric days” means finite numeric entries, not confirmed original observations or a training-quality clearance.

| File / station | Daily calendar | Numeric days | Missing discharge days | Entire missing years |
|---|---|---:|---:|---|
| Hunza1966_2008.xls — Hunza, Dainyor | 1966-01-01 to 2008-12-31 | 14,611 | 1,095 | 2005-2007 |
| Indus River at Partab br.-Bunji 1962-2007.xls | 1962-01-01 to 2007-12-31 | 16,071 | 730 | 1997-1998 |
| Indus River at Shatial 1998-2007.xls | 1998-01-01 to 2007-12-31 | 3,652 | 0 | None |
| Shigar River at Shigar_1985-2001.xls | 1985-01-01 to 2001-12-31 | 5,478 | 731 | 1999-2000 |
| Shyok River at Yogu_1974-2007.xls | 1974-01-01 to 2007-12-31 | 12,053 | 365 | 2005 |

The five files contain 51,865 numeric station-day entries. Daily calendars are ordered and complete as calendars, with no duplicate dates, invalid timestamps, negative numeric discharge or numeric zero codes found in the selected daily sheets. Missing discharge is represented by blank cells. No partial missing years were found: the missing values occur in the whole years listed above. These structural checks do not prove flow accuracy, measurement basis, or operational availability.

`DOC-20260826-WA0011.xlsx` contains a `Clarification 01` sheet with 13 rows and five columns. It is a climate/disaster UAV monitoring questionnaire with questions and narrative responses, **not a discharge time series**. It could inform project requirements, but it provides no forecasting targets.

## Issues to resolve before using the discharge values

1. **Internal sheet disagreements.** The original monthly-style tables and rearranged daily tables disagree on some corresponding dates. Screening flagged 189 Hunza dates, 33 Shigar dates, and 537 Shyok dates beyond the comparison tolerance. The screen uses an absolute tolerance of 0.1 or a relative tolerance of 0.1%, and the standard cusec conversion when a raw block explicitly says cusecs. For raw tables without explicit units, direct comparisons assume the same numeric units; they are source-consistency findings, not certified corrections.

   Examples: Hunza 1999-09-01 is 822.299 in `data obtained` versus 596.3 in `rearranged data`. Shigar 1998-06-20 is 247.8 in the m3/s monthly table versus 151.58 in `rearranged`. Shyok 2003-08-01 is 1,944 in the m3/s monthly table versus 1,699 in `Rearranged`. Shyok 2003-07-02 has 961.3 in the monthly table versus 986.7 in the rearranged sheet; 986.7 appears on the preceding raw day. This suggests a possible alignment problem in at least part of the series, but the whole sheet must not be shifted or corrected without review. Revisions, interpolation or rearrangement errors remain possible explanations.

2. **Some later values have no matching monthly table in the same workbook.** The parser finds Hunza monthly-table years through 1999, Partab/Bunji through 2000, and Shyok through 2003, while their rearranged sheets contain additional numeric years. Those later entries may have been supplied separately, but their provenance cannot be established from the included monthly tables. Partab's 13,515 dates that can be compared match at the screening tolerance. Shatial has only one populated daily-data sheet, so internal agreement cannot be independently checked.

3. **Mixed units.** Shigar and Shyok original tables change between cusecs and m3/s across year blocks. Shigar has an explicitly labeled cumecs conversion sheet, and Hunza's rearranged header explicitly says m3/s. Partab/Bunji and Shatial daily headers say only `Discharge`; their units need external confirmation. Do not apply a single blanket conversion to all sheets or count both original and converted sheets as independent observations.

4. **Provenance and observation definition.** Shigar and Shyok monthly tables contain `SWHP, WAPDA` source labels. Exact original delivery details, download URLs, QC flags, reuse terms, gauge changes, reading time, and daily-mean versus point-reading definitions are not established by this inspection. A local filename and a full numeric column do not establish these facts. Source hashes are recorded in the JSON audit so future changes can be detected.

## Practical use

- **Current Marala gap filling:** unsuitable with the supplied records, because these are different river-system gauges and have no daily time overlap with Marala. Do not append their values to Marala or calibrate against isolated historical Marala event maxima.
- **Separate Indus/tributary models:** useful candidates once units, source inconsistencies and missing years are reviewed. Shatial is the clearest structural starting point: ten complete years with no missing numeric values. Partab/Bunji offers a longer record but lacks 1997-1998 and requires metadata confirmation. Hunza, Shigar and Shyok warrant reconciliation before treating rearranged values as ground truth.
- **Later multi-basin training or pretraining:** possible research use after QC, with each gauge kept separate and with weather, snow and catchment features for its own contributing basin. The existing Marala catchment weather series should not be assigned to these stations. Transfer benefit for Marala would need evaluation on observed Marala test periods; these files alone do not demonstrate it.

Machine-readable detail: `desktop_discharge_audit.json` includes hashes, sheet layouts, coverage, sample mismatches and source labels; `desktop_discharge_coverage_by_year.csv` includes yearly numeric counts. `inspect_desktop_discharge.py` reproduces the read-only audit with xlrd and openpyxl. No new model was trained and no source file was modified.
