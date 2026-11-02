"""Persistent, resumable retrieval with at most three EWDS requests in flight."""
import argparse
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
import time
import traceback
import cdsapi
from .common import load_config, resolve, save_json, sha
from .download import credentials


def job_paths(cfg, job):
    path = resolve(cfg, cfg["download"]["raw_dir"]) / job["file"]
    return path, path.with_suffix(".job.json"), path.with_suffix(".receipt.json")


def get_one(cfg, job):
    path, job_path, receipt_path = job_paths(cfg, job)
    if path.exists() and receipt_path.exists():
        receipt = json.loads(receipt_path.read_text())
        if receipt["sha256"] != sha(path): raise ValueError("Existing raw file checksum mismatch")
        return path
    if cfg["download"].get("credential_file"):
        os.environ["CDSAPI_RC"] = str(cfg["download"]["credential_file"])
    client = cdsapi.Client(url=cfg["download"]["api_url"], quiet=True, debug=False, timeout=60, retry_max=3, sleep_max=30).client
    if job_path.exists():
        metadata = json.loads(job_path.read_text())
        if metadata["request"] != job["request"]: raise ValueError("Saved provider job request differs from current plan")
        remote = client.get_remote(metadata["request_id"])
    else:
        remote = client.submit(collection_id=job["dataset"], request=job["request"])
        metadata = {"request_id": remote.request_id, "dataset": job["dataset"], "request": job["request"],
                    "submitted_utc": datetime.now(timezone.utc).isoformat()}
        save_json(job_path, metadata)
    print(f"Submitted/resumed {job['file']} ({remote.request_id})", flush=True)
    # Poll independently of the assistant turn. Provider IDs are persisted before
    # waiting, so interruption never requires submitting duplicate requests.
    while True:
        state = remote.status
        if state in ["successful", "completed"]: break
        if state in ["failed", "dismissed", "deleted"]:
            metadata["status"] = state
            save_json(job_path, metadata)
            raise RuntimeError(f"EWDS job {remote.request_id} ended as {state}")
        metadata["status"], metadata["last_checked_utc"] = state, datetime.now(timezone.utc).isoformat()
        save_json(job_path, metadata)
        time.sleep(30)
    part = path.with_suffix(".part")
    remote.download(str(part))
    if part.stat().st_size == 0: raise ValueError("Empty GloFAS download")
    part.replace(path)
    save_json(receipt_path, {"dataset": job["dataset"], "request": job["request"], "file": str(path), "sha256": sha(path),
        "kind": job["kind"], "system_version": cfg["download"]["system_version"], "provider_request_id": remote.request_id})
    metadata["status"] = "downloaded"
    save_json(job_path, metadata)
    print(f"Downloaded {job['file']}: {path.stat().st_size:,} bytes", flush=True)
    return path


def work(cfg, workers=3, limit=None, train_after=True):
    root = cfg["_root"]
    jobs = json.loads(resolve(cfg, "data/download_plan.json").read_text())["jobs"]
    if limit: jobs = jobs[:limit]
    if not credentials(cfg)["file_exists"] and not credentials(cfg)["environment_key_present"]:
        raise RuntimeError("Configure local EWDS credentials before starting the worker")
    save_json(root / "worker.pid.json", {"pid": os.getpid(), "started_utc": datetime.now(timezone.utc).isoformat()})
    pending = [job for job in jobs if not all(p.exists() for p in [job_paths(cfg, job)[0], job_paths(cfg, job)[2]])]
    completed, failures, active = len(jobs)-len(pending), [], {}
    with ThreadPoolExecutor(max_workers=min(workers, 3)) as pool:
        while pending or active:
            while pending and len(active) < min(workers, 3):
                job = pending.pop(0)
                active[pool.submit(get_one, cfg, job)] = job
            ready, _ = wait(active, timeout=30, return_when=FIRST_COMPLETED)
            for future in ready:
                job = active.pop(future)
                try:
                    future.result()
                    completed += 1
                except Exception as error:
                    failures.append({"file": job["file"], "error": str(error)[:800]})
                    print(f"Retrieval failed for {job['file']}: {type(error).__name__}: {error}", flush=True)
            state = {"phase": "retrieval", "completed": completed, "total": len(jobs),
                     "active": [j["file"] for j in active.values()], "pending": len(pending), "failures": failures,
                     "heartbeat_utc": datetime.now(timezone.utc).isoformat(), "training_complete": False}
            save_json(root / "WORKER_STATUS.json", state)
            print(f"Progress: {completed}/{len(jobs)} downloaded; {len(active)} active; {len(failures)} failed", flush=True)
    if failures:
        raise RuntimeError("Some retrievals failed. Inspect WORKER_STATUS.json and resume after addressing the provider error.")
    if train_after and not limit:
        from .run_pipeline import run
        save_json(root / "WORKER_STATUS.json", {"phase": "prepare_and_train", "downloaded": completed, "training_complete": False})
        run(cfg, "prepare")
        run(cfg, "train", resume=True)
        run(cfg, "forecast")
        save_json(root / "WORKER_STATUS.json", {"phase": "complete", "downloaded": completed, "training_complete": True,
                  "finished_utc": datetime.now(timezone.utc).isoformat()})


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default=str(Path(__file__).with_name("config.yaml")))
    parser.add_argument("--workers", type=int, default=3)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-train", action="store_true")
    args = parser.parse_args()
    cfg = load_config(args.config)
    original_out, original_err = sys.stdout, sys.stderr
    with (cfg["_root"] / "worker.log").open("a", encoding="utf-8") as log:
        class Tee:
            def __init__(self, stream): self.stream = stream
            def write(self, value): self.stream.write(value); log.write(value); log.flush()
            def flush(self): self.stream.flush(); log.flush()
        sys.stdout, sys.stderr = Tee(original_out), Tee(original_err)
        try:
            work(cfg, args.workers, args.limit, not args.no_train)
        except Exception:
            traceback.print_exc()
            save_json(cfg["_root"] / "WORKER_ERROR.json", {"message": traceback.format_exc()[-2500:]})
            raise
        finally:
            sys.stdout, sys.stderr = original_out, original_err
