"""Rebuild the portal and serve it on this computer only."""
import argparse
import functools
import threading
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from build_dashboard import DIST, MODEL, PROCESSED, build, station_names
from build_models import build_models, patch_manifest, watch_fingerprint


IGNORED_SUFFIXES = {".pyc", ".tmp", ".log"}
IGNORED_PARTS = {"__pycache__", ".venv"}


def source_fingerprint():
    """Fast metadata fingerprint for source files, excluding portal build outputs."""
    roots = (MODEL / "raw", PROCESSED)
    values = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file() or path.suffix.lower() in IGNORED_SUFFIXES or IGNORED_PARTS.intersection(path.parts):
                continue
            try:
                stat = path.stat()
                values.append((str(path), stat.st_size, stat.st_mtime_ns))
            except OSError:
                continue
    return tuple(values)


def watch_sources(stop_event, interval):
    """Rebuild only after files stop changing briefly.

    Dataset changes rebuild the whole snapshot (which also rescores the models).
    Changes to saved model predictions, run folders or the model catalog rescore
    the models only, which is much faster.
    """
    probes = {"data": source_fingerprint, "models": watch_fingerprint}
    current = {name: probe() for name, probe in probes.items()}
    candidate = dict.fromkeys(probes)
    since = dict.fromkeys(probes, 0.0)
    retry_after = 0.0
    while not stop_event.wait(interval):
        now = time.monotonic()
        latest, ready = {}, []
        for name, probe in probes.items():
            latest[name] = probe()
            if latest[name] == current[name]:
                candidate[name] = None
            elif latest[name] != candidate[name]:
                candidate[name], since[name] = latest[name], now
            elif now - since[name] >= max(2.0, interval * 2) and now >= retry_after:
                ready.append(name)
        if not ready:
            continue
        try:
            if "data" in ready:
                print("Source data changed; rebuilding portal snapshot...", flush=True)
                build()
                refreshed = list(probes)
                print("Portal snapshot refreshed. Open pages will reload the new data automatically.", flush=True)
            else:
                print("Model results changed; rescoring models...", flush=True)
                summary = build_models(stations=station_names())
                if not summary.get("reused"):
                    patch_manifest(summary)
                changes = summary.get("changes") or []
                described = ", ".join(f"{change['name']} v{change['version']}" for change in changes[:5])
                print(f"Models rescored{': new versions ' + described if described else ''}. Open pages will update automatically.", flush=True)
                refreshed = ["models"]
            for name in refreshed:
                current[name] = latest[name]
                candidate[name] = None
            retry_after = 0.0
        except Exception as error:
            print(f"Portal refresh failed; keeping the previous snapshot: {error}", flush=True)
            retry_after = time.monotonic() + 30.0


class LocalPortalHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        # This is a changing local workspace, so do not retain stale navigation
        # or scripts across edits and server restarts.
        self.send_header("Cache-Control", "no-store")
        super().end_headers()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-build", action="store_true", help="Use the current saved snapshot")
    parser.add_argument("--no-watch", action="store_true", help="Disable automatic data-folder monitoring")
    parser.add_argument("--watch-interval", type=float, default=4.0, help="Seconds between local change checks")
    args = parser.parse_args()
    if not args.no_build:
        build()
    stop_event = threading.Event()
    watcher = None
    if not args.no_watch:
        watcher = threading.Thread(target=watch_sources, args=(stop_event, max(1.0, args.watch_interval)), daemon=True)
        watcher.start()
    handler = functools.partial(LocalPortalHandler, directory=str(DIST))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Flood Data Observatory: http://127.0.0.1:{args.port}", flush=True)
    if watcher:
        print(f"Watching {MODEL / 'raw'}, {PROCESSED} and saved model results; Ctrl+C stops the portal and watcher.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stop_event.set()
        server.server_close()


if __name__ == "__main__":
    main()
