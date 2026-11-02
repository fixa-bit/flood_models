"""Reuse repository config, observed-day loader, climatology and metrics."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd
import yaml
from data import load_config as load_project_config, read_daily, DataStore
from climatology.model import Climatology
from hbv_residual.evaluation import flow_metrics, threshold_metrics, peak_events


def load_config(path):
    path = Path(path).resolve()
    cfg = yaml.safe_load(path.read_text())
    cfg["_root"] = path.parent
    cfg["_path"] = path
    if cfg["experiment"]["weekly_statistic"] != "maximum":
        raise ValueError("This module verifies weekly MAXIMA, not weekly means")
    return cfg


def resolve(cfg, path):
    return (cfg["_root"] / path).resolve()


def sha(path):
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1024*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def save_json(path, obj):
    def clean(x):
        if isinstance(x, dict): return {str(k): clean(v) for k, v in x.items()}
        if isinstance(x, (list, tuple, np.ndarray)): return [clean(v) for v in x]
        if isinstance(x, (float, np.floating)): return float(x) if np.isfinite(x) else None
        if isinstance(x, np.integer): return int(x)
        if isinstance(x, np.bool_): return bool(x)
        if isinstance(x, (pd.Timestamp, Path)): return str(x)
        return x
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(clean(obj), indent=2, allow_nan=False) + "\n", encoding="utf-8")


def observations(cfg):
    project = load_project_config(resolve(cfg, cfg["project_config"]))
    # Shared DataStore retains source target NaNs, basin IDs and daily alignment.
    store = DataStore(project)
    if "marala" not in store.frames:
        raise ValueError("No Marala basin in the configured existing project")
    return store.frames["marala"].copy(), project


def climatology(cfg, obs, train_years):
    """Fit the repository's existing climatology, never a new baseline definition."""
    class Store:
        pass
    store = Store()
    store.cfg = {"splits": {"train": [min(train_years), max(train_years)]}}
    selected = obs.loc[obs.index.year.isin(train_years)].copy()
    store.frames, store.d = {"marala": selected}, {"target_column": "q_cumecs"}
    return Climatology().fit(store)


def daily_climate(model, dates):
    return np.array([model.daily.get(("marala", d.strftime("%m-%d")), model.basin_mean["marala"])
                     for d in pd.DatetimeIndex(dates)])


def horizons():
    # Week 2 intentionally overlaps daily leads 8-10: separate forecast products.
    return [(f"day_{d:02d}", d, d) for d in range(1, 11)] + [
        ("week_2", 8, 14), ("week_3", 15, 21), ("week_4", 22, 28)]
