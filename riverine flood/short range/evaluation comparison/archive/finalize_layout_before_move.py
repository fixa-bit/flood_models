"""Finish the model-folder layout without touching trained weights or source discharge."""
from __future__ import annotations

import ast
import json
import shutil
from pathlib import Path

import pandas as pd
import yaml


ROOT = Path(__file__).resolve().parents[1]
COMMON = ROOT / "evaluation comparison" / "common"


def yaml_read(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8-sig"))


def yaml_write(path: Path, value: dict) -> None:
    path.write_text(yaml.safe_dump(value, sort_keys=False), encoding="utf-8")


def copy_if_missing(source: Path, target: Path) -> None:
    if source.exists() and not target.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)


def bootstrap(path: Path) -> None:
    """Make the relocated common loaders importable from a model entry point."""
    source = path.read_text(encoding="utf-8-sig")
    marker = "# Model workspace import path."
    if marker in source:
        return
    tree = ast.parse(source)
    position = 0
    for node in tree.body:
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str):
            position = node.end_lineno
        elif isinstance(node, ast.ImportFrom) and node.module == "__future__":
            position = node.end_lineno
        else:
            break
    lines = source.splitlines(keepends=True)
    block = (
        "# Model workspace import path.\n"
        "import sys as _layout_sys\n"
        "from pathlib import Path as _LayoutPath\n"
        "for _layout_parent in _LayoutPath(__file__).resolve().parents:\n"
        "    if (_layout_parent / 'evaluation comparison' / 'common').is_dir():\n"
        "        _layout_sys.path.insert(0, str(_layout_parent))\n"
        "        _layout_sys.path.insert(0, str(_layout_parent / 'evaluation comparison' / 'common'))\n"
        "        break\n\n"
    )
    path.write_text("".join(lines[:position]) + block + "".join(lines[position:]), encoding="utf-8")


# Keep all historical configurations in place. Active copies point to the local run.
base = yaml_read(COMMON / "config.yaml")
base["data"]["daily_file"] = "data/marala_daily.csv"
for name in ("lstm", "gradient_boosting", "persistence", "climatology", "ensemble"):
    local = ROOT / name
    copy_if_missing(COMMON / "data/marala_daily.csv", local / "data/marala_daily.csv")
    copy_if_missing(COMMON / "data/marala_daily.provenance.json", local / "data/marala_daily.provenance.json")
    cfg = json.loads(json.dumps(base))
    cfg["training"]["output_dir"] = "runs/initial"
    cfg["finetuning"]["output_dir"] = "runs/finetuned"
    cfg["baselines"]["output_dirs"] = {key: f"../{key}/runs/initial" for key in ("persistence", "climatology", "gradient_boosting")}
    cfg["ensemble"]["output_dir"] = "runs/initial" if name == "ensemble" else "../ensemble/runs/initial"
    cfg["evaluation"]["output_dir"] = "../evaluation comparison/initial_lstm_baselines"
    cfg["evaluation"]["model_output_dirs"] = {key: f"../{key.lower() if key == 'LSTM' else key}/reports/initial" for key in ("LSTM", "persistence", "climatology", "gradient_boosting")}
    yaml_write(local / "config.yaml", cfg)

base["training"]["output_dir"] = "../../lstm/runs/initial"
base["finetuning"]["output_dir"] = "../../lstm/runs/finetuned"
base["baselines"]["output_dirs"] = {key: f"../../{key}/runs/initial" for key in ("persistence", "climatology", "gradient_boosting")}
base["ensemble"]["output_dir"] = "../../ensemble/runs/initial"
base["evaluation"]["output_dir"] = "../initial_lstm_baselines"
base["evaluation"]["model_output_dirs"] = {key: f"../../{key.lower() if key == 'LSTM' else key}/reports/initial" for key in ("LSTM", "persistence", "climatology", "gradient_boosting")}
yaml_write(COMMON / "config.yaml", base)

pretrain_variants = {
    "pretrained_multibasin_lstm": ("config_pretrain.yaml", "pretrain"),
    "pretrained_multibasin_lstm_finetuned": ("config_marala.yaml", "finetune"),
    "lstm_two_input_scratch": ("config_scratch.yaml", "scratch"),
}
for name, (source, stage) in pretrain_variants.items():
    local = ROOT / name
    cfg = yaml_read(local / source)
    cfg["training"]["output_dir"] = "runs/initial"
    cfg["finetuning"]["output_dir"] = "runs/initial" if stage == "finetune" else "runs/finetuned"
    cfg["variant_stage"] = stage
    cfg["pretrained_checkpoint"] = "../pretrained_multibasin_lstm/runs/initial/seed_42/best.pt" if stage == "finetune" else None
    yaml_write(local / "config.yaml", cfg)
    workflow = yaml_read(local / "workflow.yaml")
    workflow["sources"]["marala_source"] = "../evaluation comparison/common/data/marala_daily.csv"
    workflow["evaluation"]["output_dir"] = f"../evaluation comparison/pretrained_multibasin_lstm"
    workflow["evaluation"]["original_config"] = "../lstm/config.yaml"
    workflow["evaluation"]["original_checkpoint"] = "../lstm/runs/initial/seed_42/best.pt"
    workflow["variant_stage"] = stage
    workflow["variant_config"] = "config.yaml"
    workflow["pretrained_checkpoint"] = "../pretrained_multibasin_lstm/runs/initial/seed_42/best.pt" if stage == "finetune" else None
    yaml_write(local / "workflow.yaml", workflow)

for name, stage in (("spatially_distributed_model", "spatial"), ("catchment_mean_lstm", "mean_control")):
    local = ROOT / name
    cfg = yaml_read(local / ("config.yaml" if stage == "spatial" else "config_mean_control.yaml"))
    cfg["training"]["output_dir"] = "runs/initial"
    cfg["spatial"]["control_config"] = "../catchment_mean_lstm/config.yaml"
    cfg["evaluation"]["output_dir"] = "../evaluation comparison/spatially_distributed_model"
    cfg["variant_stage"] = stage
    yaml_write(local / "config.yaml", cfg)

for name, stage in (("encoder_decoder_lstm", "scratch"), ("encoder_decoder_lstm_finetuned", "finetuned")):
    local = ROOT / name
    cfg = yaml_read(local / "config.yaml")
    cfg["training"]["output_dir"] = "runs/initial"
    cfg["finetuning"]["output_dir"] = "runs/initial" if stage == "finetuned" else "runs/finetuned"
    cfg["experiment"]["source_daily_file"] = "../evaluation comparison/common/data/marala_daily.csv"
    cfg["experiment"]["source_pretrained_checkpoint"] = "../pretrained_multibasin_lstm/runs/initial/seed_42/best.pt"
    cfg["experiment"]["report_dir"] = "../evaluation comparison/encoder_decoder_lstm"
    cfg["variant_stage"] = stage
    yaml_write(local / "config.yaml", cfg)

matched = ROOT / "lstm_past_discharge_weather"
matched_cfg = yaml_read(matched / "config.yaml")
matched_cfg["training"]["output_dir"] = "runs/initial"
matched_cfg["prior_comparison"] = "../evaluation comparison/N-HiTS_N-BEATSx/scores_flood_nonflood_by_lead.csv"
yaml_write(matched / "config.yaml", matched_cfg)

# Use the code copied into each variant folder rather than importing a sibling.
for name, old in (("pretrained_multibasin_lstm_finetuned", "pretrained_multibasin_lstm"),
                  ("lstm_two_input_scratch", "pretrained_multibasin_lstm"),
                  ("catchment_mean_lstm", "spatially_distributed_model"),
                  ("encoder_decoder_lstm_finetuned", "encoder_decoder_lstm")):
    for path in (ROOT / name).glob("*.py"):
        source = path.read_text(encoding="utf-8-sig")
        source = source.replace(f"from {old}.", f"from {name}.")
        source = source.replace(f"import {old}.", f"import {name}.")
        path.write_text(source, encoding="utf-8")

# Pick a single model stage when an entry point is run without an explicit stage.
for name, (_, stage) in pretrain_variants.items():
    path = ROOT / name / "train.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace("with_name('config.yaml'))\n    parser.add_argument('--stage'", "with_name('workflow.yaml'))\n    parser.add_argument('--stage'")
    source = source.replace("default='all')", f"default='{stage}')")
    source = source.replace("parent = args.checkpoint or state.get('pretrain') if stage == 'finetune' else None",
                            "parent = (args.checkpoint or str((cfg['_root'] / cfg['pretrained_checkpoint']).resolve()) or state.get('pretrain')) if stage == 'finetune' else None")
    source = source.replace("config = load_config(cfg['_root'] / cfg['stages'][key])", "config = load_config(cfg['_root'] / (cfg['variant_config'] if stage == cfg.get('variant_stage') else cfg['stages'][key]))")
    path.write_text(source, encoding="utf-8")

for name, stage in (("spatially_distributed_model", "spatial"), ("catchment_mean_lstm", "mean_control")):
    path = ROOT / name / "train.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace("default='all')", f"default='{stage}')")
    source = source.replace("cfg = main_cfg if stage == 'spatial' else load_spatial_config(resolve(main_cfg, main_cfg['spatial']['control_config']))",
                            "cfg = main_cfg if stage == main_cfg.get('variant_stage') else load_spatial_config(resolve(main_cfg, main_cfg['spatial']['control_config']))")
    path.write_text(source, encoding="utf-8")

for name, stage in (("encoder_decoder_lstm", "scratch"), ("encoder_decoder_lstm_finetuned", "finetuned")):
    path = ROOT / name / "train.py"
    source = path.read_text(encoding="utf-8")
    source = source.replace('for stage, initial in [("finetuned", adapted_path), ("scratch", None)]:',
                            'for stage, initial in [("finetuned", adapted_path), ("scratch", None)]:\n        if stage != cfg.get("variant_stage"):\n            continue')
    path.write_text(source, encoding="utf-8")

for name in ("pretrained_multibasin_lstm", "pretrained_multibasin_lstm_finetuned", "lstm_two_input_scratch"):
    for filename in ("evaluate.py", "prepare_data.py"):
        path = ROOT / name / filename
        source = path.read_text(encoding="utf-8-sig")
        source = source.replace("with_name('config.yaml')", "with_name('workflow.yaml')")
        path.write_text(source, encoding="utf-8")

# The matched LSTM was formerly nested below N-HiTS. Its report now stays local.
path = matched / "_nhits" / "evaluate.py"
source = path.read_text(encoding="utf-8")
source = source.replace("('README.md' if name != 'Matched_LSTM' else 'controls/lstm/README.md')", "'README.md'")
source = source.replace("('RUN_RESULTS.md' if name != 'Matched_LSTM' else 'controls/lstm/RUN_RESULTS.md')", "'RUN_RESULTS.md'")
path.write_text(source, encoding="utf-8")

# Scripts for the original shared pipeline and its model-specific entry points.
for path in list(COMMON.glob("*.py")) + list((ROOT / "lstm").glob("*.py")):
    bootstrap(path)
for name in ("pretrained_multibasin_lstm", "pretrained_multibasin_lstm_finetuned", "lstm_two_input_scratch", "spatially_distributed_model", "catchment_mean_lstm", "encoder_decoder_lstm", "encoder_decoder_lstm_finetuned", "hybrid_physics_ml", "fine_tuned_global_pretrained_lstm"):
    for path in (ROOT / name).glob("*.py"):
        bootstrap(path)

comparison = ROOT / "evaluation comparison"
for source_name, target_name, label in (
    ("finetuned", "pretrained_multibasin_lstm_finetuned", "finetuned"),
    ("scratch", "lstm_two_input_scratch", "scratch"),
    ("pretrained_only", "pretrained_multibasin_lstm", "pretrained_only"),
):
    source = comparison / "pretrained_multibasin_lstm" / source_name
    target = ROOT / target_name / "reports/initial"
    for file in source.glob("*.csv"):
        copy_if_missing(file, target / file.name)


def filter_csv(source: Path, target: Path, column: str, value: str) -> None:
    if not source.exists():
        return
    frame = pd.read_csv(source)
    if column not in frame:
        return
    selected = frame.loc[frame[column].astype(str).eq(value)]
    if selected.empty:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    selected.to_csv(target, index=False)


comparison_sets = (
    ("spatially_distributed_model", "spatially_distributed_model", "ElevationBands"),
    ("spatially_distributed_model", "catchment_mean_lstm", "MeanControl"),
    ("encoder_decoder_lstm", "encoder_decoder_lstm", "scratch"),
    ("encoder_decoder_lstm", "encoder_decoder_lstm_finetuned", "finetuned"),
    ("global_pretrained_lstm", "fine_tuned_global_pretrained_lstm", "Global_finetuned"),
    ("hybrid_physics_ml", "hybrid_physics_ml", "Hybrid"),
)
for source_name, target_name, model in comparison_sets:
    source = comparison / source_name
    target = ROOT / target_name / "reports/initial"
    for file in source.glob("*.csv"):
        if file.name.startswith("scores") or file.name == "quantile_calibration.csv":
            filter_csv(file, target / file.name, "model", model)
    if (source / "predictions.csv").exists():
        frame = pd.read_csv(source / "predictions.csv")
        base_columns = [c for c in frame if c in ("issue_date", "target_date", "date", "lead_day", "basin_id", "observed_cumecs", "observed", "year", "season", "monsoon")]
        model_columns = [c for c in frame if c == model or c.startswith(model + "_")]
        if model_columns:
            target.mkdir(parents=True, exist_ok=True)
            frame[base_columns + model_columns].to_csv(target / "predictions.csv", index=False)
    elif (source / "predictions.csv.gz").exists():
        frame = pd.read_csv(source / "predictions.csv.gz")
        base_columns = [c for c in frame if c in ("issue_date", "target_date", "date", "lead_day", "basin_id", "observed_cumecs", "observed", "year", "season", "monsoon")]
        model_columns = [c for c in frame if c == model or c.startswith(model + "_")]
        if model_columns:
            target.mkdir(parents=True, exist_ok=True)
            frame[base_columns + model_columns].to_csv(target / "predictions.csv.gz", index=False, compression="gzip")

hbv_source = comparison / "hbv_residual_2026-10-30/reports"
for name, model in (("hbv_residual", "HBV"), ("hbv_lstm", "HBV_LSTM"), ("hbv_lightgbm", "HBV_LightGBM")):
    target = ROOT / name / "reports/2026-10-30"
    for file in hbv_source.glob("*.csv"):
        filter_csv(file, target / file.name, "model", model)
    file = hbv_source / "rolling_predictions.csv.gz"
    if file.exists():
        frame = pd.read_csv(file)
        if "model" in frame:
            selected = frame.loc[frame.model.eq(model)]
            if not selected.empty:
                target.mkdir(parents=True, exist_ok=True)
                selected.to_csv(target / file.name, index=False, compression="gzip")

grrr_source = comparison / "grrr_lstm/experiment"
for name, arm in (("grrr_lstm", "nan_gaps"), ("grrr_lstm_weighted_fills_rejected", "weighted_fills")):
    target = ROOT / name / "reports/initial"
    for file in ("scores.csv", "sampled_peak_scores.csv"):
        filter_csv(grrr_source / file, target / file, "arm", arm)
    predictions = grrr_source / "predictions_observed_days.csv"
    if predictions.exists():
        frame = pd.read_csv(predictions)
        base_columns = [c for c in frame if c in ("date", "issue_date", "target_date", "lead_day", "observed_m3_s", "observed_cumecs", "q_cumecs", "year", "season")]
        model_columns = [c for c in frame if arm in c]
        if model_columns:
            target.mkdir(parents=True, exist_ok=True)
            frame[base_columns + model_columns].to_csv(target / predictions.name, index=False)
copy_if_missing(grrr_source / "experimental_daily.csv", ROOT / "grrr_lstm_weighted_fills_rejected/data/experimental_daily.csv")

# Keep a one-page guide in each folder, retaining earlier detailed notes as archives.
descriptions = {
    "lstm": "Original 10-day hindcast-forecast LSTM",
    "gradient_boosting": "Gradient boosting baseline",
    "ensemble": "LSTM plus gradient boosting ensemble",
    "pretrained_multibasin_lstm": "Eight-basin CAMELS-US donor-pretrained LSTM",
    "pretrained_multibasin_lstm_finetuned": "CAMELS-US LSTM fine-tuned on Marala",
    "lstm_two_input_scratch": "Two-input scratch LSTM transfer control",
    "fine_tuned_global_pretrained_lstm": "Global Caravan-pretrained LSTM fine-tuned on Marala",
    "hybrid_physics_ml": "Snow and water bucket plus LSTM hybrid",
    "spatially_distributed_model": "Elevation-band spatial LSTM",
    "catchment_mean_lstm": "Catchment-mean spatial control",
    "encoder_decoder_lstm_finetuned": "15-day encoder-decoder LSTM fine-tuned",
    "encoder_decoder_lstm": "15-day encoder-decoder LSTM trained from scratch",
    "hbv_residual": "Calibrated physical HBV",
    "hbv_lstm": "HBV plus LSTM residual correction",
    "hbv_lightgbm": "HBV plus LightGBM residual correction",
    "discharge_history_lstm": "Discharge-history-only LSTM",
    "grrr_lstm": "LSTM with lagged GRRR inputs and discharge gaps retained",
    "grrr_lstm_weighted_fills_rejected": "Experimental low-weight GRRR-filled targets, rejected",
    "N-HiTS": "N-HiTS basis model",
    "N-BEATSx": "N-BEATSx weather-aware basis model",
    "lstm_past_discharge_weather": "Matched past-discharge and weather LSTM control",
    "persistence": "Persistence benchmark",
    "climatology": "Training-period day-of-year climatology benchmark",
}
old_readmes = comparison / "archive/original_readmes"
old_readmes.mkdir(parents=True, exist_ok=True)
for name, title in descriptions.items():
    folder = ROOT / name
    if not folder.is_dir():
        raise FileNotFoundError(folder)
    readme = folder / "README.md"
    old_readme = old_readmes / f"{name}.md"
    if readme.exists() and not old_readme.exists():
        shutil.copy2(readme, old_readme)
    elif not readme.exists() and (folder / "readme.md").exists() and not old_readme.exists():
        shutil.copy2(folder / "readme.md", old_readme)
    artifacts = []
    for pattern in ("runs/**/best.pt", "runs/**/model.pkl", "runs/**/nan_gaps.pt", "runs/**/physical/*.json", "runs/**/models/lightgbm/*"):
        artifacts.extend(p for p in folder.glob(pattern) if p.is_file())
    # Prefer selected/final artifacts over fold checkpoints.
    artifacts = sorted(set(artifacts), key=lambda p: ("final" not in p.parts and "initial" not in p.parts, len(p.parts), str(p)))
    report_candidates = sorted((folder / "reports").glob("**/scores_by_lead.csv")) if (folder / "reports").exists() else []
    report_candidates += sorted((folder / "reports").glob("**/scores.csv")) if (folder / "reports").exists() else []
    lines = [f"# {title}", "", f"Folder: `{name}/`", "", "## Trained artifact", ""]
    if name == "grrr_lstm_weighted_fills_rejected":
        lines.append("This variant was trained and evaluated, then rejected. Its checkpoint was removed in the original experiment; only the historical evaluation and experimental input table are retained.")
    elif artifacts:
        lines.extend(f"- `{p.relative_to(folder).as_posix()}`" for p in artifacts[:3])
    else:
        lines.append("See `runs/` for saved model states and training records.")
    lines.extend(["", "## Files", ""])
    for file in ("config.yaml", "config.json", "workflow.yaml", "train.py", "finetune.py", "evaluate.py", "model.py", "experiment.py"):
        if (folder / file).exists():
            lines.append(f"- `{file}`")
    if report_candidates:
        lines.extend(["", "## Own evaluation", ""])
        lines.extend(f"- `{p.relative_to(folder).as_posix()}`" for p in report_candidates[:3])
        try:
            frame = pd.read_csv(report_candidates[0])
            metric = next((x for x in ("NSE", "nse") if x in frame.columns), None)
            if metric and "lead_day" in frame:
                day = frame.loc[frame.lead_day.eq(10)]
                if "season" in day:
                    day = day.loc[day.season.eq("all")] if day.season.eq("all").any() else day
                if not day.empty:
                    lines.append(f"- Lead 10 {metric}: **{float(day.iloc[0][metric]):.3f}** on the recorded observed test days. See the CSV for sample count and other leads.")
        except (ValueError, KeyError, TypeError):
            pass
    lines.extend(["", "## Context", "", f"[Cross-model comparisons](../evaluation%20comparison/README.md) | [Original detailed notes](../evaluation%20comparison/archive/original_readmes/{name}.md)", "", "Saved evaluations use observed target days. Future reanalysis was used as a forecast stand-in in most LSTM experiments; these scores are not operational forecast accuracy.", ""])
    readme.write_text("\n".join(lines), encoding="utf-8")

index = ["# Marala short-range model folders", "", "Each trained variant has its own folder with its code, configuration, artifacts and own evaluation. Cross-model reports and shared utilities are in [evaluation comparison](evaluation%20comparison/README.md).", "", "| Model | Folder |", "|---|---|"]
for name, title in descriptions.items():
    index.append(f"| {title} | [{name}]({name}/README.md) |")
index += ["", "The experimental low-weight GRRR-filled run was rejected and has no retained checkpoint. No discharge observations or model weights were changed during this reorganization. Missing observed targets remain missing in the original data.", ""]
(ROOT / "README.md").write_text("\n".join(index), encoding="utf-8")
(comparison / "README.md").write_text("# Evaluation comparison\n\nCross-model reports, shared evaluation code and archived original layout files are kept here. Each model folder contains its own result subset and README.\n\n- `common/`: shared data loading, training and baseline code, plus the unchanged source daily table.\n- `flood_nonflood_2026-11-02_with_nhits_nbeatsx/`: consolidated observed-day flood and non-flood comparison.\n- `pretrained_multibasin_lstm/`, `spatially_distributed_model/`, `encoder_decoder_lstm/`, `global_pretrained_lstm/`, `hybrid_physics_ml/`, `hbv_residual_2026-10-30/`, `grrr_lstm/`: original cross-variant experiment reports.\n- `archive/`: original readmes, superseded shared experiment code and historical comparison copies.\n\nNo scores were recomputed by the folder reorganization; local CSVs are filtered copies of the saved comparisons.\n", encoding="utf-8")
print(f"Updated {len(descriptions)} model folders, local score subsets, and both indexes.")
