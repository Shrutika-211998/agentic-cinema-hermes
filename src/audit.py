"""Structured audit trail — Cloud Logging seam."""

from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AuditLog:
    def __init__(self, path: Optional[str | Path] = None):
        root = Path(__file__).resolve().parent.parent / "data"
        self.path = Path(path or root / "audit_log.jsonl")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def new_trail_id(self) -> str:
        return f"audit_{uuid.uuid4().hex[:12]}"

    def write_audit_log(
        self,
        stage: str,
        decision: str,
        actor: str,
        payload: Optional[dict[str, Any]] = None,
        audit_trail_id: Optional[str] = None,
        run_id: Optional[str] = None,
    ) -> dict[str, Any]:
        entry = {
            "ts": now_iso(),
            "stage": stage,
            "decision": decision,
            "actor": actor,
            "audit_trail_id": audit_trail_id or "",
            "run_id": run_id or "",
            "payload": payload or {},
        }
        line = json.dumps(entry, ensure_ascii=False)
        with self._lock:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(line + "\n")
        return {"ack": True, "entry": entry}

    def read_trail(self, audit_trail_id: str, limit: int = 200) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self._lock:
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("audit_trail_id") == audit_trail_id:
                        out.append(row)
                        if len(out) >= limit:
                            break
        return out

    def read_for_run(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        if not self.path.exists():
            return []
        out: list[dict[str, Any]] = []
        with self._lock:
            with self.path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if row.get("run_id") == run_id:
                        out.append(row)
                        if len(out) >= limit:
                            break
        return out
