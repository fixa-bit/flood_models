"""Audit date overlap and retain the rainfall source-consistency finding.

Uses existing local datasets and saved independent verification responses.
No rainfall values are corrected or imputed by this audit.
"""
import csv
import json
from datetime import datetime, timezone
from pathlib import Path

MODEL = Path(__file__).resolve().parents[1]
PROCESSED = MODEL / "processed/marala"
OUTPUT = PROCESSED / "metadata"


def read(relative):
    with (PROCESSED / relative).open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main():
    discharge = read("discharge/marala_daily_inflow_clean.csv")
    rain = read("rainfall/marala_catchment_daily_precipitation.csv")
    rainfall = {r["date"]: r for r in rain}
    by_year = []
    for year in range(2016, 2027):
        rows = [r for r in discharge if r["date"].startswith(str(year))]
        dates = [r for r in rain if r["date"].startswith(str(year))]
        valid_rain = [r for r in dates if r["precipitation_mm_day"] != ""]
        by_year.append({"year": year, "discharge_dates": len(rows),
                        "eligible_discharge_dates": sum(r["eligible_daily_training"] == "1" for r in rows),
                        "rainfall_dates": len(dates), "rainfall_nonmissing_dates": len(valid_rain),
                        "discharge_dates_without_rainfall_value": sum(r["date"] not in rainfall or rainfall[r["date"]]["precipitation_mm_day"] == "" for r in rows),
                        "rainfall_sum_mm_as_saved": round(sum(float(r["precipitation_mm_day"]) for r in valid_rain), 6),
                        "rainfall_values_cleared_for_training": False})
    evidence_path = MODEL / "raw/marala/rainfall/nasa_power/verification_2026-10-23/source_receipt.json"
    evidence = json.loads(evidence_path.read_text(encoding="utf-8"))["checks"]
    comparisons = [r for r in evidence if r["label"].startswith("daily_")]
    disagreements = [r for r in comparisons if not r["matches"]]
    hourly = next(r for r in evidence if r["label"] == "hourly_20240302")
    usable_structure = [r["eligible_daily_training"] == "1" and r["date"] in rainfall and rainfall[r["date"]]["precipitation_mm_day"] != "" for r in discharge]
    report = {
        "checked_utc": datetime.now(timezone.utc).isoformat(),
        "discharge_span": {"start": discharge[0]["date"], "end": discharge[-1]["date"], "dates": len(discharge), "eligible_dates": sum(r["eligible_daily_training"] == "1" for r in discharge)},
        "rainfall_span": {"start": rain[0]["date"], "end": rain[-1]["date"], "last_nonmissing": max(r["date"] for r in rain if r["precipitation_mm_day"] != "")},
        "missing_rainfall_on_discharge_dates": [r["date"] for r in discharge if r["date"] not in rainfall or rainfall[r["date"]]["precipitation_mm_day"] == ""],
        "temporally_complete_for_wapda_span": all(r["date"] in rainfall and rainfall[r["date"]]["precipitation_mm_day"] != "" for r in discharge),
        "structurally_paired_eligible_dates": sum(usable_structure),
        "training_readiness": "blocked_pending_rainfall_source_consistency_resolution",
        "rainfall_quality_blocked": bool(disagreements),
        "source_consistency": {"spot_checks": comparisons, "disagreements": len(disagreements),
                               "hourly_2024_03_02_sum_mm": hourly["hourly_sum_mm"],
                               "same_full_range_request_reproduces_saved_values": next(r["spot_comparisons"] for r in evidence if r["label"] == "full_range_same_request"),
                               "finding": "At the sampled cell, short-period daily responses disagree with the saved long-period response. On two wet dates, the saved value is exactly 24 times the short-period daily value. The 24 hourly values for 2024-03-02 sum to the short-period daily value. This is request-period-dependent source inconsistency, not an established correction factor for all data.",
                               "evidence_manifest": evidence_path.relative_to(MODEL).as_posix()},
        "candidate_15_day_window_counts_not_training_clearance": {str(lookback): sum(all(usable_structure[i:i+lookback+15]) for i in range(len(usable_structure)-lookback-15+1)) for lookback in (30, 60, 90)},
        "other_features": {"catchment_boundary": "static research boundary available; no annual series needed", "temperature": "not collected", "snow_conditions": "not collected", "soil_moisture": "not collected", "soil_properties": "not collected; mostly static", "archived_15_day_weather_forecasts": "not collected", "reservoir_operations": "not collected"},
        "time_alignment": "Rainfall is accumulated over UTC days (05:00 Pakistan to next 05:00). Most WAPDA observation times are unconfirmed. Shared date labels do not establish a matching observation interval or issue-time availability.",
        "recent_discharge": "2025-2026 FFD data is seasonal, not a year-round continuation; IRSA means remain separate.",
        "next_step": "Recollect rainfall in validated shorter date ranges, independently compare daily totals with hourly values on multiple cells/years and flood events, then recompute the catchment series. Do not divide every saved value by 24 without checking. Collect other chosen historical features over the common 2016-03-01 to 2024-12-19 period."
    }
    OUTPUT.mkdir(parents=True, exist_ok=True)
    (OUTPUT / "marala_feature_coverage_audit.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    with (OUTPUT / "marala_feature_coverage_by_year.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(by_year[0]))
        writer.writeheader()
        writer.writerows(by_year)
    print(f"Date coverage complete: {report['temporally_complete_for_wapda_span']}; paired eligible dates: {sum(usable_structure)}; training readiness: {report['training_readiness']}")


if __name__ == "__main__":
    main()
