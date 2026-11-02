"""Version-specific upstream-area selection and small resumable EWDS requests."""
import argparse
import calendar
import json
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import xarray as xr
from .common import load_config, resolve, save_json, sha


def distance_km(lat, lon, station_lat, station_lon):
    phi, phi0 = np.radians(lat), np.radians(station_lat)
    a = np.sin((phi-phi0)/2)**2 + np.cos(phi)*np.cos(phi0)*np.sin(np.radians(lon-station_lon)/2)**2
    return 6371.0088 * 2*np.arcsin(np.sqrt(np.clip(a, 0, 1)))


def select_cell(ds, station, area_km2):
    lat_name = "latitude" if "latitude" in ds.coords else "lat"
    lon_name = "longitude" if "longitude" in ds.coords else "lon"
    variable = next((v for v in ds.data_vars if "uparea" in v.lower().replace("_", "")), None)
    if variable is None:
        raise ValueError("Auxiliary dataset has no upstream-area variable")
    da = ds[variable]
    units = da.attrs.get("units", "").replace(" ", "").lower()
    if units in ["m2", "m^2", "m**2"]: factor = 1e-6
    elif units in ["km2", "km^2", "km**2"]: factor = 1.
    else: raise ValueError(f"Unknown upstream-area units: {units}")
    lat, lon = float(station["latitude"]), float(station["longitude"])
    delta = station["search_radius_km"] / 90.
    local = da.where(abs(ds[lat_name]-lat) <= delta, drop=True).where(abs(ds[lon_name]-lon) <= delta*2, drop=True)
    table = local.to_dataframe(name="area").reset_index()
    table["distance_km"] = distance_km(table[lat_name].to_numpy(), table[lon_name].to_numpy(), lat, lon)
    table["upstream_area_km2"] = table.area * factor
    table["relative_area_error"] = abs(table.upstream_area_km2 / area_km2 - 1)
    table = table[table.distance_km <= station["search_radius_km"]].sort_values("distance_km")
    if table.empty:
        raise ValueError("No grid cells near station")
    nearest = table.iloc[0]
    valid = table[np.isfinite(table.upstream_area_km2) & (table.upstream_area_km2 > 0) &
                  (table.relative_area_error <= station["relative_area_tolerance"])]
    if station.get("cell_override"):
        override = station["cell_override"]
        chosen = table[(abs(table[lat_name]-override["latitude"]) < 1e-6) & (abs(table[lon_name]-override["longitude"]) < 1e-6)]
        if len(chosen) != 1: raise ValueError("Cell override not on local grid")
        chosen = chosen.iloc[0]
    elif station["selection"] == "nearest_area_match":
        chosen = valid.iloc[0] if len(valid) else nearest
    elif station["selection"] == "nearest_cell": chosen = nearest
    else: raise ValueError("Unknown station selection mode")
    def record(row):
        return {"latitude": float(row[lat_name]), "longitude": float(row[lon_name]),
                "upstream_area_km2": float(row.upstream_area_km2), "distance_km": float(row.distance_km),
                "relative_area_error": float(row.relative_area_error)}
    accepted = bool(np.isfinite(chosen.upstream_area_km2) and chosen.upstream_area_km2 > 0 and
                    chosen.relative_area_error <= station["relative_area_tolerance"])
    return {"passed": accepted, "selection": station["selection"], "reference_area_km2": area_km2,
            "reference_area_source": station["area_source"], "selected": record(chosen),
            "geographically_nearest": record(nearest), "nearby_area_matches": [record(row) for _, row in valid.head(20).iterrows()],
            "area_tolerance": station["relative_area_tolerance"], "note": "Area agreement alone does not prove river-network identity."}


def auxiliary(cfg):
    directory = resolve(cfg, cfg["download"]["raw_dir"])
    directory.mkdir(parents=True, exist_ok=True)
    target = directory / "uparea_glofas_v4_0.nc"
    if not target.exists():
        part = target.with_suffix(".part")
        with requests.get(cfg["download"]["auxiliary_url"], stream=True, timeout=(15, 90)) as response:
            response.raise_for_status()
            with part.open("wb") as f:
                for block in response.iter_content(1024*1024): f.write(block)
        with xr.open_dataset(part, engine="netcdf4") as ds:
            if not ds.data_vars: raise ValueError("Empty auxiliary download")
        part.replace(target)
    metadata = json.loads(resolve(cfg, cfg["catchment_metadata"]).read_text())
    area = cfg["station"]["upstream_area_km2"] or metadata["catchment_area_km2"]
    with xr.open_dataset(target) as ds:
        result = select_cell(ds, cfg["station"], area)
    result.update({"system_version": cfg["download"]["system_version"], "auxiliary_sha256": sha(target),
                   "source_url": cfg["download"]["auxiliary_url"]})
    save_json(resolve(cfg, cfg["download"]["grid_report"]), result)
    if not result["passed"]: raise ValueError("Grid upstream-area check FAILED; see data/grid_cell.json")
    return result


def snapshot_catalogue(cfg):
    target = resolve(cfg, "data/catalogue")
    target.mkdir(parents=True, exist_ok=True)
    result = {}
    for kind in ["forecast", "reforecast"]:
        name = f"cems-glofas-{kind}"
        url = f"{cfg['download']['api_url']}/catalogue/v1/collections/{name}"
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        collection = response.json()
        save_json(target / f"{kind}_collection.json", collection)
        for rel in ["form", "constraints", "messages"]:
            link = next((x["href"] for x in collection["links"] if x["rel"] == rel), None)
            if link:
                r = requests.get(link, timeout=60)
                if r.ok: save_json(target / f"{kind}_{rel}.json", r.json())
        result[kind] = collection
    return result


def request_for(cfg, kind, year, month, days, cell):
    request = {"system_version": cfg["download"]["system_version"] if kind == "reforecast" else cfg["download"].get("forecast_system_version", "operational"), "hydrological_model": cfg["download"]["hydrological_model"],
               "product_type": (["control_reforecast", "ensemble_perturbed_reforecast"] if kind == "reforecast" else
                                ["control_forecast", "ensemble_perturbed_forecasts"]),
               "variable": "river_discharge_in_the_last_24_hours", "data_format": "grib2",
               "download_format": "unarchived", "leadtime_hour": [str(24*d) for d in range(1, cfg["download"]["max_lead_days"]+1)],
               "area": [cell["latitude"], cell["longitude"], cell["latitude"], cell["longitude"]]}
    prefix = "h" if kind == "reforecast" else ""
    request.update({prefix+"year": str(year), prefix+"month": f"{month:02d}", prefix+"day": [f"{d:02d}" for d in days]})
    return request


def plan(cfg, grid):
    jobs = []
    cell = grid["selected"]
    for year in cfg["download"]["reforecast_years"]:
        for month in cfg["download"]["reforecast_months"]:
            # Historical weekdays need not match the Monday/Thursday reference cycle.
            # Request the calendar month; EWDS constraints determine actual reference dates.
            days = list(range(1, calendar.monthrange(year, month)[1]+1))
            jobs.append({"kind": "reforecast", "dataset": "cems-glofas-reforecast",
                         "file": f"reforecast_{year}_{month:02d}.grib", "request": request_for(cfg, "reforecast", year, month, days, cell)})
    for text in cfg["download"]["forecast_dates"]:
        d = pd.Timestamp(text)
        jobs.append({"kind": "forecast", "dataset": "cems-glofas-forecast", "file": f"forecast_{d:%Y%m%d}.grib",
                     "request": request_for(cfg, "forecast", d.year, d.month, [d.day], cell)})
    # Use live provider constraints, not guessed weekdays, product names or dates.
    checked = []
    unavailable = []
    for job in jobs:
        constraint_path = resolve(cfg, f"data/catalogue/{job['kind']}_constraints.json")
        if constraint_path.exists():
            constraints = json.loads(constraint_path.read_text())
            request = job["request"]
            prefix = "h" if job["kind"] == "reforecast" else ""
            possible = []
            for day in request[prefix+"day"]:
                good = True
                for product in request["product_type"]:
                    matched = [c for c in constraints if all(
                        value in c.get(key, [value]) for key, value in {
                            "system_version": request["system_version"], "hydrological_model": request["hydrological_model"],
                            "product_type": product, "variable": request["variable"], prefix+"year": request[prefix+"year"],
                            prefix+"month": request[prefix+"month"], prefix+"day": day}.items())]
                    if not matched or not any(set(request["leadtime_hour"]).issubset(c.get("leadtime_hour", [])) for c in matched):
                        good = False
                if good: possible.append(day)
            if not possible:
                unavailable.append({"file": job["file"], "reason": "No requested issue supports all configured leads/products in live constraints"})
                continue
            request[prefix+"day"] = possible
            job["constraints_checked"] = True
        else:
            raise ValueError("Snapshot the live catalogue before generating a download plan")
        checked.append(job)
    jobs = checked
    save_json(resolve(cfg, "data/download_plan.json"), {"jobs": jobs, "unavailable": unavailable, "cell": cell,
              "warning": "Check live EWDS constraints. Some dates/leads may not exist; missing leads are never invented."})
    return jobs


def credentials(cfg):
    path = cfg["download"].get("credential_file")
    path = Path(path).expanduser() if path else Path(os.environ.get("CDSAPI_RC", Path.home()/".cdsapirc"))
    # Report only existence; never print or save a token.
    return {"credential_file": str(path), "file_exists": path.exists(), "environment_key_present": bool(os.environ.get("CDSAPI_KEY"))}


def retrieve(cfg, jobs, kind, limit=None):
    state = credentials(cfg)
    if not state["file_exists"] and not state["environment_key_present"]:
        raise RuntimeError("EWDS credentials missing. Configure a local .cdsapirc or CDSAPI_KEY; do not paste secrets into chat.")
    if cfg["download"].get("credential_file"): os.environ["CDSAPI_RC"] = str(cfg["download"]["credential_file"])
    import cdsapi
    client = cdsapi.Client(url=cfg["download"]["api_url"], quiet=True, debug=False)
    chosen = [j for j in jobs if j["kind"] == kind]
    if limit: chosen = chosen[:limit]
    receipts = []
    for job in chosen:
        path = resolve(cfg, cfg["download"]["raw_dir"]) / job["file"]
        if not path.exists():
            part = path.with_suffix(".part")
            client.retrieve(job["dataset"], job["request"], str(part))
            if part.stat().st_size == 0: raise ValueError("Empty GloFAS retrieval")
            part.replace(path)
        receipt = {"dataset": job["dataset"], "request": job["request"], "file": str(path), "sha256": sha(path),
                   "kind": kind, "system_version": cfg["download"]["system_version"]}
        save_json(path.with_suffix(".receipt.json"), receipt)
        receipts.append(receipt)
    return receipts


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.yaml")))
    parser.add_argument("--action", choices=["auxiliary", "catalogue", "plan", "forecast", "reforecast"], default="plan")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    cfg = load_config(args.config)
    if args.action == "catalogue": snapshot_catalogue(cfg)
    else:
        grid = auxiliary(cfg)
        jobs = plan(cfg, grid)
        if args.action in ["forecast", "reforecast"]: retrieve(cfg, jobs, args.action, args.limit)
        print(json.dumps(grid, indent=2))
