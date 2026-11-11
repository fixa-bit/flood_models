"""Score saved model predictions for the portal's Models and Performance analyzer views.

The builder reads the prediction files named in ``model_catalog.json`` and the model
runs it discovers under the catalog's discovery roots. For every model it

* keeps one compact copy of each distinct set of predictions (a *version*),
* scores the current version against observations, lead by lead,
* compares it with its cohort's baselines on matched issue dates and leads, and
* ranks every cohort member on one shared sample of issue dates and leads.

Outputs, all under ``dist/data``:

``models.json``
    What the browser reads: catalog, scores, cohort tables, the flood-peak model and
    the climate projections.
``model_versions.json``
    The version ledger. It is append-only: a version stays listed, with the scores
    recorded when it was first seen, after its source file has been replaced.
``models/<model>/<sha>.json``
    Compact predictions for each version. These are generated, but a version whose
    source file has since been overwritten can only be re-plotted from this copy.

Only the Python standard library is used. Source files are read and never changed.
"""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import math
import os
import re
import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path

PORTAL = Path(__file__).resolve().parent
WORKSPACE = PORTAL.parent
DIST = PORTAL / "dist"
CATALOG = PORTAL / "model_catalog.json"

SCORING_VERSION = 1
DETAIL_FORMAT = 1
LEAD_FACTOR = 1000                # cell key = issue date ordinal * LEAD_FACTOR + lead
COMMON_SAMPLE_MIN_COVER = 0.5     # members covering less of the reference sample are ranked separately
OBS_ABS_TOL = 0.5                 # m3/s; two files agree on an observation within this tolerance...
OBS_REL_TOL = 0.005               # ...or within this relative difference
VERSION_CHANGE_TOL = 0.01         # relative RMSE change below this is reported as unchanged
RUN_EXCLUDE = re.compile(r"valid|smoke|debug|tmp|temp|archive|scratch", re.IGNORECASE)
DATED_RUN = re.compile(r"^\d{4}-\d{2}-\d{2}")
WALK_PRUNE = {".venv", "venv", "__pycache__", ".pytest_cache", ".git", "node_modules", "runs", "data",
              "_vendor", "source_reference", "reference", "experiment_archive", "tests", "controls"}
COLUMN_CANDIDATES = {
    "issue": ("issue_date", "issue_after_date"),
    "target": ("target_date", "valid_date"),
    "lead": ("lead_day", "lead_days", "horizon_days"),
    "observed": ("observed_cumecs", "observed_m3_s", "observed", "obs_m3s", "observed_q_cumecs",
                 "observed_future_mean_q", "obs_mean"),
}
NON_PREDICTION_COLUMNS = {
    "basin_id", "station", "season", "year", "monsoon", "split", "fold_year", "model", "mode", "cohort",
    "member_count", "forcing_mode", "target_source", "measurement_basis", "highflow", "source", "obs_source",
    "grrr_last_input_available", "evaluation_year", "training_first_year", "training_last_year", "test_year",
    "selected_alpha", "reference_observed", "group",
}
META_COLUMN = re.compile(r"threshold|probability|exceed|_flag$|status|^train_|_q95_", re.IGNORECASE)
QUANTILE_COLUMN = re.compile(r"(^|_)(q0?\.\d+|p\d{1,2})$", re.IGNORECASE)
INTERVAL_PAIRS = (("q0.05", "q0.95", [0.05, 0.95]), ("q0.1", "q0.9", [0.1, 0.9]),
                  ("q0.10", "q0.90", [0.1, 0.9]), ("p10", "p90", [0.1, 0.9]), ("q0.25", "q0.75", [0.25, 0.75]))
Z90 = 1.2815515655446004          # standard normal quantile for P10/P90


# --------------------------------------------------------------------------- helpers

def utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0)


def iso(moment):
    return moment.isoformat().replace("+00:00", "Z")


def iso_from_timestamp(seconds):
    return iso(datetime.fromtimestamp(seconds, timezone.utc).replace(microsecond=0))


def relative(path, root):
    try:
        return Path(path).resolve().relative_to(Path(root).resolve()).as_posix()
    except ValueError:
        return Path(path).as_posix()


def slug(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", str(text)).strip("_") or "model"


def sha256_text(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def num(text):
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def rnd(value, digits):
    return None if value is None else round(value, digits)


def read_json(path, default=None):
    path = Path(path)
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return default


def write_json(path, value, indent=None):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    text = json.dumps(value, indent=indent, separators=None if indent else (",", ":"), allow_nan=False)
    temporary.write_text(text + ("\n" if indent else ""), encoding="utf-8")
    temporary.replace(path)


def open_text(path):
    path = Path(path)
    if path.name.endswith(".gz"):
        return io.TextIOWrapper(gzip.open(path, "rb"), encoding="utf-8-sig", newline="")
    return path.open("r", encoding="utf-8-sig", newline="")


def file_signature(path):
    stat = Path(path).stat()
    return {"bytes": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def obs_close(a, b):
    return abs(a - b) <= max(OBS_ABS_TOL, OBS_REL_TOL * max(abs(a), abs(b)))


def markdown_title(path):
    path = Path(path)
    if path.suffix.lower() != ".md" or not path.is_file():
        return None
    try:
        with path.open(encoding="utf-8-sig") as handle:
            for line in handle:
                if line.startswith("# "):
                    return line[2:].strip()
    except (OSError, UnicodeError):
        return None
    return None


# --------------------------------------------------------------------------- metrics

class Acc:
    """Single-pass sums for point-forecast scores of observed (o) and predicted (s) flow."""
    __slots__ = ("n", "so", "ss", "soo", "sss", "sos", "sse", "sae")

    def __init__(self):
        self.n = 0
        self.so = self.ss = self.soo = self.sss = self.sos = self.sse = self.sae = 0.0

    def add(self, o, s):
        self.n += 1
        self.so += o
        self.ss += s
        self.soo += o * o
        self.sss += s * s
        self.sos += o * s
        d = s - o
        self.sse += d * d
        self.sae += d if d >= 0 else -d

    def result(self):
        n = self.n
        if not n:
            return {"n": 0}
        mo, ms = self.so / n, self.ss / n
        var_o = max(self.soo / n - mo * mo, 0.0)
        var_s = max(self.sss / n - ms * ms, 0.0)
        cov = self.sos / n - mo * ms
        rmse = math.sqrt(self.sse / n)
        nse = 1 - self.sse / (n * var_o) if var_o > 0 else None
        r = cov / math.sqrt(var_o * var_s) if var_o > 0 and var_s > 0 else None
        kge = None
        if r is not None and mo:
            kge = 1 - math.sqrt((r - 1) ** 2 + (math.sqrt(var_s / var_o) - 1) ** 2 + (ms / mo - 1) ** 2)
        return {"n": n, "rmse": rnd(rmse, 3), "mae": rnd(self.sae / n, 3), "nse": rnd(nse, 5), "kge": rnd(kge, 5),
                "pbias": rnd(100 * (self.ss - self.so) / self.so, 3) if self.so else None, "r": rnd(r, 5),
                "mean_obs": rnd(mo, 3), "mean_pred": rnd(ms, 3)}


def coverage_fields(counts):
    n, inside, width = counts
    return {"cov_n": n, "cov": rnd(inside / n, 5), "width": rnd(width / n, 2)} if n else {}


def contingency_fields(counts):
    if not counts:
        return {}
    hits, misses, false_alarms, negatives = counts
    events = hits + misses
    warned = hits + false_alarms
    return {"hits": hits, "misses": misses, "false_alarms": false_alarms, "correct_negatives": negatives,
            "hit_rate": rnd(hits / events, 5) if events else None,
            "far": rnd(false_alarms / warned, 5) if warned else None,
            "csi": rnd(hits / (events + false_alarms), 5) if events + false_alarms else None}


def pair_fields(lead, model, base):
    a, b = model.result(), base.result()
    skill = None
    if a["n"] and b.get("rmse"):
        skill = rnd(1 - a["rmse"] / b["rmse"], 5)
    row = {"n": a["n"], "rmse": a.get("rmse"), "rmse_base": b.get("rmse"), "skill": skill,
           "mae": a.get("mae"), "mae_base": b.get("mae"), "nse": a.get("nse"), "nse_base": b.get("nse"),
           "kge": a.get("kge"), "kge_base": b.get("kge"), "pbias": a.get("pbias"), "pbias_base": b.get("pbias")}
    if lead is not None:
        row = {"lead": lead, **row}
    return row


# --------------------------------------------------------------------------- compact predictions

class Extractor:
    """Collects one model's cells from a prediction file."""

    def __init__(self, model_id, columns, filters, interval, kind):
        self.model_id = model_id
        self.columns = dict(columns or {})
        self.filters = {key: str(value) for key, value in (filters or {}).items()}
        self.interval = interval
        self.kind = kind or "daily"
        self.cells = {}
        self.rows = 0
        self.conflicts = 0
        self.missing_prediction = 0
        self.bad_rows = 0
        self.plan = None
        self.error = None

    def signature(self):
        return sha256_text(canonical({"columns": self.columns, "filters": self.filters, "interval": self.interval,
                                      "kind": self.kind, "format": DETAIL_FORMAT}))[:16]

    def resolve(self, index):
        def pick(role, required):
            name = self.columns.get(role)
            if name:
                if name not in index:
                    raise KeyError(f"column '{name}' ({role}) is not in the file")
                return index[name]
            for candidate in COLUMN_CANDIDATES.get(role, ()):
                if candidate in index:
                    return index[candidate]
            if required:
                raise KeyError(f"no {role} column found")
            return None

        point = self.columns.get("point")
        if not point or point not in index:
            raise KeyError(f"prediction column '{point}' is not in the file")
        low, high = self.columns.get("low"), self.columns.get("high")
        low_index = index.get(low) if low else None
        high_index = index.get(high) if high else None
        if low_index is None or high_index is None:
            low_index = high_index = None
            self.interval = None
        self.plan = (pick("issue", True), pick("target", False), pick("lead", True), pick("observed", True),
                     index[point], low_index, high_index)

    def add(self, row, dates):
        issue_i, target_i, lead_i, obs_i, point_i, low_i, high_i = self.plan
        self.rows += 1
        prediction = num(row[point_i])
        if prediction is None:
            self.missing_prediction += 1
            return
        text = row[issue_i][:10]
        issue = dates.get(text)
        if issue is None:
            issue = dates[text] = date.fromisoformat(text).toordinal()
        lead = int(float(row[lead_i]))
        target = None
        if target_i is not None:
            text = row[target_i][:10]
            target = dates.get(text)
            if target is None:
                target = dates[text] = date.fromisoformat(text).toordinal()
        key = issue * LEAD_FACTOR + lead
        existing = self.cells.get(key)
        prediction = round(prediction, 1)
        if existing is not None:
            if existing[0] != prediction:
                self.conflicts += 1
            return
        observed = num(row[obs_i])
        low = num(row[low_i]) if low_i is not None else None
        high = num(row[high_i]) if high_i is not None else None
        self.cells[key] = (prediction, None if low is None else round(low, 1), None if high is None else round(high, 1),
                           None if observed is None else round(observed, 1), target)

    def compact(self):
        if not self.cells:
            return None
        issues = sorted({key // LEAD_FACTOR for key in self.cells})
        leads = sorted({key % LEAD_FACTOR for key in self.cells})
        issue_pos = {value: i for i, value in enumerate(issues)}
        lead_pos = {value: j for j, value in enumerate(leads)}
        width = len(leads)
        size = len(issues) * width
        has_interval = self.interval is not None and any(cell[1] is not None and cell[2] is not None
                                                         for cell in self.cells.values())
        p50 = [None] * size
        low = [None] * size if has_interval else None
        high = [None] * size if has_interval else None
        series_mode = self.kind == "daily" and all(cell[4] is None or cell[4] == key // LEAD_FACTOR + key % LEAD_FACTOR
                                                   for key, cell in self.cells.items())
        observed_by_target = {}
        observed_cells = None if series_mode else [None] * size
        obs_conflicts = 0
        for key, (prediction, lo, hi, observed, _target) in self.cells.items():
            issue, lead = divmod(key, LEAD_FACTOR)
            position = issue_pos[issue] * width + lead_pos[lead]
            p50[position] = prediction
            if has_interval:
                low[position], high[position] = lo, hi
            if series_mode:
                if observed is not None:
                    target = issue + lead
                    seen = observed_by_target.get(target)
                    if seen is None:
                        observed_by_target[target] = observed
                    elif not obs_close(seen, observed):
                        obs_conflicts += 1
            else:
                observed_cells[position] = observed
        if series_mode:
            if observed_by_target:
                first, last = min(observed_by_target), max(observed_by_target)
                values = [observed_by_target.get(day) for day in range(first, last + 1)]
                obs = {"mode": "series", "day0": date.fromordinal(first).isoformat(), "values": values}
            else:
                obs = {"mode": "series", "day0": date.fromordinal(issues[0]).isoformat(), "values": []}
        else:
            obs = {"mode": "cell", "values": observed_cells}
        compact = {"kind": self.kind, "day0": date.fromordinal(issues[0]).isoformat(),
                   "issues": [value - issues[0] for value in issues], "leads": leads,
                   "interval": self.interval if has_interval else None,
                   "p50": p50, "lo": low, "hi": high, "obs": obs}
        stats = {"rows": self.rows, "cells": len(self.cells), "duplicate_conflicts": self.conflicts,
                 "observation_conflicts": obs_conflicts, "rows_without_prediction": self.missing_prediction,
                 "unreadable_rows": self.bad_rows}
        return compact, stats


def parse_file(path, extractors, value_column=None, value_filters=None):
    """Read a prediction file once, feeding each row to the extractors whose filters match.

    Returns the distinct values of ``value_column`` (rows matching ``value_filters``) when asked.
    """
    values = set()
    with open_text(path) as handle:
        reader = csv.reader(handle)
        header = [name.strip() for name in next(reader, [])]
        index = {name: i for i, name in enumerate(header)}
        groups = defaultdict(dict)
        for extractor in extractors:
            try:
                extractor.resolve(index)
                columns = tuple(sorted(extractor.filters))
                missing = [name for name in columns if name not in index]
                if missing:
                    raise KeyError(f"filter column {missing[0]!r} is not in the file")
                positions = tuple(index[name] for name in columns)
                key = tuple(extractor.filters[name] for name in columns)
                groups[positions].setdefault(key, []).append(extractor)
            except (KeyError, ValueError) as error:
                extractor.error = str(error)
        value_index = index.get(value_column) if value_column else None
        value_filter = [(index[name], str(wanted)) for name, wanted in (value_filters or {}).items() if name in index]
        dates = {}
        for row in reader:
            if not row:
                continue
            try:
                if value_index is not None and all(row[i] == wanted for i, wanted in value_filter):
                    values.add(row[value_index])
                for positions, table in groups.items():
                    matched = table.get(tuple(row[i] for i in positions) if positions else ())
                    if matched:
                        for extractor in matched:
                            try:
                                extractor.add(row, dates)
                            except (ValueError, IndexError):
                                extractor.bad_rows += 1
            except IndexError:
                continue
    return values


def scan_values(path, column, filters):
    with open_text(path) as handle:
        reader = csv.reader(handle)
        header = [name.strip() for name in next(reader, [])]
        if column not in header:
            return set()
        position = header.index(column)
        checks = [(header.index(name), str(value)) for name, value in (filters or {}).items() if name in header]
        values = set()
        for row in reader:
            if len(row) > position and all(len(row) > i and row[i] == wanted for i, wanted in checks):
                values.add(row[position])
    return values


def sniff_header(path):
    with open_text(path) as handle:
        reader = csv.reader(handle)
        header = [name.strip() for name in next(reader, [])]
        first = next(reader, None)
    return header, first


class View:
    """Read access to one compact prediction set."""

    def __init__(self, compact):
        start = date.fromisoformat(compact["day0"]).toordinal()
        self.kind = compact.get("kind", "daily")
        self.issue_ords = [start + offset for offset in compact["issues"]]
        self.leads = compact["leads"]
        self.width = len(self.leads)
        self.p50 = compact["p50"]
        self.lo = compact.get("lo")
        self.hi = compact.get("hi")
        self.interval = compact.get("interval")
        obs = compact["obs"]
        if obs["mode"] == "series":
            self.obs_series = obs["values"]
            self.obs_start = date.fromisoformat(obs["day0"]).toordinal()
            self.obs_cells = None
        else:
            self.obs_series = None
            self.obs_start = None
            self.obs_cells = obs["values"]
        self._index = None

    def cells(self):
        """Yield (key, lead position, prediction, low, high, observed) for every predicted cell."""
        width, leads, p50, lo, hi = self.width, self.leads, self.p50, self.lo, self.hi
        series, cells = self.obs_series, self.obs_cells
        start = self.obs_start or 0
        length = len(series) if series is not None else 0
        for i, issue in enumerate(self.issue_ords):
            base = i * width
            key_base = issue * LEAD_FACTOR
            for j in range(width):
                prediction = p50[base + j]
                if prediction is None:
                    continue
                lead = leads[j]
                if series is not None:
                    t = issue + lead - start
                    observed = series[t] if 0 <= t < length else None
                else:
                    observed = cells[base + j]
                yield (key_base + lead, j, prediction, lo[base + j] if lo is not None else None,
                       hi[base + j] if hi is not None else None, observed)

    def index(self):
        if self._index is None:
            self._index = {key: (prediction, observed) for key, _, prediction, _, _, observed in self.cells()}
        return self._index

    def period(self):
        if not self.issue_ords:
            return {}
        last_lead = max(self.leads) if self.leads else 0
        return {"first_issue": date.fromordinal(self.issue_ords[0]).isoformat(),
                "last_issue": date.fromordinal(self.issue_ords[-1]).isoformat(),
                "last_target": date.fromordinal(self.issue_ords[-1] + last_lead).isoformat(),
                "issues": len(self.issue_ords), "leads": len(self.leads)}


def score_view(view, threshold=None):
    width = view.width
    per_lead = [Acc() for _ in range(width)]
    pooled = Acc()
    coverage = [[0, 0, 0.0] for _ in range(width)]
    coverage_all = [0, 0, 0.0]
    events = [[0, 0, 0, 0] for _ in range(width)] if threshold is not None else None
    events_all = [0, 0, 0, 0]
    cells = 0
    for _key, j, prediction, low, high, observed in view.cells():
        cells += 1
        if observed is None:
            continue
        per_lead[j].add(observed, prediction)
        pooled.add(observed, prediction)
        if low is not None and high is not None:
            inside = 1 if low <= observed <= high else 0
            counts = coverage[j]
            counts[0] += 1
            counts[1] += inside
            counts[2] += high - low
            coverage_all[0] += 1
            coverage_all[1] += inside
            coverage_all[2] += high - low
        if events is not None:
            happened, warned = observed > threshold, prediction > threshold
            slot = 0 if happened and warned else 1 if happened else 2 if warned else 3
            events[j][slot] += 1
            events_all[slot] += 1
    by_lead = []
    for j, lead in enumerate(view.leads):
        row = {"lead": lead, **per_lead[j].result(), **coverage_fields(coverage[j])}
        if events is not None:
            row.update(contingency_fields(events[j]))
        by_lead.append(row)
    summary = {**pooled.result(), **coverage_fields(coverage_all)}
    if events is not None:
        summary.update(contingency_fields(events_all))
    return {"leads": list(view.leads), "by_lead": by_lead, "pooled": summary, "interval": view.interval,
            "period": {**view.period(), "cells": cells, "scored": pooled.n}}


def compare_views(view, other):
    """Score ``view`` and ``other`` on the cells both predict, using ``view``'s observations."""
    other_index = other.index()
    width = view.width
    model = [Acc() for _ in range(width)]
    base = [Acc() for _ in range(width)]
    model_all, base_all = Acc(), Acc()
    mismatched = 0
    for key, j, prediction, _low, _high, observed in view.cells():
        if observed is None:
            continue
        match = other_index.get(key)
        if match is None:
            continue
        reference, other_observed = match
        if other_observed is not None and not obs_close(observed, other_observed):
            mismatched += 1
            continue
        model[j].add(observed, prediction)
        base[j].add(observed, reference)
        model_all.add(observed, prediction)
        base_all.add(observed, reference)
    by_lead = [pair_fields(view.leads[j], model[j], base[j]) for j in range(width) if model[j].n]
    beating = sum(1 for row in by_lead if row["skill"] is not None and row["skill"] > 0)
    return {"by_lead": by_lead, "pooled": pair_fields(None, model_all, base_all),
            "leads_better": beating, "leads_compared": len(by_lead), "observation_mismatches": mismatched}


def same_sample(members, reference_id, threshold=None, roles=None):
    """Score cohort members on the issue/lead cells that all of them predict.

    Models and baselines define the shared sample. Reference, diagnostic and rejected
    members join the table only when they cover all of it, so they never shrink it.
    """
    if not members:
        return None
    roles = roles or {}
    if reference_id not in members:
        reference_id = max(members, key=lambda name: sum(1 for value in members[name].index().values()
                                                          if value[1] is not None))
    reference_obs = {key: observed for key, (_p, observed) in members[reference_id].index().items()
                     if observed is not None}
    if not reference_obs:
        return None
    core = {name for name in members if roles.get(name, "model") in ("model", "baseline")} or set(members)
    keysets, excluded = {}, []
    for name, view in members.items():
        keys = set()
        for key, (_prediction, observed) in view.index().items():
            truth = reference_obs.get(key)
            if truth is not None and observed is not None and obs_close(truth, observed):
                keys.add(key)
        keysets[name] = keys
    included = []
    common = set(reference_obs)
    for name in members:
        if name not in core:
            continue
        cover = len(keysets[name]) / len(reference_obs)
        if cover < COMMON_SAMPLE_MIN_COVER:
            excluded.append({"model": name, "coverage": rnd(cover, 4),
                             "reason": f"Predicts {cover:.0%} of the reference sample, so it is scored on its own sample instead."})
            continue
        included.append(name)
        common &= keysets[name]
    for name in members:
        if name in core:
            continue
        cover = len(keysets[name] & common) / len(common) if common else 0
        if cover < 0.999:
            excluded.append({"model": name, "coverage": rnd(cover, 4),
                             "reason": f"Covers {cover:.0%} of the shared sample, so it is scored on its own sample instead."})
            continue
        included.append(name)
    if not included or not common:
        return None
    included = [(name, members[name].index(), keysets[name]) for name in included]
    leads = sorted({key % LEAD_FACTOR for key in common})
    lead_pos = {lead: j for j, lead in enumerate(leads)}
    ordered = sorted(common)
    accumulators = {}
    for name, index, _keys in included:
        per_lead = [Acc() for _ in leads]
        pooled = Acc()
        events = [[0, 0, 0, 0] for _ in leads] if threshold is not None else None
        events_all = [0, 0, 0, 0]
        for key in ordered:
            observed = reference_obs[key]
            prediction = index[key][0]
            j = lead_pos[key % LEAD_FACTOR]
            per_lead[j].add(observed, prediction)
            pooled.add(observed, prediction)
            if events is not None:
                happened, warned = observed > threshold, prediction > threshold
                slot = 0 if happened and warned else 1 if happened else 2 if warned else 3
                events[j][slot] += 1
                events_all[slot] += 1
        accumulators[name] = (per_lead, pooled, events, events_all)
    reference_acc = accumulators.get(reference_id)
    rows = []
    for name, (per_lead, pooled, events, events_all) in accumulators.items():
        by_lead = []
        for j, lead in enumerate(leads):
            row = {"lead": lead, **per_lead[j].result()}
            if reference_acc and reference_acc[0][j].n:
                row["skill"] = pair_fields(None, per_lead[j], reference_acc[0][j])["skill"]
            if events is not None:
                row.update(contingency_fields(events[j]))
            by_lead.append(row)
        summary = pooled.result()
        if reference_acc:
            summary["skill"] = pair_fields(None, pooled, reference_acc[1])["skill"]
        if events is not None:
            summary.update(contingency_fields(events_all))
        rows.append({"model": name, "by_lead": by_lead, "pooled": summary})
    issues = sorted({key // LEAD_FACTOR for key in common})
    return {"reference": reference_id, "cells": len(common), "issues": len(issues),
            "first_issue": date.fromordinal(issues[0]).isoformat() if issues else None,
            "last_issue": date.fromordinal(issues[-1]).isoformat() if issues else None,
            "leads": leads, "excluded": excluded, "rows": rows}


# --------------------------------------------------------------------------- products

def build_peaks(spec, workspace, warnings):
    files = {name: workspace / spec[name] for name in ("model", "training", "test")}
    missing = [relative(path, workspace) for path in files.values() if not path.is_file()]
    if missing:
        return None, [], f"Missing: {', '.join(missing)}"
    model = read_json(files["model"], {})
    fit = model.get("model", {})
    features = fit.get("features", [])
    coefficients = fit.get("coefficients", [])
    means, stds = fit.get("feature_mean", []), fit.get("feature_std", [])
    sigma = fit.get("sigma_log")

    def predict(row):
        try:
            mu = coefficients[0] + sum(coefficients[k + 1] * (float(row[name]) - means[k]) / stds[k]
                                       for k, name in enumerate(features))
        except (KeyError, ValueError, IndexError, TypeError, ZeroDivisionError):
            return None, None, None
        return math.exp(mu), math.exp(mu - Z90 * sigma), math.exp(mu + Z90 * sigma)

    training = []
    with open_text(files["training"]) as handle:
        for row in csv.DictReader(handle):
            median, low, high = predict(row) if sigma else (None, None, None)
            training.append({"year": int(row["year"]), "storm_end": row.get("storm_end"),
                             "p3_mm": rnd(num(row.get("p3_mm")), 2), "peak": rnd(num(row.get("peak_m3s")), 1),
                             "censored": str(row.get("censored", "")).strip().lower() == "true",
                             "fit_median": rnd(median, 1), "fit_p10": rnd(low, 1), "fit_p90": rnd(high, 1)})
    test = []
    with open_text(files["test"]) as handle:
        for row in csv.DictReader(handle):
            test.append({"year": int(row["year"]), "storm_end": row.get("storm_end"), "p3_mm": rnd(num(row.get("p3_mm")), 2),
                         "obs_daily_max": rnd(num(row.get("obs_daily_max_m3s")), 1), "obs_days": int(num(row.get("obs_days")) or 0),
                         "pred_median": rnd(num(row.get("pred_median_m3s")), 1), "pred_p10": rnd(num(row.get("pred_p10_m3s")), 1),
                         "pred_p90": rnd(num(row.get("pred_p90_m3s")), 1),
                         "p_high": rnd(num(row.get("p_exceed_high_200k_cusecs")), 4),
                         "p_very_high": rnd(num(row.get("p_exceed_very_high_400k_cusecs")), 4),
                         "p_exceptional": rnd(num(row.get("p_exceed_exceptional_600k_cusecs")), 4),
                         "tft_max_p50": rnd(num(row.get("tft_climate_conditioned_max_p50_m3s")), 1)})
    selection = [{"features": name, "loo_log_score": rnd(values.get("loo_mean_log_score"), 4),
                  "loo_brier_400k": rnd(values.get("loo_brier_400k"), 4)}
                 for name, values in (model.get("selection") or {}).items()]
    chosen = (model.get("selection") or {}).get(model.get("selected_features"), {})
    reference = (model.get("selection") or {}).get("no_predictor", {})
    product = {"title": spec.get("title", "Annual flood-peak model"), "station": spec.get("station", "marala"),
               "docs": spec.get("docs"), "docs_title": markdown_title(workspace / spec["docs"]) if spec.get("docs") else None,
               "selected_features": model.get("selected_features"), "selection": selection,
               "coefficients": coefficients, "sigma_log": sigma, "features": features,
               "thresholds_m3s": model.get("thresholds_m3s", {}), "censor_m3s": model.get("censor_m3s"),
               "n_train_years": model.get("n_train_years"), "n_censored": model.get("n_censored"),
               "assumption": model.get("assumption"),
               "headline": {"loo_log_score": rnd(chosen.get("loo_mean_log_score"), 4),
                            "loo_log_score_reference": rnd(reference.get("loo_mean_log_score"), 4),
                            "loo_brier_400k": rnd(chosen.get("loo_brier_400k"), 4),
                            "loo_brier_400k_reference": rnd(reference.get("loo_brier_400k"), 4)},
               "training": training, "test": test,
               "note": "Fitted medians for 1980-2016 are in-sample, from the saved coefficients. Leave-one-year-out scores are from the model's own report."}
    return product, [files[name] for name in ("model", "training", "test")], None


def build_projections(spec, workspace, warnings):
    paths = {name: workspace / spec[name] for name in ("period_statistics", "change", "daily_quantiles")}
    missing = [relative(path, workspace) for path in paths.values() if not path.is_file()]
    if missing:
        return None, [], f"Missing: {', '.join(missing)}"

    def spread(values):
        values = [value for value in values if value is not None]
        if not values:
            return None
        return {"median": rnd(statistics.median(values), 4), "min": rnd(min(values), 4), "max": rnd(max(values), 4),
                "n": len(values)}

    annual = defaultdict(lambda: [0.0, 0])        # (gcm, experiment, year) -> sum, count of daily P50
    monthly = defaultdict(lambda: [0.0, 0])       # (gcm, experiment, period, month) -> sum, count
    with open_text(paths["daily_quantiles"]) as handle:
        reader = csv.reader(handle)
        header = next(reader)
        position = {name: i for i, name in enumerate(header)}
        i_date, i_p50, i_gcm, i_exp = position["date"], position["p50_m3s"], position["gcm"], position["experiment"]
        for row in reader:
            value = num(row[i_p50])
            if value is None:
                continue
            day = row[i_date]
            year, month = int(day[:4]), int(day[5:7])
            gcm, experiment = row[i_gcm], row[i_exp]
            cell = annual[(gcm, experiment, year)]
            cell[0] += value
            cell[1] += 1
            if experiment in ("historical", "reference") and 1986 <= year <= 2014:
                period = "1986-2014"
            elif experiment.startswith("ssp") and 2026 <= year <= 2040:
                period = "2026-2040"
            else:
                period = None
            if period:
                cell = monthly[(gcm, experiment, period, month)]
                cell[0] += value
                cell[1] += 1
    experiments = sorted({key[1] for key in annual})
    gcms = sorted({key[0] for key in annual if key[1] != "reference"})
    annual_series = {}
    for experiment in experiments:
        years = sorted({key[2] for key in annual if key[1] == experiment and annual[key][1] >= 360})
        if experiment.startswith("ssp"):
            years = [year for year in years if year >= 2026]
        rows = []
        for year in years:
            values = [annual[(gcm, experiment, year)][0] / annual[(gcm, experiment, year)][1]
                      for gcm in sorted({key[0] for key in annual if key[1] == experiment})
                      if annual.get((gcm, experiment, year), [0, 0])[1] >= 360]
            stats = spread(values)
            if stats:
                rows.append({"year": year, **{k: rnd(v, 1) if k != "n" else v for k, v in stats.items()}})
        annual_series[experiment] = rows
    cycle = {}
    for experiment in experiments:
        period = "1986-2014" if experiment in ("historical", "reference") else "2026-2040"
        months = []
        for month in range(1, 13):
            values = [monthly[(gcm, experiment, period, month)][0] / monthly[(gcm, experiment, period, month)][1]
                      for gcm in sorted({key[0] for key in monthly if key[1] == experiment})
                      if monthly.get((gcm, experiment, period, month), [0, 0])[1]]
            stats = spread(values)
            months.append({"month": month, **({k: rnd(v, 1) if k != "n" else v for k, v in stats.items()} if stats else {})})
        cycle[experiment] = {"period": period, "months": months}

    with open_text(paths["period_statistics"]) as handle:
        statistics_rows = list(csv.DictReader(handle))
    metric_names = [name for name in (statistics_rows[0].keys() if statistics_rows else [])
                    if name not in ("gcm", "experiment", "period")]
    periods = []
    for experiment, period in sorted({(row["experiment"], row["period"]) for row in statistics_rows}):
        rows = [row for row in statistics_rows if row["experiment"] == experiment and row["period"] == period]
        periods.append({"experiment": experiment, "period": period, "gcms": len(rows),
                        "metrics": {name: spread([num(row.get(name)) for row in rows]) for name in metric_names}})
    with open_text(paths["change"]) as handle:
        change_rows = list(csv.DictReader(handle))
    change_names = [name for name in (change_rows[0].keys() if change_rows else [])
                    if name not in ("gcm", "experiment", "period")]
    changes = []
    for experiment, period in sorted({(row["experiment"], row["period"]) for row in change_rows}):
        rows = [row for row in change_rows if row["experiment"] == experiment and row["period"] == period]
        changes.append({"experiment": experiment, "period": period,
                        "metrics": {name: spread([num(row.get(name)) for row in rows]) for name in change_names},
                        "by_gcm": [{"gcm": row["gcm"], **{name: rnd(num(row.get(name)), 3) for name in change_names}}
                                   for row in sorted(rows, key=lambda r: r["gcm"])]})
    product = {"title": spec.get("title", "Climate projections"), "station": spec.get("station", "marala"),
               "docs": spec.get("docs"), "docs_title": markdown_title(workspace / spec["docs"]) if spec.get("docs") else None,
               "gcms": gcms, "experiments": experiments, "annual_mean_flow": annual_series, "monthly_cycle": cycle,
               "periods": periods, "changes": changes,
               "note": "Annual and monthly flows are means of the daily calibrated P50 from the projection-mode TFT; the band is the range across GCMs."}
    return product, list(paths.values()), None


def read_calibration(spec, workspace):
    path = workspace / spec["file"]
    if not path.is_file():
        return None
    rows = {}
    with open_text(path) as handle:
        for row in csv.DictReader(handle):
            if row.get("mode") != spec.get("mode") or row.get("model") != spec.get("model"):
                continue
            method = row.get("method", "")
            rows.setdefault(method, []).append({
                "subset": row.get("subset"), "n": int(num(row.get("n")) or 0),
                "coverage_raw": rnd(num(row.get("coverage_raw")), 4),
                "coverage_calibrated": rnd(num(row.get("coverage_calibrated")), 4),
                "below_p10": rnd(num(row.get("below_p10_calibrated")), 4),
                "above_p90": rnd(num(row.get("above_p90_calibrated")), 4),
                "width_raw": rnd(num(row.get("median_width_raw_m3s")), 1),
                "width_calibrated": rnd(num(row.get("median_width_calibrated_m3s")), 1)})
    if not rows:
        return None
    return {"file": spec["file"], "nominal": 0.8, "methods": rows}


def read_importance(path_text, workspace):
    data = read_json(workspace / path_text)
    if not isinstance(data, dict):
        return None
    result = {}
    for part in ("encoder", "decoder", "static"):
        values = data.get(part)
        if isinstance(values, dict):
            result[part] = sorted(({"variable": name, "weight": rnd(float(weight), 4)} for name, weight in values.items()
                                   if isinstance(weight, (int, float))), key=lambda item: -item["weight"])
    return {"file": path_text, **result} if result else None


# --------------------------------------------------------------------------- registry

class Registry:
    def __init__(self, catalog, workspace, stations, warnings):
        self.catalog = catalog
        self.workspace = workspace
        self.stations = stations
        self.warnings = warnings
        self.cohorts = {cohort["id"]: dict(cohort) for cohort in catalog.get("cohorts", [])}
        self.models = []
        self.watch_files = set()

    def add(self, spec, origin):
        cohort = self.cohorts.get(spec["cohorts"][0]) if spec.get("cohorts") else None
        spec = dict(spec)
        spec.setdefault("station", (cohort or {}).get("station", "marala"))
        spec.setdefault("range", (cohort or {}).get("range", "short"))
        spec.setdefault("role", "model")
        spec.setdefault("kind", "daily")
        spec.setdefault("tags", [])
        spec["origin"] = origin
        self.models.append(spec)

    def runs(self, spec):
        """Return the model's runs, oldest first: [{'label', 'file'}]."""
        source = spec["source"]
        names = source["file"] if isinstance(source.get("file"), list) else [source.get("file")]
        if "runs" in source:
            root = self.workspace / source["runs"]
            runs = []
            if root.is_dir():
                for folder in root.iterdir():
                    if not folder.is_dir() or RUN_EXCLUDE.search(folder.name):
                        continue
                    for name in names:
                        candidate = folder / name
                        if candidate.is_file():
                            runs.append({"label": folder.name, "file": candidate})
                            break

            def order(run):
                label = run["label"]
                if label.lower() == "initial":
                    return (0, "", 0.0)
                if DATED_RUN.match(label):
                    return (1, label, 0.0)
                return (2, "", run["file"].stat().st_mtime)

            return sorted(runs, key=order)
        path = self.workspace / source["file"]
        if not path.is_file():
            return []
        stamp = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).date().isoformat()
        return [{"label": f"{stamp} run", "file": path}]


def cached_values(path, column, filters, value_cache, workspace):
    """Distinct values of a model column, re-read only when the file changes."""
    key = relative(path, workspace)
    signature = file_signature(path)
    cached = value_cache.get(key, {})
    if (cached.get("bytes") == signature["bytes"] and cached.get("mtime_ns") == signature["mtime_ns"]
            and cached.get("column") == column and cached.get("filters") == (filters or {})):
        return cached["values"]
    values = sorted(scan_values(path, column, filters))
    value_cache[key] = {**signature, "column": column, "filters": filters or {}, "values": values}
    return values


def discover(registry, catalog, value_cache):
    workspace = registry.workspace
    claimed_runs = set()
    claimed_files = set()
    for spec in registry.models:
        source = spec["source"]
        names = source["file"] if isinstance(source.get("file"), list) else [source.get("file")]
        if "runs" in source:
            for name in names:
                claimed_runs.add(((workspace / source["runs"]).resolve(), name))
        else:
            claimed_files.add((workspace / source["file"]).resolve())
    for rule in catalog.get("discovery", []):
        root = workspace / rule["root"]
        if not root.is_dir():
            continue
        wanted = set(rule.get("files", []))
        horizon_pattern = re.compile(rule.get("horizon_pattern", r"(\d+)[ _-]?days?"))
        found = defaultdict(list)
        for directory, subdirectories, filenames in os.walk(root):
            subdirectories[:] = [name for name in subdirectories if name not in WALK_PRUNE and not name.startswith(".")]
            current = Path(directory)
            if current.parent.name != "reports" or RUN_EXCLUDE.search(current.name):
                continue
            for name in filenames:
                if name in wanted:
                    found[(current.parent.parent, name)].append(current / name)
        for (model_dir, name), files in sorted(found.items(), key=lambda item: (str(item[0][0]), item[0][1])):
            reports = (model_dir / "reports").resolve()
            if (reports, name) in claimed_runs or any(path.resolve() in claimed_files for path in files):
                continue
            latest = max(files, key=lambda path: path.stat().st_mtime)
            for path in files:
                registry.watch_files.add(path)
            try:
                header, first = sniff_header(latest)
            except (OSError, UnicodeError, csv.Error) as error:
                registry.warnings.append(f"Skipped discovered predictions {relative(latest, workspace)}: {error}")
                continue
            roles = {role: next((c for c in candidates if c in header), None) for role, candidates in COLUMN_CANDIDATES.items()}
            if not roles["issue"] or not roles["lead"] or not roles["observed"]:
                registry.warnings.append(f"Skipped discovered predictions {relative(latest, workspace)}: no issue date, lead or observed column.")
                continue
            used = {value for value in roles.values() if value}
            station = rule.get("default_station", "marala")
            if "basin_id" in header and first and len(first) > header.index("basin_id"):
                candidate = slug(first[header.index("basin_id")].strip().lower())
                station = candidate if candidate in registry.stations else station
            rel_dir = relative(model_dir, workspace)
            match = horizon_pattern.search(rel_dir)
            horizon = match.group(1) if match else None
            cohort_id = rule.get("cohort_by_horizon", {}).get(horizon) if horizon else None
            if not cohort_id or registry.cohorts.get(cohort_id, {}).get("station") != station:
                cohort_id = f"auto.{station}.{rule.get('range', 'short')}.{horizon or 'other'}"
                if cohort_id not in registry.cohorts:
                    registry.cohorts[cohort_id] = {
                        "id": cohort_id, "range": rule.get("range", "short"), "station": station,
                        "title": f"{horizon}-day forecasts" if horizon else "Other forecasts",
                        "period": "Discovered automatically", "description": "Models found under the discovery root without a curated cohort.",
                        "default_baseline": None, "baselines": [], "headline_lead": int(horizon) if horizon else None,
                        "flood_threshold": None, "origin": "discovered"}
            title = markdown_title(model_dir / "README.md") or model_dir.name.replace("_", " ").replace("-", " ")
            role = "baseline" if re.search(r"climatolog|persistence", model_dir.name, re.IGNORECASE) else "model"
            base = {"station": station, "range": rule.get("range", "short"), "cohorts": [cohort_id], "role": role,
                    "family": "Discovered", "docs": relative(model_dir / "README.md", workspace) if (model_dir / "README.md").is_file() else None,
                    "source": {"runs": relative(model_dir / "reports", workspace), "file": name}}
            if "p50" in header:
                columns = {"point": "p50", "low": "p10" if "p10" in header else None, "high": "p90" if "p90" in header else None}
                columns = {key: value for key, value in columns.items() if value}
                points = [("p50", columns, [0.1, 0.9] if "low" in columns else None)]
            else:
                points = []
                for column in header:
                    if column in used or column in NON_PREDICTION_COLUMNS or META_COLUMN.search(column) or QUANTILE_COLUMN.search(column):
                        continue
                    columns = {"point": column}
                    for low, high, interval in INTERVAL_PAIRS:
                        for prefix in (f"{column}_", ""):
                            if prefix + low in header and prefix + high in header:
                                columns.update(low=prefix + low, high=prefix + high)
                                break
                        if "low" in columns:
                            points.append((column, columns, interval))
                            break
                    else:
                        points.append((column, columns, None))
            if not points:
                registry.warnings.append(f"Skipped discovered predictions {relative(latest, workspace)}: no prediction column recognised.")
                continue
            model_values = [None]
            if "model" in header:
                model_values = cached_values(latest, "model", {}, value_cache, workspace)
            for column, columns, interval in points:
                for value in model_values:
                    suffix = "" if len(points) == 1 else f".{slug(column)}"
                    suffix += "" if value is None else f".{slug(value)}"
                    name_suffix = "" if len(points) == 1 else f" · {column}"
                    name_suffix += "" if value is None else f" · {value}"
                    spec = {**base, "id": f"auto.{slug(rel_dir.replace('/', '.'))}{'.' + slug(Path(name).stem) if name not in ('predictions.csv', 'model_predictions.csv') else ''}{suffix}",
                            "name": f"{title}{name_suffix}", "columns": columns, "interval": interval,
                            "description": f"Found automatically in {rel_dir}. Add it to model_catalog.json to give it a curated name and description."}
                    if value is not None:
                        spec["filter"] = {"model": value}
                    registry.add(spec, "discovered")


def register_column_models(registry, catalog, value_cache):
    """Models that appear as new values in a multi-model file's model column."""
    workspace = registry.workspace
    for source in catalog.get("multi_model_sources", []):
        path = workspace / source["file"]
        if not path.is_file():
            continue
        registry.watch_files.add(path)
        column = source.get("model_column", "model")
        values = cached_values(path, column, source.get("filter"), value_cache, workspace)
        cohorts = source.get("cohorts") or [source["cohort"]]
        known = {spec.get("filter", {}).get(column) for spec in registry.models
                 if spec["source"].get("file") == source["file"]}
        for value in values:
            if value in known:
                continue
            registry.add({"id": f"auto.{cohorts[0]}.{slug(value)}", "name": value.replace("_", " "), "cohorts": cohorts,
                          "role": source.get("role", "model"), "family": source.get("family", "Discovered"),
                          "description": f"New '{value}' rows found in {source['file']}. Add it to model_catalog.json to give it a curated name.",
                          "docs": None, "source": {"file": source["file"]},
                          "filter": {**source.get("filter", {}), column: value},
                          "columns": source.get("columns", {}), "interval": source.get("interval")}, "source column")


def watched_files(catalog_path=CATALOG, workspace=WORKSPACE):
    """Files whose change should trigger a model rebuild (cheap enough to poll every few seconds)."""
    catalog = read_json(catalog_path, {})
    files = {Path(catalog_path)}
    for spec in catalog.get("models", []):
        source = spec.get("source", {})
        names = source.get("file") if isinstance(source.get("file"), list) else [source.get("file")]
        if "runs" in source:
            root = workspace / source["runs"]
            if root.is_dir():
                for folder in root.iterdir():
                    if folder.is_dir():
                        files.update(folder / name for name in names if name and (folder / name).is_file())
                files.add(root)
        elif source.get("file"):
            files.add(workspace / source["file"])
        for extra in ("importance",):
            if spec.get(extra):
                files.add(workspace / spec[extra])
        if spec.get("calibration", {}).get("file"):
            files.add(workspace / spec["calibration"]["file"])
    for source in catalog.get("multi_model_sources", []):
        files.add(workspace / source["file"])
    for product in (catalog.get("products") or {}).values():
        for key, value in product.items():
            if key not in ("title", "station", "docs") and isinstance(value, str):
                files.add(workspace / value)
    for rule in catalog.get("discovery", []):
        root = workspace / rule["root"]
        wanted = set(rule.get("files", []))
        for directory, subdirectories, filenames in os.walk(root):
            subdirectories[:] = [name for name in subdirectories if name not in WALK_PRUNE and not name.startswith(".")]
            current = Path(directory)
            if current.name == "reports":
                files.add(current)
            if current.parent.name == "reports":
                files.update(current / name for name in filenames if name in wanted)
    return files


def watch_fingerprint(catalog_path=CATALOG, workspace=WORKSPACE):
    values = []
    for path in sorted(watched_files(catalog_path, workspace), key=str):
        try:
            stat = path.stat()
        except OSError:
            values.append((str(path), None, None))
            continue
        values.append((str(path), stat.st_size if path.is_file() else -1, stat.st_mtime_ns))
    return tuple(values)


# --------------------------------------------------------------------------- build

def detail_path(dist, model_id, sha):
    return dist / "data" / "models" / slug(model_id) / f"{sha[:16]}.json"


def version_summary(scores, comparison, baseline_id, headline_lead):
    pooled = scores["pooled"]
    summary = {key: pooled.get(key) for key in ("n", "rmse", "mae", "nse", "kge", "pbias", "cov", "hit_rate", "far", "csi")
               if pooled.get(key) is not None}
    if comparison:
        summary.update(skill=comparison["pooled"].get("skill"), skill_n=comparison["pooled"].get("n"),
                       baseline=baseline_id, leads_better=comparison["leads_better"], leads_compared=comparison["leads_compared"])
    if headline_lead is not None:
        row = next((row for row in scores["by_lead"] if row["lead"] == headline_lead), None)
        if row:
            summary["headline_lead"] = {key: row.get(key) for key in ("lead", "n", "rmse", "nse", "kge", "pbias")}
    by_lead = []
    skills = {row["lead"]: row.get("skill") for row in (comparison or {}).get("by_lead", [])}
    for row in scores["by_lead"]:
        by_lead.append({"lead": row["lead"], "n": row["n"], "rmse": row.get("rmse"), "nse": row.get("nse"),
                        "kge": row.get("kge"), "pbias": row.get("pbias"), "skill": skills.get(row["lead"])})
    return summary, by_lead


def version_delta(new_view, old_view):
    comparison = compare_views(new_view, old_view)
    pooled = comparison["pooled"]
    if not pooled["n"] or pooled.get("rmse_base") in (None, 0):
        return {"n": pooled["n"], "verdict": "not comparable",
                "note": "The two versions share no scored issue dates and leads."}
    change = pooled["rmse"] / pooled["rmse_base"] - 1
    verdict = "improved" if change < -VERSION_CHANGE_TOL else "regressed" if change > VERSION_CHANGE_TOL else "unchanged"
    return {"n": pooled["n"], "rmse_previous": pooled["rmse_base"], "rmse": pooled["rmse"], "rmse_change_pct": rnd(100 * change, 3),
            "nse_previous": pooled.get("nse_base"), "nse": pooled.get("nse"), "kge_previous": pooled.get("kge_base"),
            "kge": pooled.get("kge"), "leads_better": comparison["leads_better"], "leads_compared": comparison["leads_compared"],
            "verdict": verdict}


def build_models(dist=DIST, catalog_path=CATALOG, workspace=WORKSPACE, stations=None, now=None, log=print, force=False):
    """Score every registered model and write models.json, the version ledger and compact predictions."""
    dist, workspace, catalog_path = Path(dist), Path(workspace), Path(catalog_path)
    started = now or utc_now()
    stations = dict(stations or {"marala": "Chenab · Marala"})
    data_dir = dist / "data"
    models_path = data_dir / "models.json"
    ledger_path = data_dir / "model_versions.json"
    catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    ids = [spec["id"] for spec in catalog.get("models", [])]
    duplicates = sorted({value for value in ids if ids.count(value) > 1})
    if duplicates:
        raise ValueError(f"Duplicate model ids in {catalog_path.name}: {', '.join(duplicates)}")
    known_cohorts = {cohort["id"] for cohort in catalog.get("cohorts", [])}
    for spec in catalog.get("models", []):
        unknown = [cohort for cohort in spec.get("cohorts", []) if cohort not in known_cohorts]
        if unknown or not spec.get("cohorts"):
            raise ValueError(f"Model {spec['id']} must name known cohorts (got {spec.get('cohorts')})")

    ledger = read_json(ledger_path, {}) or {}
    ledger.setdefault("schema_version", 1)
    ledger.setdefault("models", {})
    ledger.setdefault("products", {})
    source_cache = ledger.setdefault("source_index", {})
    value_cache = ledger.setdefault("value_index", {})
    previous = read_json(models_path, {}) or {}
    warnings = []

    registry = Registry(catalog, workspace, stations, warnings)
    for spec in catalog.get("models", []):
        registry.add(spec, "catalog")
    register_column_models(registry, catalog, value_cache)
    discover(registry, catalog, value_cache)

    # Runs per model and the files they come from.
    runs_by_model = {}
    all_files = set()
    for spec in registry.models:
        runs = registry.runs(spec)
        runs_by_model[spec["id"]] = runs
        all_files.update(run["file"] for run in runs)
    for spec in registry.models:
        for key in ("importance",):
            if spec.get(key) and (workspace / spec[key]).is_file():
                all_files.add(workspace / spec[key])
        if spec.get("calibration", {}).get("file") and (workspace / spec["calibration"]["file"]).is_file():
            all_files.add(workspace / spec["calibration"]["file"])
    product_files = []
    for product in (catalog.get("products") or {}).values():
        for key, value in product.items():
            if key not in ("title", "station", "docs") and isinstance(value, str) and (workspace / value).is_file():
                product_files.append(workspace / value)
    all_files.update(product_files)

    build_key = sha256_text(canonical({
        "scoring": SCORING_VERSION, "detail": DETAIL_FORMAT, "engine": sha256_file(Path(__file__)),
        "catalog": sha256_file(catalog_path), "stations": stations,
        "models": sorted(spec["id"] for spec in registry.models),
        "files": sorted((relative(path, workspace), *file_signature(path).values()) for path in all_files)}))
    details_present = all((dist / version["detail"]).is_file()
                          for model in previous.get("models", []) for version in model.get("versions", [])
                          if model.get("current") == version.get("version") and version.get("detail"))
    if not force and previous.get("build_key") == build_key and details_present and ledger_path.is_file():
        summary = dict(previous.get("summary", {}))
        summary.update(reused=True, sha256=sha256_file(models_path))
        return summary

    # Parse each source file once for every extractor that is not already cached.
    jobs = defaultdict(list)   # file -> [(model_id, run, extractor)]
    for spec in registry.models:
        for run in runs_by_model[spec["id"]]:
            extractor = Extractor(spec["id"], spec.get("columns"), spec.get("filter"), spec.get("interval"), spec.get("kind"))
            jobs[run["file"]].append((spec["id"], run, extractor))
    compacts = {}              # sha -> compact (only those parsed or loaded this build)
    run_results = {}           # (model_id, label) -> {"sha", "stats", ...}
    for path, items in jobs.items():
        key = relative(path, workspace)
        signature = file_signature(path)
        cached = source_cache.get(key) or {}
        same_file = cached.get("bytes") == signature["bytes"] and cached.get("mtime_ns") == signature["mtime_ns"]
        if not same_file:
            cached = {**signature, "extractors": {}}
        extractor_cache = cached.setdefault("extractors", {})
        pending = []
        for model_id, run, extractor in items:
            hit = extractor_cache.get(f"{model_id}|{extractor.signature()}")
            if same_file and hit and detail_path(dist, model_id, hit["sha"]).is_file():
                run_results[(model_id, run["label"])] = {"sha": hit["sha"], "stats": hit.get("stats", {}), "file": path}
            else:
                pending.append((model_id, run, extractor))
        if pending:
            log(f"Scoring source {key} ({len(pending)} model{'s' if len(pending) != 1 else ''})")
            try:
                parse_file(path, [extractor for _, _, extractor in pending])
            except (OSError, UnicodeError, csv.Error, EOFError, gzip.BadGzipFile) as error:
                for model_id, run, extractor in pending:
                    extractor.error = f"Could not read {key}: {error}"
            for model_id, run, extractor in pending:
                if extractor.error:
                    run_results[(model_id, run["label"])] = {"error": extractor.error, "file": path}
                    warnings.append(f"{model_id}: {extractor.error}")
                    continue
                built = extractor.compact()
                if built is None:
                    message = f"No rows matched in {key}"
                    run_results[(model_id, run["label"])] = {"error": message, "file": path}
                    warnings.append(f"{model_id}: {message}")
                    continue
                compact, stats = built
                sha = sha256_text(canonical(compact))
                compacts[sha] = compact
                target = detail_path(dist, model_id, sha)
                if not target.is_file():
                    write_json(target, {"format": DETAIL_FORMAT, "model": model_id, "sha": sha, **compact})
                extractor_cache[f"{model_id}|{extractor.signature()}"] = {"sha": sha, "stats": stats}
                run_results[(model_id, run["label"])] = {"sha": sha, "stats": stats, "file": path}
        cached.update(signature)
        source_cache[key] = cached

    def view_for(model_id, sha):
        compact = compacts.get(sha)
        if compact is None:
            document = read_json(detail_path(dist, model_id, sha))
            if not document:
                return None
            compact = {key: value for key, value in document.items() if key not in ("format", "model", "sha")}
            compacts[sha] = compact
        return View(compact)

    # Version ledger.
    changes = []
    current = {}               # model_id -> ledger version entry
    stamp = iso(started)
    for spec in registry.models:
        model_id = spec["id"]
        entry = ledger["models"].setdefault(model_id, {"versions": []})
        entry["name"] = spec["name"]
        for run in runs_by_model[model_id]:
            result = run_results.get((model_id, run["label"]))
            if not result or "sha" not in result:
                continue
            sha = result["sha"]
            version = next((item for item in entry["versions"] if item["sha"] == sha), None)
            if version is None:
                version = {"version": len(entry["versions"]) + 1, "sha": sha, "run": run["label"],
                           "evaluated_utc": iso_from_timestamp(run["file"].stat().st_mtime), "detected_utc": stamp,
                           "files": [{"path": relative(run["file"], workspace), **file_signature(run["file"])}],
                           "stats": result.get("stats", {}), "scoring_version": None}
                entry["versions"].append(version)
                changes.append({"model": model_id, "name": spec["name"], "version": version["version"], "run": run["label"]})
            version["detail"] = relative(detail_path(dist, model_id, sha), dist)
            current[model_id] = version
    # Cohort membership (catalog cohorts plus discovered ones).
    members = defaultdict(list)
    for spec in registry.models:
        for cohort_id in spec.get("cohorts", []):
            members[cohort_id].append(spec["id"])
    specs = {spec["id"]: spec for spec in registry.models}
    for cohort in registry.cohorts.values():
        if cohort.get("origin") == "discovered" and not cohort.get("default_baseline"):
            baselines = [model_id for model_id in members[cohort["id"]] if specs[model_id]["role"] == "baseline"]
            cohort["baselines"] = baselines
            cohort["default_baseline"] = baselines[0] if baselines else None

    previous_models = {model["id"]: model for model in previous.get("models", [])}
    views = {}

    def current_view(model_id):
        if model_id not in views:
            version = current.get(model_id)
            views[model_id] = view_for(model_id, version["sha"]) if version else None
        return views[model_id]

    # Scores for current versions; reuse when nothing that feeds them changed.
    model_rows = []
    for spec in registry.models:
        model_id = spec["id"]
        cohort = registry.cohorts.get(spec["cohorts"][0], {})
        threshold = (cohort.get("flood_threshold") or {}).get("value")
        baselines = [base for base in cohort.get("baselines", []) if base != model_id and base in current]
        version = current.get(model_id)
        status, message, scores = "ok", None, None
        if version is None:
            errors = [result.get("error") for (mid, _), result in run_results.items() if mid == model_id and result.get("error")]
            status = "error" if errors else "missing"
            message = errors[0] if errors else "No prediction files found for this model."
            fallback = previous_models.get(model_id, {})
            scores = fallback.get("scores")
            known = ledger["models"].get(model_id, {}).get("versions", [])
            if known:
                version = known[-1]
        else:
            scores_key = sha256_text(canonical({"scoring": SCORING_VERSION, "sha": version["sha"], "threshold": threshold,
                                                "baselines": [(base, current[base]["sha"]) for base in baselines]}))
            old = previous_models.get(model_id, {})
            if old.get("scores_key") == scores_key and old.get("scores"):
                scores = old["scores"]
            else:
                view = current_view(model_id)
                if view is None:
                    status, message = "error", "Compact predictions are missing; run the build with force=True."
                else:
                    scores = score_view(view, threshold)
                    scores["skill"] = {}
                    for base in baselines:
                        other = current_view(base)
                        if other is not None:
                            scores["skill"][base] = compare_views(view, other)
            if scores is not None:
                scores["key"] = scores_key
        model_rows.append((spec, version, status, message, scores))

    # Version summaries for versions first seen in this build (or scored with an older method).
    for spec in registry.models:
        model_id = spec["id"]
        entry = ledger["models"].get(model_id)
        if not entry:
            continue
        cohort = registry.cohorts.get(spec["cohorts"][0], {})
        threshold = (cohort.get("flood_threshold") or {}).get("value")
        baseline_id = cohort.get("default_baseline") if cohort.get("default_baseline") != model_id else None
        for position, version in enumerate(entry["versions"]):
            if version.get("scoring_version") == SCORING_VERSION:
                continue
            view = view_for(model_id, version["sha"])
            if view is None:
                continue
            if current.get(model_id) is version:
                row = next(item for item in model_rows if item[0]["id"] == model_id)
                scores = row[4]
            else:
                scores = score_view(view, threshold)
            if not scores:
                continue
            comparison = None
            if baseline_id and baseline_id in current:
                comparison = (scores or {}).get("skill", {}).get(baseline_id) if current.get(model_id) is version else None
                if comparison is None:
                    other = current_view(baseline_id)
                    comparison = compare_views(view, other) if other is not None else None
            summary, by_lead = version_summary(scores, comparison, baseline_id, cohort.get("headline_lead"))
            version.update(summary=summary, by_lead=by_lead, scoring_version=SCORING_VERSION)
            if position > 0 and "delta_vs_previous" not in version:
                before = view_for(model_id, entry["versions"][position - 1]["sha"])
                version["delta_vs_previous"] = version_delta(view, before) if before is not None else {
                    "verdict": "not comparable", "note": "The previous version's compact predictions are not available."}

    # Cohort tables on one shared sample.
    cohort_rows = []
    previous_cohorts = {cohort["id"]: cohort for cohort in previous.get("cohorts", [])}
    for cohort_id, cohort in registry.cohorts.items():
        member_ids = [model_id for model_id in members.get(cohort_id, []) if model_id in current]
        threshold = (cohort.get("flood_threshold") or {}).get("value")
        key = sha256_text(canonical({"scoring": SCORING_VERSION, "threshold": threshold, "reference": cohort.get("default_baseline"),
                                     "members": sorted((model_id, current[model_id]["sha"], specs[model_id]["role"])
                                                       for model_id in member_ids)}))
        old = previous_cohorts.get(cohort_id, {})
        if old.get("same_sample_key") == key and "same_sample" in old:
            table = old["same_sample"]
        else:
            loaded = {model_id: current_view(model_id) for model_id in member_ids}
            loaded = {model_id: view for model_id, view in loaded.items() if view is not None}
            table = same_sample(loaded, cohort.get("default_baseline"), threshold,
                                {model_id: specs[model_id]["role"] for model_id in loaded}) if loaded else None
        cohort_rows.append({**{k: v for k, v in cohort.items() if k != "origin"}, "origin": cohort.get("origin", "catalog"),
                            "members": members.get(cohort_id, []), "same_sample_key": key, "same_sample": table})
        if cohort.get("range") == "long":
            views.clear()       # long-range views are large; release them between cohorts

    # Products: flood peaks and projections, versioned by file content.
    products = {}
    for name, spec in (catalog.get("products") or {}).items():
        builder = {"peaks": build_peaks, "projections": build_projections}.get(name)
        if builder is None:
            continue
        try:
            product, files, problem = builder(spec, workspace, warnings)
        except (OSError, ValueError, KeyError, csv.Error, gzip.BadGzipFile) as error:
            product, files, problem = None, [], str(error)
        entry = ledger["products"].setdefault(name, {"versions": []})
        if product is None:
            warnings.append(f"Product {name}: {problem}")
            products[name] = {"title": spec.get("title"), "status": "missing", "message": problem,
                              "versions": entry["versions"]}
            continue
        content = sha256_text(canonical([sha256_file(path) for path in files]))
        version = next((item for item in entry["versions"] if item["sha"] == content), None)
        if version is None:
            version = {"version": len(entry["versions"]) + 1, "sha": content, "detected_utc": stamp,
                       "evaluated_utc": iso_from_timestamp(max(path.stat().st_mtime for path in files)),
                       "files": [{"path": relative(path, workspace), **file_signature(path)} for path in files]}
            entry["versions"].append(version)
            changes.append({"model": f"product.{name}", "name": spec.get("title", name), "version": version["version"], "run": None})
        products[name] = {**product, "status": "ok", "current": version["version"], "versions": entry["versions"]}

    # Assemble models.json.
    station_counts = defaultdict(int)
    models_out = []
    for spec, version, status, message, scores in model_rows:
        model_id = spec["id"]
        station_counts[spec["station"]] += 1
        versions = []
        for item in ledger["models"].get(model_id, {}).get("versions", []):
            item = dict(item)
            if not item.get("detail") or not (dist / item["detail"]).is_file():
                item["detail"] = None
            item.pop("stats", None)
            versions.append(item)
        calibration = read_calibration(spec["calibration"], workspace) if spec.get("calibration") else None
        importance = read_importance(spec["importance"], workspace) if spec.get("importance") else None
        docs = spec.get("docs")
        models_out.append({
            "id": model_id, "name": spec["name"], "station": spec["station"], "range": spec["range"],
            "cohorts": spec.get("cohorts", []), "role": spec["role"], "tags": spec.get("tags", []),
            "family": spec.get("family"), "description": spec.get("description"), "kind": spec.get("kind", "daily"),
            "docs": docs, "docs_title": markdown_title(workspace / docs) if docs else None, "origin": spec["origin"],
            "status": status, "message": message, "interval": (scores or {}).get("interval"),
            "current": version["version"] if version else None,
            "current_files": version.get("files", []) if version else [],
            "versions": versions, "scores_key": (scores or {}).get("key"), "scores": scores,
            "calibration": calibration, "importance": importance,
            "run_stats": (current.get(model_id) or {}).get("stats", {})})
    ranges = catalog.get("ranges", {})
    station_rows = [{"id": station_id, "name": name, "models": station_counts.get(station_id, 0)}
                    for station_id, name in stations.items()]
    for station_id in station_counts:
        if station_id not in stations:
            station_rows.append({"id": station_id, "name": station_id.replace("_", " ").title(), "models": station_counts[station_id]})
    version_total = sum(len(entry.get("versions", [])) for entry in ledger["models"].values())
    summary = {"built_utc": stamp, "models": len(models_out), "versions": version_total, "changes": changes,
               "warnings": len(warnings), "reused": False}
    result = {"schema_version": 1, "scoring_version": SCORING_VERSION, "built_utc": stamp, "build_key": build_key,
              "ranges": ranges, "stations": station_rows, "cohorts": cohort_rows, "models": models_out,
              "products": products, "unscored": catalog.get("unscored", []), "warnings": warnings,
              "changes": changes, "summary": summary}
    ledger["updated_utc"] = stamp
    ledger["scoring_version"] = SCORING_VERSION
    write_json(ledger_path, ledger, indent=1)
    write_json(models_path, result)
    summary = {**summary, "sha256": sha256_file(models_path)}
    prune_details(dist, ledger)
    log(f"Models: {len(models_out)} scored, {version_total} versions, {len(changes)} new or changed, {len(warnings)} warnings")
    return summary


def prune_details(dist, ledger):
    """Remove compact prediction files no ledger version refers to."""
    root = dist / "data" / "models"
    if not root.is_dir():
        return
    keep = set()
    for model_id, entry in ledger.get("models", {}).items():
        for version in entry.get("versions", []):
            keep.add(detail_path(dist, model_id, version["sha"]).resolve())
    for path in root.rglob("*.json"):
        if path.resolve() not in keep:
            path.unlink()
    for folder in sorted((p for p in root.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
        if not any(folder.iterdir()):
            folder.rmdir()


def patch_manifest(summary, dist=DIST):
    """Record a models-only rebuild in the portal manifest so open pages reload model data."""
    path = Path(dist) / "data" / "build_report.json"
    manifest = read_json(path, {}) or {}
    manifest["models"] = {key: summary.get(key) for key in ("built_utc", "sha256", "models", "versions", "changes", "warnings")}
    write_json(path, manifest, indent=2)
    return manifest


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--force", action="store_true", help="Rescore everything even when no input changed")
    arguments = parser.parse_args()
    result = build_models(force=arguments.force)
    if not result.get("reused"):
        patch_manifest(result)
    print(json.dumps({key: result.get(key) for key in ("built_utc", "models", "versions", "warnings", "reused")}))
