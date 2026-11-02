# Optional GloFAS comparison — not run

Reserved separately from the observed-only dataset and model. No local GloFAS discharge dataset was found; no modeled values have been fabricated or appended to observations.

When a station/reach-matched, versioned GloFAS series is available:

1. Save its original data, units, river reach selection, timestamps, provenance and checksums here.
2. Preserve every selected observed value. Only fill otherwise missing discharge dates; retain explicit `is_modeled` flags and the untouched observed target mask. Fit any bias correction on training-period paired observations only.
3. Train a second model with the same architecture, seed, chronological partitions and checkpoint selection policy. State explicitly whether modeled values enter inputs, targets or both. Save its data, checkpoint and results here.
4. Score both models on exactly the same observed test forecast-origin/target/lead combinations. Report any extra coverage from filling separately. Never evaluate modeled targets as ground truth.
5. Compare lead-specific errors, event peaks and false alarms on observed events. Define a meaningful improvement criterion on validation data before opening test results; use paired event/year uncertainty checks. Retain the GloFAS alternative only if improvement is clear and does not materially worsen flood-event behavior.

Historical/reanalysis GloFAS availability at forecast issue time must be checked before claiming operational skill. Future realized modeled flow must not enter forecast inputs.
