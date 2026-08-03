"""HTTP API for Second Unit studio dashboard."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs, urlparse

from .factory import build_api


API = build_api()
ROOT = Path(__file__).resolve().parent.parent


class Handler(BaseHTTPRequestHandler):
    server_version = "SecondUnit/0.1"

    def log_message(self, fmt: str, *args: Any) -> None:
        # quieter default
        print(f"[http] {self.address_string()} {fmt % args}")

    def _cors(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Principal")

    def _json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload, indent=2).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            data = json.loads(raw.decode("utf-8"))
            return data if isinstance(data, dict) else {}
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self) -> None:  # noqa: N802
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)

        if path in ("/api/health", "/health"):
            return self._json(200, API.health())
        if path == "/api/principals":
            return self._json(200, {"principals": API.list_principals()})
        if path == "/api/runs":
            return self._json(200, {"runs": API.list_runs()})
        if path == "/api/runs/active":
            run = API.get_active_run()
            return self._json(200, {"run": run})
        if path.startswith("/api/runs/") and path.endswith("/audit"):
            run_id = path[len("/api/runs/") : -len("/audit")]
            return self._json(200, {"run_id": run_id, "entries": API.get_audit(run_id)})
        if path.startswith("/api/runs/"):
            run_id = path[len("/api/runs/") :]
            run = API.get_run(run_id)
            if not run:
                return self._json(404, {"error": "not_found"})
            return self._json(200, {"run": run})
        if path == "/api/archive":
            return self._json(200, {"assets": API.list_archive()})
        if path == "/api/archive/search":
            concept = (qs.get("q") or qs.get("concept") or [""])[0]
            mood = qs.get("mood") or []
            hits = API.archive_search(concept=concept, mood=mood)
            return self._json(200, {"hits": hits})
        if path == "/api/rights/summary":
            return self._json(200, API.rights_summary())
        if path.startswith("/api/rights/check/"):
            asset_id = path[len("/api/rights/check/") :]
            platform = (qs.get("platform") or ["instagram"])[0]
            territory = (qs.get("territory") or ["US"])[0]
            return self._json(200, API.check_rights(asset_id, platform, territory))

        # Static files for single-process convenience
        if path == "/" or path == "/index.html":
            return self._file(ROOT / "index.html", "text/html; charset=utf-8")
        if path == "/styles.css":
            return self._file(ROOT / "styles.css", "text/css; charset=utf-8")
        if path == "/app.js":
            return self._file(ROOT / "app.js", "application/javascript; charset=utf-8")

        return self._json(404, {"error": "not_found", "path": path})

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        body = self._read_json()

        if path == "/api/productions":
            result = API.start_production(
                creative_brief=body.get("creative_brief") or body.get("brief") or "",
                submitter=body.get("submitter")
                or self.headers.get("X-Principal")
                or "marketing@studio.demo",
                defaults=body.get("defaults"),
            )
            code = 400 if result.get("error") else 201
            return self._json(code, result if result.get("error") else {"run": result})

        if path.startswith("/api/runs/") and path.endswith("/approve"):
            run_id = path[len("/api/runs/") : -len("/approve")]
            principal = (
                body.get("principal")
                or self.headers.get("X-Principal")
                or ""
            )
            if not principal:
                return self._json(400, {"error": "validation", "message": "principal required"})
            result = API.approve_run(run_id, principal)
            code = 403 if result.get("ok") is False else (404 if result.get("error") == "not_found" else 200)
            return self._json(code, result)

        if path.startswith("/api/runs/") and path.endswith("/reject"):
            run_id = path[len("/api/runs/") : -len("/reject")]
            principal = body.get("principal") or self.headers.get("X-Principal") or "unknown"
            result = API.reject_run(run_id, principal, reason=body.get("reason") or "")
            code = 404 if result.get("error") == "not_found" else 200
            return self._json(code, result)

        if path.startswith("/api/runs/") and path.endswith("/deliver"):
            run_id = path[len("/api/runs/") : -len("/deliver")]
            result = API.deliver_run(run_id)
            code = 404 if result.get("error") == "not_found" else 200
            return self._json(code, result)

        if path == "/api/admin/reset":
            return self._json(200, API.reset_store())

        return self._json(404, {"error": "not_found", "path": path})

    def _file(self, path: Path, content_type: str) -> None:
        if not path.exists():
            return self._json(404, {"error": "not_found", "file": str(path)})
        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self._cors()
        self.end_headers()
        self.wfile.write(data)


def main(host: str = "0.0.0.0", port: int = 8080) -> None:
    server = ThreadingHTTPServer((host, port), Handler)
    print(f"Second Unit studio API + dashboard on http://{host}:{port}")
    print(f"  health: http://{host}:{port}/api/health")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    import os

    main(port=int(os.getenv("PORT", "8080")))
