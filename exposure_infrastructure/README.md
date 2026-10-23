# Exposure & infrastructure datasets

This module is separate from flood segmentation and river forecasting. No models are trained here. The original `flood_model` folder was empty on inspection: no study polygons, verified administrative boundaries or flood masks were present.

## Active pilot: Trimmu / Jhang

The default configuration is now `configs/trimmu_jhang.json`, following the request to select a station with accessible data. Its exposure study boundary is the official OCHA COD-AB **Jhang district** polygon containing Trimmu. This is an explicit administrative exposure area, not a station upstream catchment. The prior Balloki run remains available under its own name and configuration.

All Trimmu processed layers, a pilot-specific manifest, summary, source verification, extraction log, audit and sample map live under `datasets/exposure/processed/trimmu_jhang/`. Balloki stays under `processed/balloki/`. National source files are a shared original cache; each pilot manifest records its own source versions and hashes, so changing the active provider does not change an older pilot's provenance. `scripts/run_pilot.py` runs preprocessing, tests, independent references and audit sequentially with durable logs and `validation_reports/pipeline_status.json` in the pilot folder. It expects the national originals to be downloaded first. Overpass remains a separate optional retry because public services are currently failing.

The configured HDX provider downloads a versioned original archive and preserves the earlier geoBoundaries originals and manifest history. The national release has 160 districts. Geometry was created on 2 September 2022, reviewed on 27 September 2024, and its downloadable resource updated on 14 August 2026. These dates have different meanings; the pipeline does not label it 2026 geometry. The original source attributes and PCodes are retained, with normalized `shapeName` and `shapeID` columns added to processed layers.

Run the independent source checks after preprocessing:

```powershell
.venv/Scripts/python scripts/verify_sources.py --config configs/trimmu_jhang.json
.venv/Scripts/python scripts/audit.py --config configs/trimmu_jhang.json
```

`verify_sources.py` acquires UNOSAT product 4197's dated VIIRS water extent, clips it to the district, and records geometry repairs while preserving the original ZIP. It also clips Microsoft's independent image-derived building detections to a separate `reference_buildings` layer and measures how many detections lack an OSM footprint within 10 metres. These detections are not field-verified, and tile upload dates do not establish imagery dates. The Overpass inventory check uses the PBF snapshot timestamp; it checks extraction/source inventory, not completeness in the real world. Service errors remain explicitly unverified. The results are in `validation_reports/trimmu_jhang_source_verification.json`.

The audit distinguishes **published flood reference alignment** from **model output alignment**. The historical reference can be checked now; the latter remains pending until georeferenced model outputs are supplied through `flood_extents`. Roads/facilities still need independent inventories for operational completeness. A source's age or a discovered mapping gap remains visible rather than being cleared cosmetically.

Sources: [OCHA/HDX COD-AB](https://data.humdata.org/dataset/cod-ab-pak), [Trimmu in Jhang](https://jhang.punjab.gov.pk/important-places), [UNOSAT 4197](https://unosat.org/products/4197), [Microsoft footprint dataset and license](https://github.com/microsoft/GlobalMLBuildingFootprints).

## Run locally

From `D:\Projects\flood_model\exposure_infrastructure`:

```powershell
python -m venv .venv
.venv/Scripts/python -m pip install -r requirements.txt
.venv/Scripts/python scripts/download.py
.venv/Scripts/python scripts/preprocess.py
.venv/Scripts/python scripts/verify_sources.py
.venv/Scripts/python scripts/audit.py
```

Each script accepts `--config configs/balloki.json` and `--root <persistent-storage-folder>`. `download.py --metadata-only` retrieves metadata without downloading datasets. Downloads reuse checksum-verified originals and resume `.part` files with HTTP range requests and server validators. OSM snapshots are dated and MD5-verified; SHA-256 receipts protect every cached file. Source/API errors are recorded and cause a nonzero exit; there is no substitute dataset or invented feature.

If a source is slow, `preprocess.py --vectors-only` prepares available OSM and boundary downloads independently. After WorldPop finishes, use `preprocess.py --population-only` to add its clip to the exact same configured study area, then run `audit.py`. The WorldPop server may ignore Range requests despite advertising them; in that case the downloader safely restarts the transfer. The manifest retains the STAC asset URL and the actual attachment-mode download URL.

## Google Colab / Drive

Upload or clone this module into Colab, install `requirements.txt`, then execute the same scripts. They detect Colab, mount `/content/drive`, and write **both raw and processed data** to `storage.colab_drive_root`, by default `/content/drive/MyDrive/flood_project/exposure_infrastructure`. Adjust that path in the config. An explicit `--root` overrides automatic Drive mounting. Final datasets do not rely on `/content` temporary storage.

## Choose a study area

The initial bbox `[73.75, 31.05, 74.05, 31.35]` is a **provisional Balloki vicinity**, not the Ravi catchment, an official pilot boundary, or an inferred flood extent. Its WGS84 coordinates use `[west, south, east, north]`. It must be verified before operational risk calculations. ERA5/GloFAS download extents are not used.

Edit the `area` object; keep a unique safe `name` for each selection:

```json
{"name":"custom", "mode":"bbox", "bbox":[73.75,31.05,74.05,31.35], "verified":false}
```

```json
{"name":"ravi_catchment", "mode":"polygon", "path":"../inputs/ravi.gpkg", "layer":"catchment", "verified":true}
```

```json
{"name":"kasur", "mode":"admin", "level":"ADM2", "field":"shapeName", "value":"Kasur", "verified":false}
```

```json
{"name":"punjab", "mode":"admin", "level":"ADM1", "field":"shapeName", "value":"Punjab", "verified":false}
```

```json
{"name":"pakistan", "mode":"pakistan", "verified":false}
```

Inspect actual downloaded `shapeName` values before selecting an administrative name. Paths in the config are relative to the **config directory**. Supply already verified admin polygons using `existing_boundaries`, e.g. `{"ADM1":"../inputs/provinces.geojson","ADM2":"../inputs/districts.geojson"}`. Such files take precedence; their licensing/provenance needs confirmation. The audit expects their identifying name field `shapeName`. No source boundary is silently repaired, reconciled or replaced. The geoBoundaries representation, OSM extract region and WorldPop footprint may differ in disputed territories; full Pakistan processing means the selected boundary representation, with availability limited by each source footprint. Review these differences rather than treating the sources as politically identical.

Set `flood_extents` to existing georeferenced raster/vector segmentation outputs. Auditing reports compatible CRS and overlapping footprints. It cannot establish geolocation accuracy or segmentation quality; absence of outputs is explicitly `NOT_CHECKED`.

## Data and provenance

```text
datasets/exposure/
  raw/worldpop/        # original national 2025 count raster + receipt
  raw/osm/             # dated Pakistan PBF + receipt
  raw/boundaries/      # full-resolution ADM0/ADM1/ADM2 originals
  processed/balloki/
    population/ roads/ buildings/ hospitals/ schools/
    settlements/ critical_infrastructure/ boundaries/
  metadata/           # manifest, API metadata, summary CSV
  validation_reports/ # audit JSON/Markdown, extraction log, sample PNG
```

WorldPop STAC discovers the actual file link for `pak_pop_2025_CN_100m_R2025A_v1`. The metadata description explicitly states **people per pixel** (counts); one asset description misleadingly says density. This is a modelled 2025 estimate, not a census. Units, citation, DOI, version, bounds and license are retained in source metadata.

The population clip uses native pixels, data type, CRS, nodata and grid; no resampling or reprojection. Pixels whose centres fall inside the area are retained. Clipping reduces totals by excluding outside cells; boundary cells are not fractionally apportioned. Any later reprojection must use a validated conservative redistribution of cell totals. The map alone is downsampled for display and must not be used for population calculations.

OSM is streamed with pyosmium, including polygon assembly for multipolygon relations. All source tags are retained in `tags_json`, with useful fields also exposed as columns. IDs include element type to distinguish node/way/relation namespaces. Buildings keep polygons; facilities retain original point/polygon geometry and source types. Hospitals includes clinics/doctors; schools includes colleges/universities/kindergartens. Additional critical infrastructure is a separate layer. Source-ID duplicates are suppressed; coincident distinct source objects are reported rather than automatically deleted. Invalid source geometries are repaired with `make_valid`; failed extraction and repairs are counted in a separate log.

Roads split at every source node, retaining `u`, `v`, OSM way ID, direction, geodesic length and tags. Intersections connect only when source nodes are shared, so crossings over bridges do not create artificial connections. New clip endpoints have explicit synthetic boundary IDs. Access restrictions are retained, not discarded; a later routing engine must interpret access, conditional rules, implicit legal defaults and barriers. Direction is a starting interpretation of explicit `oneway` and roundabout tags. Original turn-restriction relations are exported in `roads/turn_restrictions_pakistan.jsonl` (national reference, including restrictions outside the AOI). This is a network-compatible GIS dataset, not an evacuation routing engine.

Admin GeoPackage contains `ADM1` and `ADM2` clipped layers plus full intersecting `_context` layers. Context polygons deliberately extend outside the AOI; only clipped layers are audited for containment.

## Validation and limits

The audit checks original SHA-256 receipts, raster readability/sums/negative values/AOI overlap, vector CRS/validity/containment, feature-ID duplicates, coincident geometry and attribute availability. Summary includes raw and processed sizes, count/valid cells, bounds and readiness. Shared OSM bytes are not additional downloads per layer. Zero-feature facilities are flagged for review, not fabricated. Missing data/invalid geometry are `BLOCKED`; provisional areas or gaps requiring human review are `REVIEW`. OSM completeness and unexpected real-world gaps require external inventories; geometry checks alone cannot prove completeness. Constrained WorldPop nodata is not assumed to mean zero people.

## Initial Balloki acquisition

The first completed run downloaded 302,113,123 bytes of original data: WorldPop 2025 R2025A v1, Geofabrik snapshot `pakistan-261009.osm.pbf`, and geoBoundaries ADM0/ADM1/ADM2. The provisional pilot clip contains 63,111 valid population cells (estimated population 914,649.40), 17,203 road segments, 440 building polygons, 1 mapped hospital, 2 mapped schools and 158 settlements. It intersects one province and three district polygons. No additional critical infrastructure objects matched the configured OSM categories.

The outputs pass geometry/containment/duplicate-ID checks. Readiness is **REVIEW**: the area needs verification, building/facility coverage needs independent inventory checks, ADM1/ADM2 represent 2019, and no flood masks were available for alignment checking. Two invalid OSM area geometries were logged during the national scan; their relevance to the pilot is not established. Counts are source observations, not a complete real-world inventory or estimates of flood exposure. See the generated audit and extraction reports for details.

National processing streams raster tiles and OSM objects, but uniqueness sets still need memory. `osm_location_index` defaults to `disk`, using a disk-backed `sparse_file_array` under `metadata/osm_node_locations.idx`; `flex_mem` is also supported when RAM permits. The compiled tag filter runs after location caching and polygon assembly, so untagged geometry members are retained without excessive Python callbacks. Allow several GB of RAM and disk for national extraction. Use bbox/polygon pilots first. Roads are intentionally detailed node-to-node edges, so their record count exceeds OSM way count. Run one writer per persistent root at a time. Rerunning preprocessing rebuilds processed outputs; raw files remain untouched. Use `audit.py --no-map` for national selections; previews are automatically skipped above 250,000 vector records to avoid loading a national vector dataset into the plotting process.

Official sources: [WorldPop STAC](https://api.stac.worldpop.org/), [WorldPop Hub](https://hub.worldpop.org/), [Geofabrik Pakistan](https://download.geofabrik.de/asia/pakistan.html), [OSM license](https://www.openstreetmap.org/copyright), [geoBoundaries API](https://www.geoboundaries.org/api.html). Licenses: WorldPop CC BY 4.0; OSM ODbL 1.0; geoBoundaries source-specific license retained from the gbOpen API. Attribute the providers when publishing derived datasets or maps.
