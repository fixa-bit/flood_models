# Evaluation comparison

This folder lives beside `model/` under `short range/`. The [model index](../model/README.md) links to each trained variant.

Cross-model reports, shared evaluation code and archived original layout files are kept here. Each model folder contains its own result subset and README.

- `common/`: shared data loading, training and baseline code, plus the unchanged source daily table.
- `flood_nonflood_reorganized/`: verified, current consolidated observed-day flood and non-flood comparison.
- `delta_hbv/`: new differentiable HBV scores and matched comparison against the original LSTM, persistence and climatology.
- `flood_nonflood_with_delta_hbv/`: updated consolidated comparison including delta-HBV.
- `pretrained_multibasin_lstm/`, `spatially_distributed_model/`, `encoder_decoder_lstm/`, `global_pretrained_lstm/`, `hybrid_physics_ml/`, `hbv_residual_2026-10-30/`, `grrr_lstm/`: original cross-variant experiment reports.
- `archive/`: original readmes, superseded shared experiment code and historical comparison copies.

No scores were recomputed by the folder reorganization; local CSVs are filtered copies of the saved comparisons.

Models are now indexed in `model/model_10 days/` and `model/model_15 days/`; this comparison folder remains outside `model/`.

The new `model_30_days/` comparison subfolder holds comparisons for the sequential 30-day experiments. Their data and model artifacts are under `model/model_30_days/`. Its flood/non-flood Markdown and PDF tables now include the elevation-band spatial model, its catchment-mean control, and N-HiTS.
