"""Build a private/static portal snapshot from the four local flood model folders.

No third-party Python packages required. This reads source datasets and writes
only to data_portal/dist. It never changes the scientific inputs or QC decisions.
"""
from __future__ import annotations

import calendar
import csv
import hashlib
import json
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
    "imerg": ("NASA IMERG via NOAA", "Daily catchment rainfall comparison", "https://gpm.nasa.gov/data/imerg", "Ten event and ordinary-day samples only; comparison data are held out of training. One v07 day has ambiguous missing values."),
    "chirps_v3": ("CHIRPS v3", "Daily catchment rainfall comparison", "https://data.chc.ucsb.edu/products/CHIRPS/v3.0/daily/readme.txt", "Ten daily rnl samples only; ERA5 distributes pentad totals among days. Comparison data are held out of training."),
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


def provider_for(path):
    name = path.as_posix().lower()
    for key in ("nasa_power", "imerg", "chirps_v3", "wapda", "ffd", "irsa", "global_watersheds"):
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
        if "__pycache__" not in document.parts:
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
    raw_files = [p for p in (MODEL / "raw").rglob("*") if p.is_file() and p.suffix.lower() not in (".md", ".pyc")]
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
    integrity = collect_integrity()
    clean_raw = read_csv("discharge/marala_daily_inflow_clean.csv")
    rain_raw = read_csv("rainfall/marala_catchment_daily_precipitation.csv")
    catalog = read_csv("discharge/marala_discharge_all_sources.csv")
    reviews = read_csv("discharge/marala_inflow_quality_review.csv")
    quality = read_json(PROCESSED / "discharge/marala_daily_inflow_quality_report.json", {})
    rain_report = read_json(PROCESSED / "rainfall/marala_rainfall_collection_report.json", {})
    rain_validation = read_json(PROCESSED / "rainfall/marala_rainfall_validation_report.json", {})
    rain_comparison_dir = PROCESSED / "rainfall/source_comparison_2026-10-26"
    rain_comparison = read_json(rain_comparison_dir / "source_comparison_report.json", {})
    catchment_report = read_json(PROCESSED / "catchment/marala_catchment_verification.json", {})
    feature_audit = read_json(PROCESSED / "metadata/marala_feature_coverage_audit.json", {})
    precipitation = [{"date": r["date"], "value": number(r["precipitation_mm_day"]), "coverage": number(r["valid_area_fraction"]),
                      "flag": r["quality_flag"]} for r in rain_raw]
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
    downloads = []
    downloadable = []
    for path in sorted(rain_comparison_dir.glob("*")):
        if path.name not in ("README.md", "source_comparison_report.json", "marala_precipitation_source_comparison.csv"):
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
            # Large source-cell tables are available locally; the portal packages
            # the principal series, reviews, manifests and geospatial evidence.
            include = path.name != "marala_catchment_grid_daily_precipitation.csv"
            if include:
                shutil.copy2(path, DIST / "downloads" / path.name)
                downloadable.append(path)
            downloads.append({"name": path.name, "category": folder, "bytes": path.stat().st_size,
                              "path": path.relative_to(WORKSPACE).as_posix(), "url": f"downloads/{path.name}" if include else None,
                              "sha256": hash_file(path)})
    monthly = {"inflow": month_coverage(clean_raw, lambda r: r["eligible_daily_training"] == "1"),
               "precipitation": month_coverage(rain_raw, lambda r: r["precipitation_mm_day"] != "")}
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
        files = [f for f in root.rglob("*") if f.is_file() and f.suffix.lower() in (".csv", ".json", ".geojson", ".xls", ".xlsx", ".pdf", ".tif", ".nc", ".grib")]
        case = {"id": key, "label": label, "detail": detail, "files": len(files), "status": "collected" if files else "not_collected",
                "ranges": ["short", "long"], "stations": [{"id": "marala", "name": "Chenab · Marala", "status": "collected"},
                    {"id": "jassar", "name": "Ravi · Jassar", "status": "not_collected"}] if key == "riverine" else []}
        cases.append(case)
    result = {"schema_version": 1, "built_utc": datetime.now(timezone.utc).isoformat(), "cases": cases,
              "scope": "The four flood-model folders. Exposure/infrastructure data is a separate module and is not mixed into these model datasets.",
              "sources": sources, "integrity": integrity, "downloads": downloads,
              "marala": {"inflow": inflow, "precipitation": precipitation, "ffd": ffd, "irsa": irsa, "peaks": peaks,
                         "feature_coverage_audit": feature_audit,
                         "reviews": reviews, "events": events, "monthly": monthly,
                         "quality": quality, "rainfall_report": {k: v for k, v in rain_report.items() if k != "receipts"},
                         "rainfall_validation": rain_validation, "catchment": {k: v for k, v in catchment_report.items() if k != "source_receipts"},
                         "rainfall_source_comparison": {"status": rain_comparison.get("status"),
                                                        "power_historical_profile": rain_comparison.get("power_historical_profile", {}),
                                                        "imerg_full_days": rain_comparison.get("imerg_full_days"),
                                                        "chirps_full_days": rain_comparison.get("chirps_full_days")},
                         "rainfall_screening": {"threshold_mm_day": 100, "rule": "Advisory review screen for catchment means >=100 mm/day; not an official flood or invalid-data threshold. Source values are unchanged.",
                                                "count": len(high_precipitation), "maximum": max(high_precipitation, key=lambda r: r["value"]) if high_precipitation else None,
                                                "dates": [r["date"] for r in high_precipitation]},
                         "catalog_counts": dict(Counter(r["source"] for r in catalog)),
                         "catalog_rows": len(catalog), "unknown_time_rows": sum(not r["time_pakistan"] for r in catalog),
                         "time_status_counts": dict(Counter(r["time_status"] for r in catalog)),
                         "ffd_duplicate_dates": {d: n for d, n in Counter(r["date"] for r in ffd).items() if n > 1},
                         "flag_counts": dict(Counter(r["quality_flag"] for r in catalog if r["quality_flag"]))}}
    path = DIST / "data/portal.json"
    path.write_text(json.dumps(result, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    manifest = {"snapshot_built_utc": result["built_utc"], "snapshot_sha256": hash_file(path),
                "integrity_counts": integrity["counts"], "source_groups": len(sources), "download_count": len(downloadable),
                "asset_versions": asset_versions}
    (DIST / "data/build_report.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest))
    return result


if __name__ == "__main__":
    build()
