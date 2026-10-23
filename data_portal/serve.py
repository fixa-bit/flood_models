"""Rebuild the portal and serve it on this computer only."""
import argparse
import functools
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer

from build_dashboard import DIST, build


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8787)
    parser.add_argument("--no-build", action="store_true", help="Use the current saved snapshot")
    args = parser.parse_args()
    if not args.no_build:
        build()
    handler = functools.partial(SimpleHTTPRequestHandler, directory=str(DIST))
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler)
    print(f"Flood Data Observatory: http://127.0.0.1:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
