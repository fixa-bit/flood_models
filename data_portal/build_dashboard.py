"""Build a private/static portal snapshot from the four local flood model folders.

No third-party Python packages required. This reads source datasets and writes
only to data_portal/dist. It never changes the scientific inputs or QC decisions.
"""
from __future__ import annotations

import calendar
import csv
import hashlib
import json
import math
import re
import shutil
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

PORTAL = Path(__file__).resolve().parent
WORKSPACE = PORTAL.parent
DIST = PORTAL / "dist"
MODEL = WORKSPACE / "riverine flood/short range/dataset/chenab_marala"
PROCESSED = MODEL / "processed/marala"
GEE_RAINFALL = MODEL / "raw/marala/rainfall/google_earth_engine"
STATION_FOLDERS = ["catchment", "dewpoint_temperature", "discharge", "NDSI_Snow_Cover",
                   "potential_evaporation_sum", "rainfall", "snow_depth",
                   "snow_depth_water_equivalent", "snowmelt_sum", "static_attributes",
                   "surface_solar_radiation_downwards_sum", "temperature"]
STATION_REGISTRY = [
    {"id": "marala", "name": "Chenab · Marala", "basin": "Chenab", "root": MODEL / "raw/marala"},
    {"id": "khanki", "name": "Chenab · Khanki", "basin": "Chenab", "root": MODEL / "raw/khanki"},
    {"id": "qadirabad", "name": "Chenab · Qadirabad", "basin": "Chenab", "root": MODEL / "raw/qadirabad"},
    {"id": "trimmu", "name": "Chenab · Trimmu", "basin": "Chenab", "root": MODEL / "raw/trimmu"},
]
GEE_PRODUCTS = {
    "era5land_mm": ("ERA5-Land", "1980-01-01"),
    "chirps_mm": ("CHIRPS v2 Daily", "1981-01-01"),
    "persiann_mm": ("PERSIANN-CDR", "1983-01-01"),
    "imerg_mm": ("IMERG V07 Final", "2000-06-01"),
}
DAILY_INPUTS = [
    {"id": "snow_depth", "name": "Snow depth", "folder": "snow_depth", "glob": "*.csv",
     "column": "snow_depth_m", "unit": "m", "source": "ECMWF ERA5-Land Daily Aggregated (via Google Earth Engine)", "color": "#82d4d0"},
    {"id": "snow_water_equivalent", "name": "Snow water equivalent", "folder": "snow_depth_water_equivalent", "glob": "*.csv",
     "column": "swe_mm", "unit": "mm", "source": "ECMWF ERA5-Land Daily Aggregated (via Google Earth Engine)", "color": "#c6abd8"},
    {"id": "snowmelt", "name": "Snowmelt", "folder": "snowmelt_sum", "glob": "*.csv",
     "column": "snowmelt_mm", "unit": "mm/day", "source": "ECMWF ERA5-Land Daily Aggregated (via Google Earth Engine)", "color": "#73d2df"},
    {"id": "snow_cover", "name": "Satellite snow cover (NDSI)", "folder": "NDSI_Snow_Cover", "glob": "*.csv",
     "column": "snow_cover_pct", "unit": "%", "quality_column": "valid_frac", "source": "NASA/USGS MODIS Terra MOD10A1 v6.1 (via Google Earth Engine)", "color": "#b0b9ff"},
    {"id": "temperature", "name": "Catchment mean temperature", "folder": "temperature/google_earth_engine",
     "glob": "marala_daily_temperature*.csv", "column": "era5land_temperature_2m_c", "unit": "deg C", "source": "ECMWF ERA5-Land Daily Aggregated (via Google Earth Engine)", "color": "#f4c76b"},
    {"id": "dewpoint", "name": "Dewpoint temperature", "folder": "dewpoint_temperature", "glob": "*.csv",
     "column": "dewpoint_c", "unit": "deg C", "source": "ECMWF ERA5-Land Daily Aggregated (via Google Earth Engine)", "color": "#f598bd"},
    {"id": "potential_evaporation", "name": "Potential evaporation", "folder": "potential_evaporation_sum", "glob": "*.csv",
     "column": "pet_mm", "unit": "mm/day", "source": "ECMWF ERA5-Land Daily Aggregated (via Google Earth Engine)", "color": "#8db9df"},
    {"id": "solar_radiation", "name": "Surface solar radiation", "folder": "surface_solar_radiation_downwards_sum", "glob": "*.csv",
     "column": "ssrd_wm2", "unit": "W/m2", "source": "ECMWF ERA5-Land Daily Aggregated (via Google Earth Engine)", "color": "#efb35e"},
]
CASE_FOLDERS = [
    ("riverine", "Riverine flood", "riverine flood", "River discharge and catchment precipitation"),
    ("flash", "Flash flood", "flash flood", "Rapid rainfall and runoff response"),
    ("seasonal", "Seasonal flood", "seasonal flood", "Seasonal water and climate signals"),
    ("urban", "Urban flood", "urban flood", "Urban rainfall, drainage and inundation"),
]
PROVIDERS = {
    "wapda": ("WAPDA", "Daily Marala inflow", "https://wapda.gov.pk/river-flow/", "Dated observations; most individual reading times are unconfirmed."),
    "ffd": ("FFD · PMD", "Flood-season discharge bulletins", "https://ffd.pmd.gov.pk/bulletins/archive", "06:00 Pakistan observations; archive/PDF date conflicts remain flagged."),
    "irsa": ("IRSA", "Daily mean discharge", "http://pakirsa.gov.pk/DailyData.aspx", "Daily means remain separate from point readings; averaging bounds are unstated."),
    "pmd": ("PMD journal", "Selected historical flood peaks", "https://www.pmd.gov.pk/rnd/rndweb/rnd_new/journal/vol13_issue26_files/5_Flood_Forecasting_of_an_Ungauged_Trans-boundary_Chenab_River_Basin_Using_Distributed_Hydrological_Model_Integrated_Flood_Analysis_System_%28IFAS%29.pdf", "Selected event maxima, not a daily training series."),
    "nasa_power": ("NASA POWER", "Catchment precipitation", "https://power.larc.nasa.gov/docs/services/api/temporal/daily/", "MERRA2 / GEOSIT grid estimates, area-weighted over the catchment; UTC days."),
    "chirps_v3": ("CHIRPS v3", "Preferred historical Marala catchment rainfall", "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/readme.txt", "Final RNL historical series and separate Preliminary SAT dates; a compact third-party copy supplies most historical cells and is checked against original CHC GeoTIFF samples."),
    "global_watersheds": ("Global Watersheds", "MERIT-derived catchment and rivers", "https://mghydro.com/watersheds/help.html", "Research delineation checked against sources and geometry; not agency-certified."),
    "jica": ("JICA · PMD inventory", "Station-location evidence", "https://openjicareport.jica.go.jp/pdf/12395935.pdf", "Marala coordinates in the station inventory; PDF page 36."),
    "references": ("Methodology references", "Data definitions and source documentation", "https://power.larc.nasa.gov/docs/methodology/data/sources/", "Saved methodology pages and search snapshots; availability evidence is not a complete archive."),
}


def read_json(path, default=None):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def read_csv(relative):
    path = PROCESSED / relative
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def number(value):
    return float(value) if value not in ("", None) else None


def load_gee_rainfall(folder=None):
    """Load checked GEE exports, keeping QA warnings attached to exploratory values."""
    folder = folder or GEE_RAINFALL
    csv_path = folder / "marala_daily_precipitation_1980_2024.csv"
    status = {"state": "not_collected", "message": "ERA5-Land, CHIRPS v2, PERSIANN-CDR and IMERG: not collected yet. No Earth Engine values are plotted.",
              "method": "Native-grid pixel area × fraction inside the existing Marala catchment; UTC days (05:00–05:00 Pakistan time).",
              "products": [name for name, _ in GEE_PRODUCTS.values()]}
    if not csv_path.exists():
        chunks = list((folder / "chunks").glob("*/*.csv"))
        if chunks:
            status.update(state="in_progress", message=f"Earth Engine collection has started: {len(chunks)} monthly or smaller chunks saved at snapshot time. The four series will appear after extraction and QA finish.")
        return [], status
    try:
        qa = read_json(folder / "quality_report.json", {})
        if qa.get("merged_csv_sha256") != hash_file(csv_path):
            raise ValueError("CSV does not match the extraction quality report checksum")
        with csv_path.open(newline="", encoding="utf-8-sig") as stream:
            reader = csv.DictReader(stream)
            if reader.fieldnames != ["date", *GEE_PRODUCTS]:
                raise ValueError("Unexpected precipitation columns")
            records = list(reader)
        expected = [str(date(1980, 1, 1) + timedelta(days=i)) for i in range((date(2025, 1, 1) - date(1980, 1, 1)).days)]
        if [row["date"] for row in records] != expected:
            raise ValueError("CSV must have every unique date from 1980 through 2024 in order")
        sources = []
        qa_reasons = []
        for key, (name, available) in GEE_PRODUCTS.items():
            product_qa = qa.get("products", {}).get(key, {})
            if product_qa.get("units") != "mm/day":
                raise ValueError(f"Unconfirmed precipitation units for {name}")
            negative_days = set(product_qa.get("days_with_negative_source_pixels", []))
            missing_days = set(product_qa.get("unexpected_missing_days", []))
            if negative_days:
                qa_reasons.append(f"{name}: {len(negative_days)} days have negative source pixels")
            if missing_days:
                qa_reasons.append(f"{name}: {len(missing_days)} unexpected missing days")
            rows = []
            for record in records:
                text = record[key].strip()
                value = None if text.lower() in ("", "nan") else float(text)
                if value is not None and not math.isfinite(value):
                    value = None
                negative = value is not None and value < 0
                if negative:
                    value = None
                if record["date"] < available and value is not None:
                    raise ValueError(f"Value before requested availability for {name}")
                flag = ("expected_unavailable" if record["date"] < available and value is None else
                        "negative_daily_mean_omitted" if negative else
                        "missing_source_value" if value is None else
                        "extraction_qa_passed" if qa.get("qa_passed") is True else "quality_review_required")
                rows.append({"date": record["date"], "value": value,
                             "flag": flag,
                             "representation": "native-grid area-weighted catchment mean; UTC day"})
            sources.append({"id": "gee_" + key.removesuffix("_mm"), "name": name, "group": "Earth Engine",
                            "status": "extraction QA passed; historical research series" if qa.get("qa_passed") is True else "exploratory only; extraction QA did not pass",
                            "method": status["method"], "download": "gee_" + csv_path.name, "rows": rows})
        passed = qa.get("qa_passed") is True
        status.update(state="ready" if passed else "exploratory",
                      message=("ERA5-Land, CHIRPS v2, PERSIANN-CDR and IMERG are loaded from the checked 1980–2024 extraction." if passed else
                               "GEE series are shown for visual comparison only; extraction QA did not pass. " + "; ".join(qa_reasons)),
                      csv_sha256=qa["merged_csv_sha256"])
        return sources, status
    except (ValueError, KeyError, TypeError, OSError) as error:
        status.update(state="withheld", message=f"Earth Engine precipitation is withheld: {error}. Existing comparison series remain visible.")
        return [], status


def provider_for(path):
    name = path.as_posix().lower()
    for key in ("nasa_power", "chirps_v3", "wapda", "ffd", "irsa", "global_watersheds"):
        if f"/{key}/" in name:
            return key
    if "/discharge/pmd/" in name:
        return "pmd"
    if "jica_station" in name:
        return "jica"
    return "references"


def hash_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_daily_inputs():
    """Discover registered date/value CSVs; retain missing values and flag conflicts."""
    results = []
    for spec in DAILY_INPUTS:
        folder = MODEL / "raw/marala" / spec["folder"]
        candidates = [folder / spec["file"]] if spec.get("file") else sorted(folder.glob(spec["glob"]))
        candidates = [path for path in candidates if path.is_file()]
        readings = defaultdict(list)
        source_files = []
        for path in candidates:
            source_files.append(path)
            with path.open(newline="", encoding="utf-8-sig") as handle:
                for row in csv.DictReader(handle):
                    day = row.get("date", "").strip()
                    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                        continue
                    raw = row.get(spec["column"], "").strip()
                    value = number(raw)
                    if value is not None and not math.isfinite(value):
                        value = None
                    quality = number(row.get(spec.get("quality_column", ""), "")) if spec.get("quality_column") else None
                    if quality is not None and not math.isfinite(quality):
                        quality = None
                    readings[day].append((value, quality, path))
        rows = []
        for day, values in sorted(readings.items()):
            unique = {value for value, _, _ in values if value is not None}
            conflict = len(unique) > 1
            value = None if conflict or not unique else next(iter(unique))
            quality_values = [q for _, q, _ in values if q is not None]
            date_sources = sorted({str(source.relative_to(WORKSPACE).as_posix()) for _, _, source in values})
            rows.append({"date": day, "value": value, "coverage": quality_values[0] if len(set(quality_values)) == 1 and quality_values else None,
                         "flag": "conflicting_duplicate" if conflict else ("missing_value" if value is None else ""),
                         "source_files": date_sources})
        if not rows:
            continue
        first = rows[0]["date"]
        last = rows[-1]["date"]
        download_name = f"marala_{spec['id']}_daily.csv"
        download_path = DIST / "downloads" / download_name
        with download_path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=["date", spec["column"], "quality_fraction", "quality_flag", "source_files"])
            writer.writeheader()
            for day, values in sorted(readings.items()):
                unique = {value for value, _, _ in values if value is not None}
                conflict = len(unique) > 1
                value = "" if conflict or not unique else format(next(iter(unique)), ".15g")
                qualities = [q for _, q, _ in values if q is not None]
                quality = "" if not qualities or len(set(qualities)) != 1 else format(qualities[0], ".15g")
                sources = "|".join(sorted({str(source.relative_to(WORKSPACE).as_posix()) for _, _, source in values}))
                writer.writerow({"date": day, spec["column"]: value, "quality_fraction": quality,
                                 "quality_flag": "conflicting_duplicate" if conflict else ("missing_value" if not unique else ""),
                                 "source_files": sources})
        results.append({"id": spec["id"], "name": spec["name"], "unit": spec["unit"], "source": spec["source"], "color": spec["color"],
                        "column": spec["column"], "rows": rows, "records": len(rows),
                        "values": sum(row["value"] is not None for row in rows),
                        "first_date": first, "last_date": last,
                        "source_files": [p.relative_to(WORKSPACE).as_posix() for p in source_files],
                        "download": download_name, "bytes": download_path.stat().st_size,
                        "sha256": hash_file(download_path),
                        "path": str(folder.relative_to(WORKSPACE).as_posix()),
                        "note": "Raw daily input values; no interpolation. Conflicting same-date values are withheld from the chart."})
    return results


def load_station_workspaces(daily_inputs):
    """List station raw folders and read simple date/numeric CSV series for future stations."""
    stations = []
    station_specs = list(STATION_REGISTRY)
    registered = {item["root"].resolve() for item in station_specs}
    for root in sorted((MODEL / "raw").iterdir()):
        if not root.is_dir() or root.resolve() in registered:
            continue
        station_id = re.sub(r"[^a-z0-9]+", "_", root.name.lower()).strip("_")
        if station_id:
            station_specs.append({"id": station_id, "name": f"Chenab · {root.name.replace('_', ' ').title()}",
                                  "basin": "Chenab", "root": root})
    ignored_columns = {"quality", "quality_flag", "coverage", "coverage_fraction", "valid_frac",
                       "source_files", "flag", "status", "is_observed"}
    for spec in station_specs:
        root = spec["root"]
        root.mkdir(parents=True, exist_ok=True)
        for folder in STATION_FOLDERS:
            (root / folder).mkdir(parents=True, exist_ok=True)
        (root / "temperature/google_earth_engine").mkdir(parents=True, exist_ok=True)
        folders = []
        files = []
        series = []
        static_values = []
        for path in sorted((root / "static_attributes").rglob("*.csv")):
            try:
                with path.open(newline="", encoding="utf-8-sig") as stream:
                    rows = list(csv.DictReader(stream))
                if rows:
                    static_values.extend({"name": key, "value": value, "source_file": path.relative_to(root).as_posix()}
                                         for key, value in rows[0].items() if value not in (None, ""))
                    break
            except (OSError, csv.Error, UnicodeError):
                continue
        catchment_info = None
        geojsons = sorted(path for path in (root / "catchment").rglob("*.geojson")
                          if "receipt" not in path.stem.lower())
        if geojsons:
            try:
                geometry = read_json(geojsons[0], {})
                features = geometry.get("features", [])
                catchment_info = {"file": geojsons[0].relative_to(root).as_posix(), "features": len(features),
                                  "geometry_types": sorted({feature.get("geometry", {}).get("type", "unknown") for feature in features}),
                                  "properties": features[0].get("properties", {}) if features else {}}
            except (OSError, ValueError, AttributeError):
                catchment_info = {"file": geojsons[0].relative_to(root).as_posix(), "features": None,
                                  "geometry_types": [], "properties": {}}
        daily_by_folder = defaultdict(list)
        if spec["id"] == "marala":
            input_folder_by_id = {entry["id"]: entry["folder"] for entry in DAILY_INPUTS}
            for feature in daily_inputs:
                daily_by_folder[input_folder_by_id[feature["id"]].split("/")[0]].append(feature)
        for folder in STATION_FOLDERS:
            directory = root / folder
            candidates = sorted(path for path in directory.rglob("*") if path.is_file()
                                and path.name != ".gitkeep" and path.suffix.lower() in (".csv", ".json", ".geojson", ".nc", ".grib", ".tif", ".pdf", ".xlsx", ".xls"))
            folder_files = []
            for path in candidates:
                relative = path.relative_to(root).as_posix()
                entry = {"name": path.name, "path": str(path.relative_to(WORKSPACE).as_posix()), "folder": folder,
                         "bytes": path.stat().st_size, "format": path.suffix.lower().lstrip("."), "download": None}
                folder_files.append(entry)
                if spec["id"] != "marala":
                    files.append(entry)
                if spec["id"] == "marala" or path.suffix.lower() != ".csv":
                    continue
                try:
                    with path.open(newline="", encoding="utf-8-sig") as stream:
                        reader = csv.DictReader(stream)
                        headers = reader.fieldnames or []
                        date_column = next((column for column in headers if column.strip().lower() in ("date", "day", "datetime", "time")), None)
                        if not date_column:
                            continue
                        table = list(reader)
                    for column in headers:
                        if column == date_column or column.strip().lower() in ignored_columns:
                            continue
                        values = []
                        for row in table:
                            day = (row.get(date_column) or "").strip()[:10]
                            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", day):
                                continue
                            try:
                                value = float((row.get(column) or "").strip())
                            except (TypeError, ValueError):
                                continue
                            if math.isfinite(value):
                                values.append({"date": day, "value": value})
                        if values:
                            series.append({"id": f"{spec['id']}:{relative}:{column}", "name": f"{path.stem} · {column}",
                                           "folder": folder, "column": column, "unit": "as saved", "rows": values,
                                           "records": len(values), "first_date": min(row["date"] for row in values),
                                           "last_date": max(row["date"] for row in values), "source_file": relative})
                except (OSError, csv.Error, UnicodeError):
                    continue
            related = daily_by_folder.get(folder, [])
            folders.append({"id": folder, "name": folder.replace("_", " "), "files": len(folder_files),
                            "formats": dict(Counter(entry["format"] for entry in folder_files)),
                            "first_date": min((item["first_date"] for item in related), default=None),
                            "last_date": max((item["last_date"] for item in related), default=None),
                            "series": len(related) + sum(item["folder"] == folder for item in series),
                            "items": [] if spec["id"] == "marala" else folder_files})
        stations.append({"id": spec["id"], "name": spec["name"], "basin": spec["basin"],
                         "path": root.relative_to(WORKSPACE).as_posix(), "status": "collected" if files or spec["id"] == "marala" else "empty",
                         "folders": folders, "files": files, "series": series,
                         "static_attributes": static_values, "catchment": catchment_info})
    return stations


def version_assets():
    """Refresh local script/style URLs when their bytes change.

    An existing browser tab can otherwise combine new navigation HTML with an
    older cached app.js that does not recognize the Summary route.
    """
    index = DIST / "index.html"
    html = index.read_bytes().decode("utf-8")
    versions = {}

    def replace(match):
        relative = match.group("path")
        version = hash_file(DIST / relative)[:12]
        versions[relative] = version
        return f'{match.group("attribute")}="{relative}?v={version}"'

    updated = re.sub(r'(?P<attribute>src|href)="(?P<path>assets/[\w.-]+\.(?:js|css))(?:\?[^"<>]*)?"', replace, html)
    if updated != html:
        index.write_bytes(updated.encode("utf-8"))
    return versions


def collect_integrity():
    """Compare unique local files with saved checksum claims, not internet copies."""
    claims = {}

    def claim(path, expected, url=""):
        path = path.resolve()
        if not path.is_relative_to(MODEL.resolve()) or not expected or len(str(expected)) != 64:
            return
        record = claims.setdefault(path, {"hashes": set(), "urls": set()})
        record["hashes"].add(str(expected).lower())
        if str(url).startswith(("http://", "https://")):
            record["urls"].add(url)

    def walk(value, document):
        if isinstance(value, dict):
            expected = value.get("sha256") or value.get("source_sha256")
            relative = value.get("raw_file") or value.get("source_file")
            if document.name.endswith(".receipt.json") and expected and value.get("source_url") and not relative:
                claim(document.with_name(document.name.removesuffix(".receipt.json")), expected, value["source_url"])
            elif expected and isinstance(relative, str):
                candidate = MODEL / relative
                if not candidate.exists() and (document.parent / relative).exists():
                    candidate = document.parent / relative
                claim(candidate, expected, value.get("source_url", value.get("url", "")))
            elif expected and isinstance(value.get("filename"), str):
                claim(document.parent / value["filename"], expected, value.get("source_url", ""))
            for child in value.values():
                if isinstance(child, (dict, list)):
                    walk(child, document)
        elif isinstance(value, list):
            for child in value:
                walk(child, document)

    for document in sorted(MODEL.rglob("*.json")):
        if not {"__pycache__", ".venv"}.intersection(document.parts):
            walk(read_json(document), document)
    for year in (2024, 2025, 2026):
        for row in read_csv(f"discharge/marala_ffd_{year}_bulletin_discharge.csv"):
            claim(MODEL / f"raw/marala/discharge/ffd/bulletins_{year}" / row["raw_file"], row["source_sha256"], row["source_url"])
    evidence = []
    for path, entry in sorted(claims.items()):
        actual = hash_file(path) if path.is_file() else None
        status = "missing" if actual is None else ("conflicting_claims" if len(entry["hashes"]) != 1 else ("match" if actual in entry["hashes"] else "mismatch"))
        evidence.append({"path": path.relative_to(WORKSPACE).as_posix(), "provider": provider_for(path),
                         "bytes": path.stat().st_size if path.is_file() else None,
                         "expected_sha256": sorted(entry["hashes"]), "actual_sha256": actual,
                         "status": status, "source_urls": sorted(entry["urls"])})
    raw_files = [p for p in (MODEL / "raw").rglob("*") if p.is_file() and ".venv" not in p.parts and p.suffix.lower() not in (".md", ".pyc")]
    untracked = [p.relative_to(WORKSPACE).as_posix() for p in raw_files if p.resolve() not in claims and not p.name.endswith(("receipt.json", "_receipt.json"))]
    return {"checked_utc": datetime.now(timezone.utc).isoformat(), "counts": dict(Counter(e["status"] for e in evidence)),
            "files": evidence, "untracked_files": untracked,
            "scope": "Recomputed local SHA-256 versus saved receipts; does not prove agency authenticity, measurement accuracy or that the live source is unchanged."}


def month_coverage(series, valid):
    if not series:
        return []
    dates = {r["date"]: r for r in series}
    start, end = min(dates), max(dates)
    result = []
    for year in range(int(start[:4]), int(end[:4]) + 1):
        for month in range(1, 13):
            expected = [f"{year}-{month:02d}-{day:02d}" for day in range(1, calendar.monthrange(year, month)[1] + 1)]
            applicable = [d for d in expected if start <= d <= end]
            count = sum(d in dates and valid(dates[d]) for d in applicable)
            result.append({"year": year, "month": month, "valid": count, "expected": len(applicable),
                           "fraction": count / len(applicable) if applicable else None})
    return result


def interval_series(rows, value_key):
    """Preserve gaps between dates rather than drawing across missing periods."""
    result, last = [], None
    for row in sorted(rows, key=lambda r: r["date"]):
        if last and date.fromisoformat(row["date"]) > date.fromisoformat(last) + timedelta(days=1):
            result.append({"date": str(date.fromisoformat(last) + timedelta(days=1)), "value": None})
        result.append({"date": row["date"], "value": number(row[value_key])})
        last = row["date"]
    return result


def build():
    asset_versions = version_assets()
    for directory in (DIST / "data", DIST / "downloads"):
        directory.mkdir(parents=True, exist_ok=True)
    daily_inputs = load_daily_inputs()
    station_workspaces = load_station_workspaces(daily_inputs)
    integrity = collect_integrity()
    clean_raw = read_csv("discharge/marala_daily_inflow_clean.csv")
    catalog = read_csv("discharge/marala_discharge_all_sources.csv")
    reviews = read_csv("discharge/marala_inflow_quality_review.csv")
    quality = read_json(PROCESSED / "discharge/marala_daily_inflow_quality_report.json", {})
    rain_report = read_json(PROCESSED / "rainfall/marala_rainfall_collection_report.json", {})
    rain_validation = read_json(PROCESSED / "rainfall/marala_rainfall_validation_report.json", {})
    rain_comparison_dir = PROCESSED / "rainfall/source_comparison_2026-10-26"
    rain_comparison = read_json(rain_comparison_dir / "source_comparison_report.json", {})
    chirps_dir = PROCESSED / "rainfall/chirps_v3_primary"
    chirps_collection = read_json(chirps_dir / "collection_report.json", {})
    chirps_final = read_csv("rainfall/chirps_v3_primary/marala_chirps_v3_final_rnl_daily_1990_2026.csv")
    chirps_preliminary = read_csv("rainfall/chirps_v3_primary/marala_chirps_v3_preliminary_sat_2026.csv")
    nasa_fresh = read_csv("rainfall/source_comparison_2026-10-26/nasa_power_fresh_historical_basin_candidate.csv")
    chirps_original_samples = read_csv("rainfall/source_comparison_2026-10-26/chirps_v3_daily_catchment_sample.csv")
    catchment_report = read_json(PROCESSED / "catchment/marala_catchment_verification.json", {})
    feature_audit = read_json(PROCESSED / "metadata/marala_feature_coverage_audit.json", {})
    # The saved NASA POWER long-request values have a verified request-range
    # inconsistency. Keep their raw files downloadable for audit, but make the
    # displayed precipitation series the separate CHIRPS Final candidate.
    precipitation = [{"date": r["date"], "value": number(r["precipitation_mm"]),
                      "coverage": number(r["valid_area_fraction"]), "flag": r["quality_flag"]} for r in chirps_final]
    rainfall_sources = [
        {"id": "chirps_final", "name": "CHIRPS v3 Final RNL", "group": "CHIRPS", "status": "preferred historical candidate",
         "method": "Daily pentad allocation uses ERA5; compact historical copy is rounded to 0.1 mm per cell.",
         "download": "marala_chirps_v3_final_rnl_daily_1990_2026.csv",
         "rows": [{"date": r["date"], "value": number(r["precipitation_mm"]), "flag": r["quality_flag"],
                   "coverage": number(r["valid_area_fraction"]), "representation": r["source_representation"]} for r in chirps_final]},
        {"id": "chirps_preliminary", "name": "CHIRPS v3 Preliminary SAT", "group": "CHIRPS", "status": "provisional; separate from Final RNL",
         "method": "Daily pentad allocation uses IMERG Late V07; replace with Final when published.",
         "download": "marala_chirps_v3_preliminary_sat_2026.csv",
         "rows": [{"date": r["date"], "value": number(r["precipitation_mm"]), "flag": r["quality_flag"],
                   "coverage": number(r["valid_area_fraction"]), "representation": r["source_representation"],
                   "source_url": r["source_url"]} for r in chirps_preliminary]},
        {"id": "nasa_fresh", "name": "NASA POWER fresh historical request", "group": "NASA POWER", "status": "hold: alternate request, comparison candidate",
         "method": "Separately requested 2016–2024 catchment means; not a correction to the saved series.",
         "download": "nasa_power_fresh_historical_basin_candidate.csv",
         "rows": [{"date": r["date"], "value": number(r["fresh_basin_mean_mm_day"]), "flag": r["training_status"],
                   "coverage": int(r["valid_cells"]) / int(r["required_cells"])} for r in nasa_fresh]},
        {"id": "chirps_original_samples", "name": "CHIRPS original GeoTIFF checks", "group": "CHIRPS", "status": "ten original-file check days; overlaps Final RNL",
         "method": "Full original CHC GeoTIFFs provide a precision check of the compact historical copy.",
         "download": "chirps_v3_daily_catchment_sample.csv",
         "rows": [{"date": r["date"], "value": number(r["precipitation_mm_day"]), "flag": "sample_check",
                   "coverage": 0 if int(r["missing_cells"]) else 1, "source_url": r["source_url"]} for r in chirps_original_samples]},
    ]
    gee_sources, gee_status = load_gee_rainfall()
    rainfall_sources.extend(gee_sources)
    for source in rainfall_sources:
        source["records"] = len(source["rows"])
        source["values"] = sum(row["value"] is not None for row in source["rows"])
        source["first_date"] = min((row["date"] for row in source["rows"]), default=None)
        source["last_date"] = max((row["date"] for row in source["rows"]), default=None)
    high_precipitation = [r for r in precipitation if r["value"] is not None and r["value"] >= 100]
    inflow = [{"date": r["date"], "value": number(r["inflow_cusecs"]), "source_value": number(r["source_inflow_cusecs"]),
               "eligible": r["eligible_daily_training"] == "1", "flag": r["quality_flag"], "time": r["time_pakistan"]} for r in clean_raw]
    ffd = []
    for year in (2024, 2025, 2026):
        for row in read_csv(f"discharge/marala_ffd_{year}_bulletin_discharge.csv"):
            ffd.append({"date": row["date"], "inflow": number(row["marala_inflow_1000_cusecs"]) * 1000,
                        "outflow": number(row["marala_outflow_1000_cusecs"]) * 1000,
                        "archive_date": row.get("archive_listed_date", row["date"]),
                        "flag": row.get("date_status", "matches_archive") != "matches_archive", "source_url": row["source_url"]})
    irsa = [{"date": r["date"], "inflow": number(r["mean_inflow_cusecs"]), "outflow": number(r["mean_outflow_cusecs"]), "source_url": r["source_url"]}
            for r in read_csv("discharge/marala_irsa_daily_mean_discharge.csv")]
    peaks = [{"date": r["peak_date"], "value": number(r["peak_discharge_1000_cusecs"]) * 1000,
              "level": r["flood_level_as_published"], "source_url": r["source_url"]} for r in read_csv("discharge/marala_pmd_historical_flood_peaks.csv")]
    marala_workspace = next((station for station in station_workspaces if station["id"] == "marala"), None)
    if marala_workspace:
        folder_map = {folder["id"]: folder for folder in marala_workspace["folders"]}
        discharge_folder = folder_map.get("discharge")
        if discharge_folder:
            discharge_dates = [row["date"] for row in inflow + ffd + irsa + peaks]
            discharge_folder["first_date"] = min(discharge_dates, default=None)
            discharge_folder["last_date"] = max(discharge_dates, default=None)
            discharge_folder["series"] = sum((bool(inflow), bool(ffd), bool(irsa), bool(peaks)))
        rainfall_folder = folder_map.get("rainfall")
        if rainfall_folder and precipitation:
            rainfall_folder["first_date"] = min(row["date"] for row in precipitation)
            rainfall_folder["last_date"] = max(row["date"] for row in precipitation)
            rainfall_folder["series"] = len(rainfall_sources)
    sources = []
    for key, (name, purpose, url, note) in PROVIDERS.items():
        evidence = [e for e in integrity["files"] if e["provider"] == key]
        if not evidence:
            continue
        if key == "nasa_power" and rain_comparison:
            note = "Training hold: full 2016–2024 check found request-range-dependent daily values; original and fresh candidate remain separate. " + note
        elif key == "nasa_power" and feature_audit.get("rainfall_quality_blocked"):
            note = "Training hold: saved long-range responses disagree with independent short-period daily/hourly checks. " + note
        urls = sorted({u for e in evidence for u in e["source_urls"]})
        sources.append({"id": key, "name": name, "purpose": purpose, "url": url, "note": note,
                        "counts": dict(Counter(e["status"] for e in evidence)), "files": len(evidence),
                        "links": urls, "bytes": sum(e["bytes"] or 0 for e in evidence)})
    for feature in daily_inputs:
        sources.append({"id": "input_" + feature["id"], "name": feature["name"],
                        "purpose": f"Daily model input, {feature['unit']}", "url": "",
                        "note": f"Auto-discovered from {feature['path']}; {feature['values']} of {feature['records']} dates have values. {feature['note']}",
                        "counts": {}, "files": len(feature["source_files"]), "links": [],
                        "bytes": sum((WORKSPACE / name).stat().st_size for name in feature["source_files"]),
                        "first_date": feature["first_date"], "last_date": feature["last_date"]})
    downloads = []
    downloadable = []
    for name in ("extract_precipitation.py", "run_precipitation.ps1", "requirements.txt", "README.md", "marala_daily_precipitation_1980_2024.csv",
                 "annual_totals.csv", "quality_report.json", "catchment_metadata.json", "run_manifest.json"):
        path = GEE_RAINFALL / name
        if not path.is_file():
            continue
        download_name = "gee_" + name
        shutil.copy2(path, DIST / "downloads" / download_name)
        downloadable.append(path)
        downloads.append({"name": download_name, "category": "Earth Engine catchment precipitation",
                          "bytes": path.stat().st_size, "path": path.relative_to(WORKSPACE).as_posix(),
                          "url": f"downloads/{download_name}", "sha256": hash_file(path)})
    for path in sorted(chirps_dir.glob("*")):
        if not path.is_file() or path.suffix not in (".csv", ".json", ".md"):
            continue
        download_name = "marala_chirps_v3_README.md" if path.name == "README.md" else path.name
        shutil.copy2(path, DIST / "downloads" / download_name)
        downloadable.append(path)
        downloads.append({"name": path.name, "category": "preferred CHIRPS rainfall", "bytes": path.stat().st_size,
                          "path": path.relative_to(WORKSPACE).as_posix(), "url": f"downloads/{download_name}",
                          "sha256": hash_file(path)})
    for path in sorted(rain_comparison_dir.glob("*")):
        if not path.is_file() or path.suffix not in (".csv", ".json", ".md"):
            continue
        download_name = "marala_precipitation_source_comparison_README.md" if path.name == "README.md" else path.name
        shutil.copy2(path, DIST / "downloads" / download_name)
        downloadable.append(path)
        downloads.append({"name": path.name, "category": "rainfall investigation", "bytes": path.stat().st_size,
                          "path": path.relative_to(WORKSPACE).as_posix(), "url": f"downloads/{download_name}",
                          "sha256": hash_file(path)})
    for folder in ("discharge", "rainfall", "catchment", "metadata"):
        if not (PROCESSED / folder).exists():
            continue
        for path in (PROCESSED / folder).iterdir():
            if not path.is_file() or path.suffix not in (".csv", ".json", ".geojson", ".png", ".md"):
                continue
            include = True
            if include:
                shutil.copy2(path, DIST / "downloads" / path.name)
                downloadable.append(path)
            downloads.append({"name": path.name, "category": folder, "bytes": path.stat().st_size,
                              "path": path.relative_to(WORKSPACE).as_posix(), "url": f"downloads/{path.name}" if include else None,
                              "sha256": hash_file(path)})
    for feature in daily_inputs:
        daily_path = DIST / "downloads" / feature["download"]
        downloadable.append(daily_path)
        downloads.append({"name": feature["download"], "category": "daily model inputs", "bytes": daily_path.stat().st_size,
                          "path": feature["path"], "url": f"downloads/{feature['download']}", "sha256": feature["sha256"]})
    static_attributes = MODEL / "raw/marala/static_attributes/marala_static_attributes.csv"
    if static_attributes.is_file():
        static_name = "marala_static_attributes.csv"
        static_copy = DIST / "downloads" / static_name
        shutil.copy2(static_attributes, static_copy)
        downloadable.append(static_copy)
        downloads.append({"name": static_name, "category": "daily model inputs", "bytes": static_copy.stat().st_size,
                          "path": static_attributes.relative_to(WORKSPACE).as_posix(), "url": f"downloads/{static_name}",
                          "sha256": hash_file(static_copy)})
    for station in station_workspaces:
        if station["id"] == "marala":
            continue
        for file in station["files"]:
            source = WORKSPACE / file["path"]
            if source.suffix.lower() != ".csv":
                continue
            download_name = f"station_{station['id']}_{file['folder']}_{source.name}"
            destination = DIST / "downloads" / download_name
            shutil.copy2(source, destination)
            file["download"] = download_name
            downloads.append({"name": download_name, "category": "station data", "bytes": source.stat().st_size,
                              "path": file["path"], "url": f"downloads/{download_name}", "sha256": hash_file(source)})
    monthly = {"inflow": month_coverage(clean_raw, lambda r: r["eligible_daily_training"] == "1"),
               "precipitation": month_coverage(chirps_final, lambda r: r["precipitation_mm"] != "")}
    events = []
    for year in sorted({r["date"][:4] for r in inflow}):
        candidates = [r for r in inflow if r["date"].startswith(year) and r["eligible"] and r["value"] is not None]
        if candidates:
            peak = max(candidates, key=lambda r: r["value"])
            day = date.fromisoformat(peak["date"])
            events.append({"id": year, "date": peak["date"], "value": peak["value"], "start": str(day - timedelta(days=14)),
                           "end": str(day + timedelta(days=14)), "label": f"{year} annual maximum · {peak['date']}",
                           "basis": "Exploratory window around the largest eligible daily WAPDA value; not an officially classified flood event."})
    cases = []
    for key, label, folder, detail in CASE_FOLDERS:
        root = WORKSPACE / folder
        files = [f for f in root.rglob("*") if f.is_file() and ".venv" not in f.parts and f.suffix.lower() in (".csv", ".json", ".geojson", ".xls", ".xlsx", ".pdf", ".tif", ".nc", ".grib")]
        case = {"id": key, "label": label, "detail": detail, "files": len(files), "status": "collected" if files else "not_collected",
                "ranges": ["short", "long"], "stations": [{"id": station["id"], "name": station["name"], "status": station["status"]}
                    for station in station_workspaces] if key == "riverine" else []}
        cases.append(case)
    result = {"schema_version": 1, "built_utc": datetime.now(timezone.utc).isoformat(), "cases": cases,
              "stations": station_workspaces,
              "scope": "The four flood-model folders. Exposure/infrastructure data is a separate module and is not mixed into these model datasets.",
              "sources": sources, "integrity": integrity, "downloads": downloads,
              "marala": {"inflow": inflow, "precipitation": precipitation, "rainfall_sources": rainfall_sources,
                         "ffd": ffd, "irsa": irsa, "peaks": peaks, "gee_precipitation": gee_status,
                         "feature_coverage_audit": feature_audit,
                         "reviews": reviews, "events": events, "monthly": monthly,
                         "quality": quality, "rainfall_report": {k: v for k, v in rain_report.items() if k != "receipts"},
                         "rainfall_validation": rain_validation, "catchment": {k: v for k, v in catchment_report.items() if k != "source_receipts"},
                         "rainfall_source_comparison": {"status": rain_comparison.get("status"),
                                                        "power_historical_profile": rain_comparison.get("power_historical_profile", {}),
                                                        "chirps_full_days": rain_comparison.get("chirps_full_days")},
                         "chirps_collection": {key: chirps_collection.get(key) for key in
                                               ("start", "final_end", "final_daily_rows", "final_complete_days",
                                                "preliminary_end", "preliminary_daily_rows", "preliminary_complete_days",
                                                "catchment_cells", "original_chc_samples_checked",
                                                "maximum_sample_absolute_difference_mm")},
                         "rainfall_screening": {"threshold_mm_day": 100, "rule": "Advisory review screen for catchment means >=100 mm/day; not an official flood or invalid-data threshold. Source values are unchanged.",
                                                "count": len(high_precipitation), "maximum": max(high_precipitation, key=lambda r: r["value"]) if high_precipitation else None,
                                                "dates": [r["date"] for r in high_precipitation]},
                         "catalog_counts": dict(Counter(r["source"] for r in catalog)),
                         "catalog_rows": len(catalog), "unknown_time_rows": sum(not r["time_pakistan"] for r in catalog),
                         "time_status_counts": dict(Counter(r["time_status"] for r in catalog)),
                         "ffd_duplicate_dates": {d: n for d, n in Counter(r["date"] for r in ffd).items() if n > 1},
                         "flag_counts": dict(Counter(r["quality_flag"] for r in catalog if r["quality_flag"]))}}
    result["marala"]["daily_inputs"] = daily_inputs
    path = DIST / "data/portal.json"
    temporary_path = path.with_suffix(".json.tmp")
    temporary_path.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    temporary_path.replace(path)
    manifest = {"snapshot_built_utc": result["built_utc"], "snapshot_sha256": hash_file(path),
                "integrity_counts": integrity["counts"], "source_groups": len(sources), "download_count": len(downloadable),
                "asset_versions": asset_versions}
    manifest_path = DIST / "data/build_report.json"
    manifest_tmp = manifest_path.with_suffix(".json.tmp")
    manifest_tmp.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    manifest_tmp.replace(manifest_path)
    print(json.dumps(manifest))
    return result


if __name__ == "__main__":
    build()
