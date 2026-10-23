"""Download original official datasets. Restarting resumes incomplete downloads."""
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from common import setup, load, manifest, write_json, now, digest, boundary_path


def session():
    s = requests.Session()
    s.headers["User-Agent"] = "Pakistan-Flood-Exposure-Data/1.0"
    s.mount("https://", HTTPAdapter(max_retries=Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])))
    return s


def get_json(s, url):
    r = s.get(url, timeout=(30, 120))
    r.raise_for_status()
    return r.json()


def download(s, url, path, expected_md5=None):
    """Use If-Range validators, validate lengths/checksums, atomically commit."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path = path.with_suffix(path.suffix + ".receipt.json")
    if path.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt["url"] == url and path.stat().st_size == receipt["bytes"] and digest(path) == receipt["sha256"]:
            if expected_md5 and digest(path, "md5") != expected_md5:
                raise ValueError(f"Remote checksum changed for {path}; choose a dated OSM snapshot, do not overwrite original data")
            print(f"Verified cached: {path.name}", flush=True)
            return receipt
    if path.exists():
        raise ValueError(f"Unverified existing original: {path}. Move it aside explicitly before downloading.")
    part = path.with_suffix(path.suffix + ".part")
    validator_path = part.with_suffix(part.suffix + ".json")
    for attempt in range(5):
        try:
            validator = json.loads(validator_path.read_text()) if validator_path.exists() else {}
            offset = part.stat().st_size if part.exists() else 0
            headers = {"Accept-Encoding": "identity"}
            if offset and validator.get("url") == url and validator.get("validator"):
                headers.update({"Range": f"bytes={offset}-", "If-Range": validator["validator"]})
            else:
                offset = 0
            with s.get(url, headers=headers, stream=True, timeout=(30, 180)) as r:
                r.raise_for_status()
                if r.status_code == 206:
                    match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)", r.headers.get("Content-Range", ""))
                    if not match or int(match[1]) != offset:
                        raise ValueError("Invalid Content-Range; refusing to append")
                    expected_size = int(match[3])
                else:
                    offset = 0
                    expected_size = int(r.headers.get("Content-Length", 0))
                write_json(validator_path, {"url": url, "validator": r.headers.get("ETag") or r.headers.get("Last-Modified")})
                print(f"Downloading {path.name}, resume={offset:,} bytes", flush=True)
                with part.open("ab" if offset else "wb") as out:
                    received = offset
                    last_log = received
                    for chunk in r.iter_content(64 * 1024):
                        out.write(chunk)
                        received += len(chunk)
                        if received - last_log >= 16 * 1024 * 1024:
                            print(f"{path.name}: {received:,} bytes", flush=True)
                            last_log = received
                if expected_size and part.stat().st_size != expected_size:
                    raise IOError("Incomplete download")
                if not part.stat().st_size:
                    raise IOError("Empty download")
                if expected_md5 and digest(part, "md5") != expected_md5:
                    part.unlink()
                    raise IOError("MD5 mismatch")
                receipt = {"url": url, "downloaded_at": now(), "bytes": part.stat().st_size, "sha256": digest(part),
                           "etag": r.headers.get("ETag"), "last_modified": r.headers.get("Last-Modified")}
                part.replace(path)
                write_json(receipt_path, receipt)
                return receipt
        except (requests.RequestException, IOError, ValueError) as exc:
            print(f"Attempt {attempt + 1} failed for {path.name}: {exc!r}", flush=True)
            if attempt == 4:
                raise
            time.sleep(min(2 ** attempt, 16))


def run(cfg, data, metadata_only=False):
    if cfg.get("boundary_provider") == "hdx_cod":
        from hdx_boundaries import acquire as acquire_hdx
        acquire_hdx(cfg, data, metadata_only)
    s, m = session(), manifest(data)
    errors = {}
    pending = []
    def save():
        m["updated_at"] = now()
        write_json(data / "metadata/manifest.json", m)
    def acquire(key, metadata, url, path, license_text, checksum=None):
        write_json(data / f"metadata/{key}_source.json", metadata)
        entry = {"source_metadata": metadata, "url": url, "raw_path": path.relative_to(data).as_posix(), "license": license_text, "status": "metadata_only", "metadata_retrieved_at": now()}
        if key == "worldpop":
            props = metadata["properties"]
            entry.update(version=props["Release"] + "/" + props["Version"], year=props["year"], crs=f"EPSG:{props['projection:epsg']}", bbox=metadata["bbox"], units="people per pixel")
        elif key == "osm":
            entry.update(version=metadata["selected_snapshot"], crs="EPSG:4326")
        else:
            entry.update(version=metadata["boundaryID"], year=metadata.get("boundaryYearRepresented"), crs="EPSG:4326", feature_count=int(metadata["admUnitCount"]))
        old = m["sources"].get(key, {})
        if metadata_only and old.get("url") == url and old.get("status") == "downloaded":
            entry.update({k: old[k] for k in ("status", "downloaded_at", "bytes", "sha256", "etag", "last_modified") if k in old})
        if not metadata_only:
            pending.append((key, url, path, checksum))
        m["sources"][key] = entry
        save()
    keys = ("worldpop", "osm") if cfg.get("boundary_provider") == "hdx_cod" else ("worldpop", "osm", "ADM0", "ADM1", "ADM2")
    for key in keys:
        try:
            if key == "worldpop":
                item = get_json(s, f"https://api.stac.worldpop.org/collections/PAK/items/{cfg['worldpop_item']}")
                props = item["properties"]
                if int(props["year"]) != 2025 or props["resolution"] != "100m" or "people per pixel" not in props["description"]:
                    raise ValueError("WorldPop item is not 2025 100m population counts")
                asset_url = item["assets"]["data"]["href"]
                # Official server attachment mode avoids stalled inline TIFF transfers.
                url = asset_url + ("&" if "?" in asset_url else "?") + "download=1"
                acquire(key, item, url, data / "raw/worldpop" / asset_url.rsplit("/", 1)[1], "CC BY 4.0; WorldPop, University of Southampton; DOI in STAC metadata")
            elif key == "osm":
                index = get_json(s, "https://download.geofabrik.de/index-v1-nogeom.json")
                feature = next(x for x in index["features"] if x["properties"]["id"] == "pakistan")
                # Resolve latest to a dated, immutable snapshot from the official page.
                html = s.get("https://download.geofabrik.de/asia/pakistan.html", timeout=120)
                html.raise_for_status()
                snapshots = sorted(set(re.findall(r'pakistan-\d{6}\.osm\.pbf', html.text)))
                if not snapshots:
                    raise ValueError("No dated Geofabrik snapshot discovered")
                filename = snapshots[-1]
                url = "https://download.geofabrik.de/asia/" + filename
                checksum_response = s.get(url + ".md5", timeout=120)
                checksum_response.raise_for_status()
                checksum = checksum_response.text.split()[0]
                feature["selected_snapshot"] = filename
                feature["md5"] = checksum
                acquire(key, feature, url, data / "raw/osm" / filename, "ODbL 1.0; © OpenStreetMap contributors; extract by Geofabrik", checksum)
            elif cfg.get("existing_boundaries", {}).get(key):
                path = boundary_path(cfg, data, key)
                if not path.exists():
                    raise FileNotFoundError(path)
                m["sources"][key] = {"status": "existing", "path": str(path), "sha256": digest(path), "license": "User-provided; provenance must be verified"}
                save()
            else:
                info = get_json(s, f"https://www.geoboundaries.org/api/current/gbOpen/PAK/{key}/")
                acquire(key, info, info["gjDownloadURL"], data / f"raw/boundaries/PAK_{key}.geojson", info.get("boundaryLicense", "See source metadata"))
        except Exception as exc:
            errors[key] = repr(exc)
            m["sources"].setdefault(key, {})["error"] = repr(exc)
            save()
            print(f"FAILED {key}: {exc}", flush=True)
    # Different originals can download independently; manifest writes remain sequential.
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = {pool.submit(download, session(), url, path, checksum): key for key, url, path, checksum in pending}
        for future in as_completed(futures):
            key = futures[future]
            try:
                m["sources"][key].update(future.result())
                m["sources"][key]["status"] = "downloaded"
                m["sources"][key].pop("error", None)
            except Exception as exc:
                errors[key] = repr(exc)
                m["sources"][key]["error"] = repr(exc)
                print(f"FAILED {key}: {exc}", flush=True)
            save()
    if errors:
        raise RuntimeError(f"Downloads incomplete: {errors}")


if __name__ == "__main__":
    parser = setup(__doc__)
    parser.add_argument("--metadata-only", action="store_true")
    args = parser.parse_args()
    run(*load(args), metadata_only=args.metadata_only)
