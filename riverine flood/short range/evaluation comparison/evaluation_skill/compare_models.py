"""Compare flood/non-flood classification and discharge errors from forecast CSVs."""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path

KEYS = ["target_date", "lead_day"]
PROTECTED = {
    "basin_id", "issue_date", "target_date", "lead_day", "season", "observed_cumecs",
    "q0.05", "q0.25", "q0.5", "q0.75", "q0.95",
}


def parse_prediction(spec: str, requested_column: str | None, lead_day: int) -> tuple[str, dict]:
    if "=" not in spec:
        raise ValueError(f"Expected MODEL_NAME=CSV_PATH, got: {spec}")
    name, raw_path = spec.split("=", 1)
    column = requested_column
    records = {}
    with Path(raw_path).open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = reader.fieldnames or []
        missing = set(KEYS + ["observed_cumecs"]) - set(fields)
        if missing:
            raise ValueError(f"{raw_path} missing columns: {sorted(missing)}")
        for row in reader:
            if int(row["lead_day"]) != lead_day:
                continue
            if column is None:
                candidates = []
                for field in fields:
                    if field in PROTECTED:
                        continue
                    try:
                        float(row[field])
                    except (TypeError, ValueError):
                        continue
                    candidates.append(field)
                candidates = sorted(set(candidates))
                if len(candidates) != 1:
                    raise ValueError(
                        f"{raw_path}: expected one prediction column after excluding metadata/quantiles; "
                        f"found {candidates}. Use --prediction-column."
                    )
                column = candidates[0]
            if column not in fields:
                raise ValueError(f"{raw_path} has no prediction column {column!r}")
            key = (row.get("basin_id", ""), row["target_date"], row["lead_day"])
            if key in records:
                raise ValueError(f"{raw_path} has duplicate target/lead key: {key}")
            try:
                observed, predicted = float(row["observed_cumecs"]), float(row[column])
            except (TypeError, ValueError):
                observed, predicted = math.nan, math.nan
            records[key] = (observed, predicted)
    return name, records


def make_report(predictions: list[tuple[str, dict]], threshold: float, lead_day: int) -> str:
    if not predictions:
        raise ValueError("Provide at least one prediction CSV")
    names = [name for name, _ in predictions]
    common_keys = set.intersection(*(set(rows) for _, rows in predictions))
    aligned = []
    for key in sorted(common_keys):
        values = [rows[key] for _, rows in predictions]
        observed_values = [v[0] for v in values]
        predicted_values = [v[1] for v in values]
        if not all(math.isfinite(v) for v in observed_values + predicted_values):
            continue
        if any(not math.isclose(observed_values[0], value, rel_tol=1e-9, abs_tol=1e-8) for value in observed_values[1:]):
            raise ValueError("Models disagree on observed flow values for aligned cases")
        aligned.append((observed_values[0], predicted_values))
    if not aligned:
        raise ValueError("No common observed cases remain after date/lead alignment")
    observed = [item[0] for item in aligned]
    actual_flood = [value >= threshold for value in observed]
    n_flood = sum(actual_flood)
    n_nonflood = len(actual_flood) - n_flood
    if not n_flood or not n_nonflood:
        raise ValueError("Common test cases must contain at least one flood and one non-flood day")

    lines = [
        f"# Lead-{lead_day} flood/non-flood model comparison", "",
        f"- Flood threshold: **{threshold:g} m3/s** (must be training-derived).",
        f"- Common observed cases: **{len(observed)}** ({n_flood} flood, {n_nonflood} non-flood).",
        "- Flood means observed flow at or above the threshold. Accuracy uses both classes; class precision/recall/F1 are computed one-vs-rest.",
        "", "| Model | Actual class | n | Accuracy | Precision | Recall | F1 | RMSE (m3/s) | MAE (m3/s) |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for model_idx, (name, _) in enumerate(predictions):
        predicted = [item[1][model_idx] >= threshold for item in aligned]
        tp = sum(a and p for a, p in zip(actual_flood, predicted))
        fp = sum((not a) and p for a, p in zip(actual_flood, predicted))
        tn = sum((not a) and (not p) for a, p in zip(actual_flood, predicted))
        fn = sum(a and (not p) for a, p in zip(actual_flood, predicted))
        accuracy = (tp + tn) / len(actual_flood)
        for label, mask in [
            ("Flood", True),
            ("Non-flood", False),
        ]:
            class_mask = [actual == mask for actual in actual_flood]
            class_obs = [obs for obs, keep in zip(observed, class_mask) if keep]
            class_pred = [values[model_idx] for (_, values), keep in zip(aligned, class_mask) if keep]
            if mask:
                tp_class, fp_class, fn_class = tp, fp, fn
            else:
                tp_class, fp_class, fn_class = tn, fn, fp
            precision = tp_class / (tp_class + fp_class) if tp_class + fp_class else 0.0
            recall = tp_class / (tp_class + fn_class) if tp_class + fn_class else 0.0
            f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
            rmse = math.sqrt(sum((obs - pred) ** 2 for obs, pred in zip(class_obs, class_pred)) / len(class_obs))
            mae = sum(abs(obs - pred) for obs, pred in zip(class_obs, class_pred)) / len(class_obs)
            lines.append(
                f"| {name} | {label} | {len(class_obs)} | {accuracy:.3f} | {precision:.3f} | "
                f"{recall:.3f} | {f1:.3f} | {rmse:.1f} | {mae:.1f} |"
            )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--predictions", nargs="+", required=True, help="MODEL_NAME=prediction.csv entries")
    parser.add_argument("--lead-day", type=int, required=True)
    parser.add_argument("--flood-threshold", type=float, required=True, help="Training-derived discharge threshold")
    parser.add_argument("--prediction-column", help="Use this prediction column for every supplied CSV")
    parser.add_argument("--output", type=Path, required=True, help="Markdown report path")
    args = parser.parse_args()
    loaded = [parse_prediction(spec, args.prediction_column, args.lead_day) for spec in args.predictions]
    report = make_report(loaded, args.flood_threshold, args.lead_day)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(report, encoding="utf-8")
    print(report)
    print(f"Saved: {args.output}")


if __name__ == "__main__":
    main()
