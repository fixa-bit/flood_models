# Thirty-day experiment comparisons

- [Weather-only scratch LSTM](hindcast_forecast_lstm_scratch/comparison_report.md): first experiment against persistence and training-only climatology.
- [Adding past observed discharge](hindcast_forecast_lstm_past_discharge/variant_comparison.md): both LSTM variants on identical observed records, with matched weather and model settings.
- [Climatology-residual LSTM ensemble](climatology_residual_ensemble/comparison_report.md): day-30 NSE 0.858, compared with exact climatology 0.792 and smoothed climatology 0.820. Three seeds, mean-flow MSE objective, and validation-only postprocessing.
- [Fine-tuned 30-day encoder-decoder](encoder_decoder_finetuned_15_to_30/comparison_report.md): day-30 NSE 0.849 and RMSE 306.4 cumecs. It beats both climatology controls but has lower overall NSE than the current best ensemble; high-flow RMSE is lower and the false-alarm ratio is higher.

The past-discharge variant changed day-30 NSE from 0.784 to 0.788 and reduced high-flow RMSE by about 3%. It did not consistently improve shorter-lead scores. Day-30 climatology NSE remains slightly higher at 0.792. P05-P95 coverage changed from 74.5% to 76.8%, below the nominal 90%.

The first two variants use one seed each; the residual and encoder-decoder ensembles use three each. All use a previously inspected benchmark and noisy future reanalysis. Operational 30-day flood forecast accuracy is unverified. HBV, spatial and basis-model families remain pending.

The latest variant uses three sequential seeds. Its day-30 RMSE is 297.6 cumecs versus climatology 359.4. High-flow RMSE is 826.1 versus climatology 973.6. Empirically adjusted P05-P95 coverage is 90.6%, while high-flow hit rate is only 33%. All earlier variants are preserved.
