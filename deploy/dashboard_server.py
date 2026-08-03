"""Static dashboard server for Cloud Run (separate from API)."""

from __future__ import annotations

import os
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


# In container: files live next to this script (/app)
ROOT = Path(__file__).resolve().parent
os.chdir(ROOT)


class Handler(SimpleHTTPRequestHandler):
    extensions_map = {
        **getattr(SimpleHTTPRequestHandler, "extensions_map", {}),
        ".js": "application/javascript",
        ".css": "text/css",
        ".html": "text/html",
        ".json": "application/json",
    }

    def do_GET(self):
        if self.path in ("/", ""):
            self.path = "/index.html"
        if self.path in ("/trailer", "/trailer/"):
            self.path = "/trailer.html"
        return SimpleHTTPRequestHandler.do_GET(self)

    def end_headers(self):
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Access-Control-Allow-Origin", "*")
        super().end_headers()


def main():
    port = int(os.getenv("PORT", "8080"))
    print(f"Second Unit dashboard on :{port} root={ROOT}")
    ThreadingHTTPServer(("0.0.0.0", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
