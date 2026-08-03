"""Partner Archive MCP server — hackathon-required partner-style integration.

Exposes archive_search / archive_get_asset over HTTP + MCP-compatible JSON.
Swap the backend to Iconik / Perfect Memory / VionLabs when track credentials land.
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.archive import ArchiveMCP  # noqa: E402

ARCHIVE = ArchiveMCP()

TOOLS = {
    "archive_search": {
        "description": "Search the media archive by concept, mood, entities, time range.",
        "readOnlyHint": True,
        "openWorldHint": True,
    },
    "archive_get_asset": {
        "description": "Get full asset metadata by asset_id. Never invent IDs.",
        "readOnlyHint": True,
    },
    "archive_list": {
        "description": "List seeded archive assets (demo catalog).",
        "readOnlyHint": True,
    },
}


def dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "archive_search":
        mood = args.get("mood") or []
        if isinstance(mood, str):
            mood = [m.strip() for m in mood.split(",") if m.strip()]
        return ARCHIVE.archive_search(
            concept=args.get("concept") or args.get("q") or "",
            mood=mood,
            entities=args.get("entities") or [],
            time_range=args.get("time_range"),
            limit=int(args.get("limit") or 24),
        )
    if name == "archive_get_asset":
        return ARCHIVE.archive_get_asset(args.get("asset_id") or "")
    if name == "archive_list":
        return ARCHIVE.list_assets()
    return {"error": "unknown_tool", "name": name}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[archive-mcp] {fmt % args}")

    def _json(self, code: int, payload: Any) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"
        qs = parse_qs(parsed.query)
        if path in ("/", "/health"):
            return self._json(
                200,
                {
                    "status": "ok",
                    "server": "partner-archive-mcp",
                    "partner_category": "archive-intelligence",
                    "compatible_with": ["Iconik/Backlight", "Perfect Memory", "VionLabs"],
                    "tools": list(TOOLS),
                    "asset_count": len(ARCHIVE.list_assets()),
                },
            )
        if path == "/tools":
            return self._json(200, {"tools": TOOLS})
        if path == "/search":
            hits = dispatch(
                "archive_search",
                {
                    "concept": (qs.get("q") or qs.get("concept") or [""])[0],
                    "mood": (qs.get("mood") or [""])[0],
                },
            )
            return self._json(200, {"hits": hits})
        return self._json(404, {"error": "not_found"})

    def do_POST(self):
        path = urlparse(self.path).path.rstrip("/") or "/"
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b"{}"
        try:
            body = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            return self._json(400, {"error": "invalid_json"})
        if path == "/tools/call":
            name = body.get("name") or body.get("tool")
            args = body.get("arguments") or body.get("args") or {}
            if name not in TOOLS:
                return self._json(404, {"error": "unknown_tool", "name": name})
            result = dispatch(name, args if isinstance(args, dict) else {})
            return self._json(
                200,
                {
                    "tool": name,
                    "structuredContent": result,
                    "isError": isinstance(result, dict) and bool(result.get("error")),
                },
            )
        return self._json(404, {"error": "not_found"})


def main(host: str = "0.0.0.0", port: int = 8090) -> None:
    print(f"Partner Archive MCP on http://{host}:{port}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    import os

    main(port=int(os.getenv("PORT", "8090")))
