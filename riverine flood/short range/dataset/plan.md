# Short-range river discharge forecasting plan

Build two separate station forecasts:

1. **Chenab — Marala:** Use past Marala discharge to predict future Marala discharge.
2. **Ravi — Jassar:** Use past Jassar discharge to predict future Jassar discharge.

Start with a next-day forecast using daily readings. Predict the next day's value from readings available before the forecast is made. Consider 6- or 12-hour forecasts only when actual subdaily records are available.


Time Horizon:
There is no single forecast length that suits every river. It depends on how quickly its flow changes and what data the model receives.


Time conflict:
Time of discharge recording of wapda:

There is a confirmed time for one reading: WAPDA labels Marala’s 19 December 2024 reading as taken at 06:00.
There is no confirmed time for every reading in the historical workbook. That file gives a date for each value, but no time. We can reasonably use 06:00 as a working assumption, and label it as an assumption until WAPDA confirms that the same schedule applied throughout 2016–2024.

I found a problem in the 2024 archive labels: some entries listed under October open PDFs dated June. I’ll use the date printed inside each bulletin, keep the archive’s listed date for tracing, and recheck the extracted values against WAPDA.
I saved the available Marala discharge data in the [combined catalog](D:/projects/flood_model/flood_model/riverine flood/short range/dataset/chenab_marala/processed/marala_discharge_all_sources.csv). Each of its 3,902 rows includes a date, value, source link, and a time where the source confirms one.
FFD confirms 06:00 Pakistan time for 656 readings. A companion WAPDA report confirms 06:00 for one WAPDA reading. The other 3,245 rows have a blank time because their individual observation times are unverified. Archive date conflicts and questionable values are flagged; the [source notes](D:/projects/flood_model/flood_model/riverine flood/short range/dataset/chenab_marala/raw/marala/discharge/README.md) explain the gaps and sources.

Source:
WAPDA source page: [River Flow](https://wapda.gov.pk/river-flow/). Direct link to the downloaded historical file: [GRAPH-DG-16-for-MAIL-2.xls](https://wapda.gov.pk/wp-content/uploads/2024/12/GRAPH-DG-16-for-MAIL-2.xls).



FFD Dischrage:
The FFD bulletins provide confirmed 06:00 readings for 2024, 2025, and 2026. Some archive dates disagree with the dates printed inside the PDFs, so I kept both dates and flagged those rows instead of silently choosing one for training.

## Data collection

- **Marala:** First collect the [WAPDA River Flow workbook](https://wapda.gov.pk/wp-content/uploads/2024/12/GRAPH-DG-16-for-MAIL-2.xls) into `chenab_marala/raw/marala/`. Its verified daily Marala inflow series covers 1 March 2016 to 19 December 2024. Keep the original workbook. Check units, reading time, and the one zero value before training. Use past Marala inflow to forecast future Marala inflow; keep outflow separate if obtained later.


- **Jassar:** [FFD flood bulletins](https://ffd.pmd.gov.pk/bulletin/) publish Jassar discharge readings. Obtain a complete historical Jassar series before training and store it in `ravi_jassar/raw/jassar/`.
- Put each station's cleaned data and forecast targets in its own `processed/` folder. Align timestamps and units, flag questionable readings, and split data by time so the same flood event does not span training and test sets.

Neither model uses Khanki, Shahdara, or Ravi Syphon data. See [historical_coverage.md](historical_coverage.md) for the source checks completed so far.




Rainfall data:

the verified upstream catchment boundary in the project for marala

Catcment area:
Marala inflow location documented by JICA and in research papers, plus a terrain-derived boundary of about 28,800 km². That is close to published upstream-area estimates.
The boundary passes the geometry check and gives about 28,781 km², roughly 1.4% below the area in the PMD paper. JICA’s station table confirms the outlet coordinates, and moving the outlet slightly produced the same catchment.

[chenab_marala/processed/marala/catchment/](D:/projects/flood_model/flood_model/riverine flood/short range/dataset/chenab_marala/processed/marala/catchment/)

File: marala_upstream_catchment.geojson