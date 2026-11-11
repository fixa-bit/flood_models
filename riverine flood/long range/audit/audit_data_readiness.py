"""Phase 0 data-readiness audit for the long-range (2026-2040) projection engine.

Reads the short-range Marala/Chenab datasets READ-ONLY and measures what each
series actually covers. Nothing is downloaded, filled, merged or modelled.

Outputs (written next to this script):
  data_readiness.json  machine-readable coverage per series + declared gaps
  data_readiness.md    human-readable summary table

Run from anywhere:
  python "riverine flood/long range/audit/audit_data_readiness.py"
"""
from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
RIVERINE = HERE.parents[1]
SHORT = RIVERINE / "short range"
MARALA = SHORT / "dataset/chenab_marala"
NEARBY = MARALA / "raw/marala/discharge/nearby stations"

# Windows the projection system needs. CMIP6 "historical" ends 2014; SSP runs start 2015.
WINDOWS = {
    "cmip6_historical_reference_1985_2014": ("1985-01-01", "2014-12-31"),
    "observed_validation_2015_2025": ("2015-01-01", "2025-12-31"),
}
FLOOD_SEASON_MONTHS = {6, 7, 8, 9, 10}


@dataclass(frozen=True)
class Series:
    key: str
    station_or_area: str
    variable: str
    kind: str  # observed | reanalysis | satellite_gauge_blend | simulated | event_peaks
    independent_ground_truth: bool
    path: Path
    date_col: str
    value_col: str
    unit: str
    filter_col: str | None = None  # keep rows where this column == 1
    note: str = ""


SERIES = [
    Series("marala_inflow_wapda", "Marala barrage", "inflow discharge", "observed", True,
           MARALA / "processed/marala/discharge/marala_daily_inflow_clean.csv", "date", "inflow_m3_s", "m3/s",
           filter_col="eligible_daily_training",
           note="Dated WAPDA reading; daily-mean vs 06:00 basis unconfirmed for most of the archive."),
    Series("marala_inflow_sindh_rim", "Marala barrage", "inflow discharge", "observed", True,
           MARALA / "processed/marala/discharge/marala_sindh_rimstation_discharge.csv", "date", "inflow_m3_s", "m3/s",
           note="Sindh Irrigation rim-station bulletins; extends Marala beyond the WAPDA workbook."),
    Series("marala_outflow_sindh_rim", "Marala barrage", "outflow discharge", "observed", True,
           MARALA / "processed/marala/discharge/marala_sindh_rimstation_discharge.csv", "date", "outflow_m3_s", "m3/s",
           note="Outflow below the barrage (after Upper Chenab / MR link withdrawals)."),
    Series("trimmu_inflow_ffd", "Trimmu barrage", "inflow discharge", "observed", True,
           NEARBY / "Trimmu/selected_daily_provenance.csv", "date", "inflow_cumecs", "m3/s",
           filter_col="eligible_daily", note="FFD 06:00 PKT bulletin readings; flood seasons only."),
    Series("trimmu_outflow_ffd", "Trimmu barrage", "outflow discharge", "observed", True,
           NEARBY / "Trimmu/selected_daily_provenance.csv", "date", "outflow_cumecs", "m3/s",
           filter_col="eligible_daily", note="Inflow minus outflow approximates canal/link withdrawals at the barrage."),
    Series("qadirabad_inflow_ffd", "Qadirabad barrage", "inflow discharge", "observed", True,
           NEARBY / "Qadirabad/selected_daily_provenance.csv", "date", "inflow_cumecs", "m3/s",
           filter_col="eligible_daily"),
    Series("khanki_inflow_ffd", "Khanki headworks", "inflow discharge", "observed", True,
           NEARBY / "Khanki/selected_daily_provenance.csv", "date", "inflow_cumecs", "m3/s",
           filter_col="eligible_daily"),
    Series("marala_glofas_v5", "Marala (GloFAS cell 32.675N 74.475E)", "discharge", "simulated", False,
           MARALA / "processed/marala/discharge/simulated/marala_glofas_historical_daily.csv",
           "date_utc_day_averaged", "glofas_v5_0_m3_s", "m3/s",
           note="Model output. Not independent ground truth; not calibrated at Marala."),
    Series("marala_precip_chirps_v3", "Marala catchment mean", "precipitation", "satellite_gauge_blend", False,
           MARALA / "processed/marala/rainfall/chirps_v3_primary/marala_chirps_v3_final_rnl_daily_1990_2026.csv",
           "date", "precipitation_mm", "mm/day"),
    Series("marala_precip_era5", "Marala catchment mean", "precipitation", "reanalysis", False,
           SHORT / "evaluation comparison/common/data/marala_daily.csv", "date", "rain_era5_mm", "mm/day"),
    Series("marala_tas_era5land", "Marala catchment mean", "2 m air temperature (daily mean)", "reanalysis", False,
           MARALA / "raw/marala/temperature/google_earth_engine/marala_daily_temperature_1980_2024.csv",
           "date", "era5land_temperature_2m_c", "degC",
           note="Daily mean only: no tasmin/tasmax extracted yet."),
    Series("marala_swe_era5land", "Marala catchment mean", "snow water equivalent", "reanalysis", False,
           MARALA / "raw/marala/marala_daily_snow_1980_2024.csv", "date", "swe_mm", "mm"),
    Series("marala_pet_era5land", "Marala catchment mean", "potential evaporation", "reanalysis", False,
           SHORT / "evaluation comparison/common/data/marala_daily.csv", "date", "pet_mm", "mm/day"),
]

# Inputs the projection design needs that were searched for and NOT found locally.
DECLARED_GAPS = [
    {"item": "Trimmu year-round daily inflow/outflow (any year)", "status": "missing",
     "consequence": "No calibration or independent validation possible at Trimmu.",
     "action": "Request daily 2000-2025 records from Punjab Irrigation Department / FFD / WAPDA."},
    {"item": "Mangla inflow/outflow and Rasul (Jhelum) series", "status": "in_raw_workbook_not_extracted",
     "consequence": "Jhelum branch to Trimmu cannot be represented yet.",
     "action": "Extract Mangla columns from the saved WAPDA GRAPH-DG-16 workbook (2016-03 to 2024-12); request Rasul."},
    {"item": "Canal/link withdrawals at Marala, Khanki, Qadirabad, Rasul, Trimmu", "status": "missing",
     "consequence": "Natural vs regulated flow cannot be separated from measurements.",
     "action": "Request IRSA/Punjab Irrigation canal head discharges; until then use labelled operation scenarios."},
    {"item": "Trimmu (Chenab+Jhelum) contributing catchment and its forcings", "status": "missing",
     "consequence": "Climate forcing only exists for the Marala catchment.",
     "action": "Delineate with the same MERIT/Global Watersheds method used for Marala; rerun GEE extractors."},
    {"item": "CMIP6 / NEX-GDDP-CMIP6 / CORDEX climate projections", "status": "missing",
     "consequence": "No future forcing exists locally.",
     "action": "Phase 2 connector (NEX-GDDP-CMIP6 on AWS open data, catchment-mean extraction)."},
    {"item": "ERA5-Land tasmin/tasmax", "status": "missing",
     "consequence": "Bias correction of CMIP6 tasmin/tasmax has no local reference.",
     "action": "Extend the existing ERA5-Land GEE extractor."},
    {"item": "Pre-2016 continuous observed Marala discharge", "status": "missing",
     "consequence": "Differential split-sample testing limited to ~10 observed years.",
     "action": "Pursue the WAPDA/IRSA historical request already drafted in short range."},
]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def coverage(dates: pd.Series, values: pd.Series) -> dict:
    """Coverage statistics for one daily series. Missing values are counted, never filled."""
    frame = pd.DataFrame({"date": pd.to_datetime(dates, errors="coerce"),
                          "value": pd.to_numeric(values, errors="coerce")})
    frame = frame.dropna(subset=["date"]).drop_duplicates("date").sort_values("date")
    valid = frame.dropna(subset=["value"])
    if valid.empty:
        return {"n_valid_days": 0}
    first, last = valid["date"].min(), valid["date"].max()
    span = (last - first).days + 1
    present = set(valid["date"].dt.normalize())
    calendar = pd.date_range(first, last, freq="D")
    missing_mask = ~calendar.isin(list(present))
    longest_gap = run = 0
    for missing in missing_mask:
        run = run + 1 if missing else 0
        longest_gap = max(longest_gap, run)
    per_year = valid.groupby(valid["date"].dt.year).size()
    days_in_year = {y: 366 if pd.Timestamp(year=y, month=1, day=1).is_leap_year else 365 for y in per_year.index}
    complete_years = [int(y) for y, n in per_year.items() if n >= 0.9 * days_in_year[y]]
    months = sorted(set(valid["date"].dt.month))
    windows = {}
    for name, (start, end) in WINDOWS.items():
        in_window = valid[(valid["date"] >= start) & (valid["date"] <= end)]
        windows[name] = int(len(in_window))
    return {
        "first_valid": str(first.date()),
        "last_valid": str(last.date()),
        "n_valid_days": int(len(valid)),
        "span_days": int(span),
        "completeness_within_span": round(len(valid) / span, 4),
        "longest_internal_gap_days": int(longest_gap),
        "years_at_least_90pct_complete": complete_years,
        "months_present": months,
        "flood_season_only": set(months) <= FLOOD_SEASON_MONTHS,
        "valid_days_in_window": windows,
        "min": round(float(valid["value"].min()), 3),
        "max": round(float(valid["value"].max()), 3),
    }


def audit_series(item: Series) -> dict:
    record = {"key": item.key, "station_or_area": item.station_or_area, "variable": item.variable,
              "kind": item.kind, "independent_ground_truth": item.independent_ground_truth,
              "unit": item.unit, "path": str(item.path.relative_to(RIVERINE)).replace("\\", "/"),
              "note": item.note}
    if not item.path.is_file():
        record["status"] = "file_missing"
        return record
    frame = pd.read_csv(item.path, low_memory=False)
    if item.filter_col:
        frame = frame[pd.to_numeric(frame[item.filter_col], errors="coerce") == 1]
    record.update(status="ok", source_sha256=sha256(item.path),
                  coverage=coverage(frame[item.date_col], frame[item.value_col]))
    return record


def audit_peaks() -> dict:
    path = MARALA / "processed/marala/discharge/marala_pmd_historical_flood_peaks.csv"
    frame = pd.read_csv(path)
    dates = pd.to_datetime(frame["peak_date"], errors="coerce")
    return {"key": "marala_pmd_flood_peaks", "kind": "event_peaks", "independent_ground_truth": True,
            "path": str(path.relative_to(RIVERINE)).replace("\\", "/"), "source_sha256": sha256(path),
            "n_events": int(len(frame)), "first": str(dates.min().date()), "last": str(dates.max().date()),
            "note": "Selected event maxima (published). Usable only for extreme-value plausibility checks."}


def readiness_verdicts(series: list[dict]) -> dict:
    by_key = {s["key"]: s for s in series}

    def years(key):
        return by_key.get(key, {}).get("coverage", {}).get("years_at_least_90pct_complete", [])

    marala_years = sorted(set(years("marala_inflow_wapda")) | set(years("marala_inflow_sindh_rim")))
    trimmu = by_key.get("trimmu_inflow_ffd", {}).get("coverage", {})
    return {
        "marala": {
            "complete_observed_years": marala_years,
            "physical_model_calibration": "feasible" if len(marala_years) >= 8 else "limited",
            "independent_validation": "feasible_but_short" if len(marala_years) >= 8 else "insufficient",
            "ai_residual_correction": "experimental_only (about a decade of observations; blocked leave-one-year-out)",
        },
        "trimmu": {
            "complete_observed_years": years("trimmu_inflow_ffd"),
            "valid_days": trimmu.get("n_valid_days", 0),
            "flood_season_only": trimmu.get("flood_season_only"),
            "physical_model_calibration": "not_feasible",
            "independent_validation": "not_feasible (flood-season spot checks only)",
            "ai_residual_correction": "disabled",
        },
    }


def to_markdown(report: dict) -> str:
    lines = [
        "# Long-range projection: data-readiness audit",
        "",
        f"Generated {report['generated_utc']} by `audit/audit_data_readiness.py` (read-only over short-range data).",
        "Counts are valid daily values after the source's own eligibility flags. Nothing was filled or merged.",
        "",
        "| Series | Kind | Independent truth | First | Last | Valid days | Complete years (>=90%) | Flood-season only | Days in 1985-2014 | Days in 2015-2025 |",
        "|---|---|---|---|---|---:|---|---|---:|---:|",
    ]
    for s in report["series"]:
        c = s.get("coverage", {})
        if s.get("status") != "ok":
            lines.append(f"| {s['key']} | {s['kind']} | {s['independent_ground_truth']} | file missing | | | | | | |")
            continue
        yrs = c.get("years_at_least_90pct_complete", [])
        yr_text = f"{len(yrs)} ({yrs[0]}-{yrs[-1]})" if yrs else "0"
        w = c.get("valid_days_in_window", {})
        lines.append(
            f"| {s['key']} | {s['kind']} | {'yes' if s['independent_ground_truth'] else 'no'} | {c.get('first_valid')} | "
            f"{c.get('last_valid')} | {c.get('n_valid_days')} | {yr_text} | {'yes' if c.get('flood_season_only') else 'no'} | "
            f"{w.get('cmip6_historical_reference_1985_2014', 0)} | {w.get('observed_validation_2015_2025', 0)} |")
    p = report["event_peaks"]
    lines += ["", f"Event peaks: {p['n_events']} published Marala flood maxima, {p['first']} to {p['last']} (PMD journal).",
              "", "## Readiness verdicts", ""]
    for station, verdict in report["verdicts"].items():
        lines.append(f"- **{station.title()}**: " + "; ".join(f"{k} = {v}" for k, v in verdict.items()
                                                             if k != "complete_observed_years")
                     + f"; complete observed years = {verdict['complete_observed_years'] or 'none'}")
    lines += ["", "## Required inputs not found locally", "", "| Item | Status | Consequence | Action |", "|---|---|---|---|"]
    for gap in report["declared_gaps"]:
        lines.append(f"| {gap['item']} | {gap['status']} | {gap['consequence']} | {gap['action']} |")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=HERE)
    args = parser.parse_args(argv)
    series = [audit_series(item) for item in SERIES]
    report = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "scope": "Phase 0 audit; no training, downloads or data modification",
        "windows": WINDOWS,
        "series": series,
        "event_peaks": audit_peaks(),
        "verdicts": readiness_verdicts(series),
        "declared_gaps": DECLARED_GAPS,
    }
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "data_readiness.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    (args.out_dir / "data_readiness.md").write_text(to_markdown(report), encoding="utf-8")
    for s in series:
        c = s.get("coverage", {})
        print(f"{s['key']:28s} {s.get('status'):12s} {c.get('first_valid', '-')}..{c.get('last_valid', '-')} "
              f"n={c.get('n_valid_days', 0)}")
    return report


if __name__ == "__main__":
    main()
