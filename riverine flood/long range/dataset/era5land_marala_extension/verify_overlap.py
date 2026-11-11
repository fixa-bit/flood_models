"""Compare the re-extracted 2024 values with the stored short-range 2024 values.

The extension is accepted only if each variable reproduces the stored series
(it is the same source, method and catchment). Writes overlap_verification.json.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "model"))
import common  # noqa: E402

TOLERANCE = {"precip_era5land_mm": 0.05, "temperature_c": 0.05, "dewpoint_c": 0.05, "pet_mm": 0.02,
             "snowmelt_mm": 0.02, "snow_depth_m": 0.002, "swe_mm": 1.0, "ssrd_wm2": 0.5}  # max abs difference


def main():
    ext = pd.read_csv(sorted(HERE.glob("marala_era5land_daily_*.csv"))[-1], parse_dates=["date"]).set_index("date")
    stored = common.load_forcing()
    stored = stored.loc[stored["forcing_source"].eq("short_range_era5land")]
    days = ext.index.intersection(stored.index)
    report = {"overlap_days": int(len(days)), "variables": {}}
    for col in common.FORCING:
        d = (ext.loc[days, col] - stored.loc[days, col]).abs()
        report["variables"][col] = {"max_abs_diff": float(d.max()), "mean_abs_diff": float(d.mean()),
                                    "corr": float(np.corrcoef(ext.loc[days, col], stored.loc[days, col])[0, 1]),
                                    "tolerance": TOLERANCE[col], "pass": bool(d.max() <= TOLERANCE[col])}
    report["all_pass"] = all(v["pass"] for v in report["variables"].values())
    (HERE / "overlap_verification.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
