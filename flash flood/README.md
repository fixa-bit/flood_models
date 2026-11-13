# Flash flood

Flash-flood work, kept apart from the riverine models.

| Path | What it is |
|---|---|
| [short range/model](short%20range/model/README.md) | First Pakistan flash-flood model: the chance of a reported flood onset in each 20 km cell over the next 24 hours, scored for all of Pakistan and the Chenab districts |
| [short range/dataset](short%20range/dataset/README.md) | The 20 km grid, Groundsource news-derived flood labels, IMERG rainfall, ERA5-Land state, terrain and land cover, with collectors and receipts |
| `long range/dataset/` | Empty; no long-range flash-flood work yet |
| `.venv/` (ignored) | Python 3.11 environment for this module |

Create the environment with:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install numpy pandas pyarrow shapely pyproj scikit-learn lightgbm earthengine-api matplotlib pytest
```
