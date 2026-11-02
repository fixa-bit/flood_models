# Local flood-forecast training readiness assessment

Inspected 30 October 2026. Scope: saved short-range riverine datasets, principally Marala; no new source downloads or model training. Counts below were recomputed directly from CSVs with Python's standard library.

## Verdict

Marala has sufficient dated observations to begin a modest daily discharge research baseline. The collection does not yet establish dependable operational flood-warning skill, particularly for extreme flows or the full 15-day horizon. Jassar contains only placeholder files and cannot be trained.

## Verified data

| Dataset | Saved coverage | Finding |
|---|---|---|
| Clean Marala discharge | 2016-03-01 to 2024-12-19 | 3,216 calendar dates; 3,209 eligible readings, seven withheld |
| Preferred CHIRPS v3 Final RNL rainfall | 1990-01-01 to 2026-09-30 | 13,422 unique dates; no nonfinite precipitation values; covers all 3,216 discharge dates |
| ERA5-Land air temperature | 1980-01-01 to 2024-12-31 | 16,437 unique dates; no nonfinite temperature values; full discharge-date overlap |
| Snow depth, SWE, snowmelt | 1980-01-01 to 2024-12-31 | 16,437 unique dates; no nonfinite values in these columns; full discharge-date overlap |
| Dewpoint and solar radiation | 1980-01-01 to 2024-12-31 | 16,437 unique dates; no nonfinite values in these columns; full discharge-date overlap |

Extra decades of weather do not create extra supervised discharge examples. Temporal completeness also does not establish physical accuracy, spatial representativeness, or availability at forecast issue time.

## Usable windows

Requiring every input and target discharge value to be eligible, with consecutive calendar dates:

| Past observations | Future targets | Candidate windows before splitting |
|---|---|---:|
| 7 days | 1 day | 3,159 |
| 30 days | 1 day | 3,050 |
| 30 days | 15 days | 2,994 |
| 60 days | 15 days | 2,910 |
| 90 days | 15 days | 2,850 |

These are overlapping samples, not independent flood events. Counts are not an issue-time availability clearance and will fall when targets crossing split boundaries are excluded.

## Extreme-flow limitation

In the eligible WAPDA baseline, 55 dates reach 100,000 cusecs, five reach 150,000, one reaches 200,000, and none reaches 300,000. The maximum is 255,400 cusecs on 2020-08-28. These are descriptive cutoffs, not verified official flood categories. The 55 dates form 31 consecutive above-cutoff runs; those runs must not be interpreted as 31 hydrologically independent floods. This record provides limited evidence for learning and testing rare extremes. Seasonal 2025-2026 FFD records and historical event maxima must not be treated as a continuous daily extension; inspect complete event hydrographs and measurement compatibility before adding them.

## Conditions before claiming forecast readiness

1. Start with next-day discharge and compare persistence (tomorrow equals the latest reading), a seasonal baseline, and a modest regularized or tree model. Assess whether weather features improve held-out performance before increasing complexity.
2. Use chronological periods, for example 2016-2021 training, 2022 validation, and 2023-2024 testing. Keep every target horizon within its assigned period, protect event boundaries, and fit preprocessing on training data only. Holdout high-flow counts are small; conclusions about rare floods will remain uncertain.
3. Preserve the seven withheld dates as gaps. Do not drop them and then index remaining rows as consecutive days.
4. Resolve observation timing: 3,215 historical WAPDA dates lack individually confirmed reading times. Weather aggregates describe UTC days. Lag predictors to intervals completed and published before the issue time; a matching date label is insufficient.
5. Use CHIRPS v3 Final RNL as the current historical rainfall candidate. The older NASA POWER audit reports a source inconsistency and predates newer features; its statement that temperature and snow are absent is stale. Keep Final and Preliminary rainfall editions distinguishable.
6. Historical analyzed rainfall and ERA5-Land are not future weather forecasts. A 15-day history-only experiment is possible, but useful 15-day warning skill is unproven. For weather-driven forecasts, collect archived weather forecast runs with issue/valid times and evaluate using products actually available at issuance. Future realized weather is not an admissible operational predictor.
7. Review feature physics and aggregation before use. Saved snow means remain approximately 1,019-1,570 mm SWE and 3.40-5.37 m depth across the full record; independently check glacier influence, units, masks, catchment weighting, and spatial coverage. Existing snow/dewpoint exports use a plain regional mean without an explicit physical-area weighting or minimum coverage threshold. These observations warrant review, not automatic rejection or correction.
8. Obtain verified station thresholds and more complete extreme-event records for flood classification. Add upstream observations and relevant operating/release records where available to evaluate predictive benefit. Daily records cannot validate 6-hour or 12-hour forecasts, and discharge series alone do not establish flood depth or extent mapping readiness.

Report per-lead error, peak magnitude and timing error, and threshold-event detection/false alarms where verified thresholds exist. A trained model and held-out comparisons are needed to establish skill; data quantity alone cannot do so.
