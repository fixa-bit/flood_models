# Qadirabad: observed Chenab discharge

`nearby.csv` contains date,q_cumecs with observed inflow in m3/s at 06:00 PKT. Missing days remain NaN. It covers flood seasons, not complete years.

`observations_with_provenance.csv` preserves all extracted inflows/outflows and quality flags; `selected_daily_provenance.csv` identifies each accepted daily value. Inflows and outflows are never substituted for one another. Exact source documents and receipts are in `../_sources/`.

350 eligible observed days; 502 missing dates within 2024-06-16 to 2026-10-15. No regression analysis has been run.
