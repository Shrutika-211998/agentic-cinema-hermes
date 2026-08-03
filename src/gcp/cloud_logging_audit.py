"""Cloud Logging audit sink."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from ..gcp.config import project_id, use_cloud_logging


class CloudAuditLog:
    """Writes structured audit entries to Cloud Logging (+ optional local mirror)."""

    def __init__(self, local_path: Optional[str] = None):
        self.local_path = local_path
        self._logger = None
        if use_cloud_logging() and project_id():
            try:
                from google.cloud import logging as cloud_logging

                client = cloud_logging.Client(project=project_id())
                client.setup_logging()
                self._logger = client.logger("second-unit-audit")
            except Exception:
                self._logger = None
        self._std = logging.getLogger("second_unit.audit")

    def new_trail_id(self) -> str:
        import uuid

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
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": stage,
            "decision": decision,
            "actor": actor,
            "audit_trail_id": audit_trail_id or "",
            "run_id": run_id or "",
            "payload": payload or {},
            "service": "second-unit",
        }
        if self._logger is not None:
            try:
                self._logger.log_struct(entry, severity="INFO")
            except Exception:
                pass
        self._std.info(json.dumps(entry, default=str))
        if self.local_path:
            try:
                with open(self.local_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry, ensure_ascii=False) + "\n")
            except Exception:
                pass
        return {"ack": True, "entry": entry}

    def read_for_run(self, run_id: str, limit: int = 200) -> list[dict[str, Any]]:
        # Cloud Logging query is eventual; prefer local mirror for demo reads
        if not self.local_path:
            return []
        out = []
        try:
            with open(self.local_path, encoding="utf-8") as f:
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
        except FileNotFoundError:
            return []
        return out

    def read_trail(self, audit_trail_id: str, limit: int = 200) -> list[dict[str, Any]]:
        if not self.local_path:
            return []
        out = []
        try:
            with open(self.local_path, encoding="utf-8") as f:
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
        except FileNotFoundError:
            return []
        return out
