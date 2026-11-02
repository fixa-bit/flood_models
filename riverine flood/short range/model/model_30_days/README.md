# 30-day flood forecasting experiments

One model variant is trained and evaluated at a time, followed by feedback. Three hindcast-forecast variants and the fine-tuned 30-day encoder-decoder ensemble are complete. HBV, spatial and basis-model families remain pending.

| Order | Model family | Status |
|---:|---|---|
| 1 | [Hindcast-forecast LSTM, including pretrained variants](Hindcast-forecast%20LSTM/README.md) | trained and evaluated; awaiting user feedback |
| 2 | [Encoder-decoder LSTM](Encoder-decoder%20LSTM/README.md) | trained and evaluated; awaiting user feedback |
| 3 | [delta-HBV, physical HBV and HBV residual hybrids](HBV%20hybrids/README.md) | pending user feedback; not trained |
| 4 | [Spatial elevation-band LSTM](Spatial%20elevation-band%20LSTM/README.md) | pending user feedback; not trained |
| 5 | [N-HiTS](N-HiTS/README.md) | pending user feedback; not trained |
| 6 | [N-BEATSx](N-BEATSx/README.md) | pending user feedback; not trained |

The first experiment uses a reanalysis weather proxy because no archived 30-day weather forecasts were found. It cannot establish operational 30-day flood forecast accuracy.
