# Flood analysis workspace

Keep each model/module and its data in a separate subfolder.

- [Data portal](data_portal/README.md): source provenance, freshly recomputed local integrity checks, quality review, discharge and precipitation plots, and a catchment explorer for the flood-model datasets. Run `python data_portal/serve.py` for a refreshed local view at `http://127.0.0.1:8787`.
- [Preferred Marala rainfall](riverine%20flood/short%20range/dataset/chenab_marala/processed/marala/rainfall/chirps_v3_primary/README.md): CHIRPS v3 catchment precipitation from 1990 through the latest available 2026 Final and separate Preliminary dates.

- `exposure_infrastructure/`: population, OSM roads/buildings/facilities/settlements, administrative boundaries, preparation scripts and GIS audits.

## Start the local data portal

From the project root, run:

```powershell
python data_portal/serve.py
```

Open **http://127.0.0.1:8787** in your browser. Keep the terminal open while using the portal; press **Ctrl+C** to stop it. No login is required.

On Windows, you can also double-click [data_portal/start_portal.cmd](data_portal/start_portal.cmd).

## Exposure module and repository contents

The active exposure pilot is **Trimmu / Jhang**, configured in `exposure_infrastructure/configs/trimmu_jhang.json`. It uses the official Jhang district polygon and published UNOSAT historical water extents. Balloki's earlier provisional run is retained separately. Run the downloader, preprocessor, source verification and audit from the exposure module; Google Colab writes to Drive using the same configuration.

The workspace was empty on initial inspection. Future segmentation and river forecasting modules should have their own directories and environments. Link their georeferenced flood outputs through the exposure configuration rather than mixing raw datasets.

Git includes the Marala source snapshots, processed datasets, provenance and quality reports, collection scripts, plans, and local portal. Source files retain their exact bytes so checksum verification also works after cloning. Only the exposure/infrastructure datasets are excluded; that module's configurations, scripts and tests are included. Install Python dependencies from each module's requirements file on the new computer.




Models list:

Encoder-decoder LSTM (seq2seq)	7-15 days	Outputs the whole horizon at once

N-BEATS / N-HiTS	7-30 days	Strong on multi-step horizons

ConvLSTM / CNN-LSTM on gridded inputs	
CNN-LSTM / TCN	3-7 days	Good for gridded rainfall or radar inputs

Transformer / Informer / PatchTST	7-15 days	Needs a lot of data

Temporal Fusion Transformer	7-15 days	Uses known future inputs and gives interpretability

Mamba / state-space models	7+ days	Newer, used in RF-Bench

LightGBM / XGBoost / Random Forest	1-10 days (direct multi-horizon)	Fast, works with little data


Random forest / XGBoost	Tree ensembles	Same family as your LightGBM baseline, cheap to add



EA-LSTM (entity-aware)	Static attributes control the LSTM input gate	Pays off only when you add many basins



Temporal CNN (TCN) or N-HiTS	Convolutions or stacked MLPs over time, direct multi-horizon output	Fast and stable. Can be weaker on long snow memory


Transformer-based (TFT, PatchTST)	Attention over past and forecast inputs	Needs more data. Published streamflow results show no clear win over LSTMs, so treat it as an experiment


Hybrid physics-ML	A degree-day snow and bucket model feeds the LSTM, or a mass-conserving LSTM (MC-LSTM)	Often the best choice with little data, because physics gives structure and snow is dominant here




Hybrid:

HBV / SRM / HEC-HMS + ML residual correction	10-15 days	Easiest hybrid, works with short records

Model states as LSTM inputs	10-15 days	Snowpack and soil moisture fed to the AI


AI bias-correction of GloFAS or NWM output	7-30 days	Post-processing of an existing forecast



Residual correction	Run HBV/SRM, then train LightGBM or an LSTM to predict the error (observed minus simulated), using simulated flow, recent errors and forecast rain as inputs.	Little to medium	The easiest start, and it works well with short records.

Model states as AI features	Feed HBV/SRM internal states (snowpack, soil moisture, groundwater storage, simulated melt) into an LSTM or GRU along with forecast rainfall and temperature.	Medium	Giving the AI physically meaningful inputs, which reduces overfitting.


AI-corrected forcing	Use ML to bias-correct and downscale ECMWF or GFS rainfall and temperature, and to fill gaps in MODIS snow cover, before they enter HBV/SRM.	Medium	Fixing the weakest link, which is usually rainfall in mountain terrain.



Differentiable hybrids (δHBV, δ-models)	10 days or more	Neural network learns the physical parameters
Differentiable hybrid (e.g. δHBV)	A neural network learns HBV’s parameters from catchment attributes and weather, and the whole model is trained end-to-end, with HBV still enforcing mass balance.	Medium to large	The most accurate and transferable option, but the most work to build.



Pretrained fine tuning:

Global pretrained LSTM, fine-tuned per basin (closest fit)



ECMWF’s AIFL (new in 2026)




Open-source toolkit and data

NeuralHydrology is the library behind most of this work. 

You can train or fine-tune LSTMs with it, with or without pretrained weights.

Caravan is the open dataset of about 6,000+ basins with forcings and attributes. Use it to pretrain your own model if no weights fit.

FloodCast and the RF-Bench benchmark (Mamba and other deep models) are open-source research platforms, but they were built for large-scale flood modelling and hourly runoff, so they are less turnkey for Marala.




Physically based and conceptual models
Model	Typical max lead	Notes
GloFAS (LISFLOOD-based)	30 days	Free global ensemble, good benchmark
NOAA National Water Model	Up to 30 days	US only



Glofas improvement:

Bias correction / quantile mapping	Statistically adjust forecast flows against observed flows at your gauge	GloFAS, NWM
ML error correction (post-processing)	Train an LSTM or LightGBM to predict observed minus forecast, using the forecast, recent errors and season as inputs	GloFAS, NWM
GloFAS/NWM output as an input feature	Feed the model’s discharge forecast into your own LSTM along with local rainfall, snow cover and past flow	GloFAS, NWM
Ensemble post-processing	Use quantile regression forests, EMOS or a neural network to turn the raw ensemble into calibrated probabilities	GloFAS (ensemble)
Data assimilation with ML	Update the model state with the latest gauge observations, then forecast from the corrected state	Both, but needs model access
Forcing correction	Bias-correct or downscale the rainfall and temperature before they enter the model	Needs to run LISFLOOD or NWM yourself
Hybrid blending	Weight GloFAS, your HBV/SRM and your AI model by lead time and flow regime	Both



