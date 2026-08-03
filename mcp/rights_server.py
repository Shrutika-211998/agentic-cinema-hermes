"""
Rights & Clearance MCP server (custom partner-style tools).

Runnable as a plain HTTP/JSON tool host for local demos. In production, wrap
these same functions with FastMCP / the official MCP Python SDK and point ADK
at the MCP endpoint.

Tools:
  - check_clip_rights
  - find_cleared_alternative
  - get_license
  - list_restricted
  - register_clearance
  - get_territory_rules
"""

from __future__ import annotations

import json
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.rights import RightsMCP  # noqa: E402

RIGHTS = RightsMCP()

TOOLS = {
    "check_clip_rights": {
        "description": "Check whether an asset is licensed for a platform and territory. Returns cleared|restricted|unknown.",
        "readOnlyHint": True,
        "idempotentHint": True,
    },
    "find_cleared_alternative": {
        "description": "Find alternate assets cleared for the brief's platform/territory when a clip is restricted/unknown.",
        "readOnlyHint": True,
        "idempotentHint": True,
    },
    "get_license": {
        "description": "Fetch the full rights ledger record for an asset_id.",
        "readOnlyHint": True,
        "idempotentHint": True,
    },
    "list_restricted": {
        "description": "List restricted or unknown assets, optionally filtered by platform/territory.",
        "readOnlyHint": True,
        "idempotentHint": True,
    },
    "register_clearance": {
        "description": "Register or update a clearance record in the rights ledger.",
        "readOnlyHint": False,
        "idempotentHint": False,
    },
    "get_territory_rules": {
        "description": "Load territory rights policy rules for clearance reasoning.",
        "readOnlyHint": True,
        "idempotentHint": True,
    },
}


def dispatch(name: str, args: dict[str, Any]) -> Any:
    if name == "check_clip_rights":
        return RIGHTS.check_clip_rights(
            args.get("asset_id") or "",
            args.get("platform") or "instagram",
            args.get("territory") or "US",
            as_of=args.get("as_of"),
        )
    if name == "find_cleared_alternative":
        return RIGHTS.find_cleared_alternative(
            args.get("asset_id") or "",
            args.get("brief_params") or {},
            limit=int(args.get("limit") or 5),
        )
    if name == "get_license":
        return RIGHTS.get_license(args.get("asset_id") or "")
    if name == "list_restricted":
        return RIGHTS.list_restricted(args.get("platform"), args.get("territory"))
    if name == "register_clearance":
        return RIGHTS.register_clearance(args.get("asset_id") or "", args.get("license_payload") or args)
    if name == "get_territory_rules":
        return RIGHTS.get_territory_rules(args.get("territory") or "US")
    return {"error": "unknown_tool", "message": f"Unknown tool '{name}'"}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        print(f"[rights-mcp] {fmt % args}")

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
        path = urlparse(self.path).path.rstrip("/") or "/"
        if path in ("/", "/health"):
            return self._json(200, {"status": "ok", "server": "rights-clearance-mcp", "tools": list(TOOLS)})
        if path == "/tools":
            return self._json(200, {"tools": TOOLS})
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
            # MCP-ish structured envelope
            return self._json(
                200,
                {
                    "tool": name,
                    "structuredContent": result,
                    "isError": isinstance(result, dict) and bool(result.get("error")),
                },
            )
        return self._json(404, {"error": "not_found"})


def main(host: str = "0.0.0.0", port: int = 8091) -> None:
    print(f"Rights & Clearance MCP on http://{host}:{port}")
    print("  GET  /tools")
    print("  POST /tools/call  {\"name\": \"check_clip_rights\", \"arguments\": {...}}")
    ThreadingHTTPServer((host, port), Handler).serve_forever()


if __name__ == "__main__":
    import os

    main(port=int(os.getenv("PORT", "8091")))
