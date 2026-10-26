# Flood analysis workspace

Keep each model/module and its data in a separate subfolder.

- [Data portal](data_portal/README.md): source provenance, freshly recomputed local integrity checks, quality review, discharge and precipitation plots, and a catchment explorer for the flood-model datasets. Run `python data_portal/serve.py` for a refreshed local view at `http://127.0.0.1:8787`.

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
