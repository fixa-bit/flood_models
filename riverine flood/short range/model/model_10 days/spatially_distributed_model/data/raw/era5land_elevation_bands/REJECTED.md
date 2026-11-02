# Rejected extraction attempt

These initial exports contain missing weather values and zero band-coverage flags.
They failed source-quality checks and were never used for model training.

The active configuration uses the separate `era5land_elevation_bands_v2` directory,
with explicit fractional area weights, complete coverage and independent
catchment-aggregation checks. Do not use this directory as a model input.
