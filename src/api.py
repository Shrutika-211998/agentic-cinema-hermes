"""Second Unit service facade — persistent runs + crew orchestration."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Optional

from .archive import ArchiveMCP
from .audit import AuditLog, now_iso
from .iam import IAMService
from .models import ProductionRun
from .pipeline import SecondUnitPipeline
from .rights import RightsMCP


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_STORE = ROOT / "data" / "store.json"


class SecondUnitAPI:
    def __init__(
        self,
        data_path: Optional[str | Path] = None,
        archive: Optional[ArchiveMCP] = None,
        rights: Optional[RightsMCP] = None,
        iam: Optional[IAMService] = None,
        audit: Optional[AuditLog] = None,
        output_dir: Optional[str | Path] = None,
    ):
        self.data_path = Path(data_path or os.getenv("SECOND_UNIT_DATA", str(DEFAULT_STORE)))
        self.data_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()
        self.archive = archive or ArchiveMCP()
        self.rights = rights or RightsMCP()
        self.iam = iam or IAMService()
        self.audit = audit or AuditLog(self.data_path.parent / "audit_log.jsonl")
        self.pipeline = SecondUnitPipeline(
            archive=self.archive,
            rights=self.rights,
            iam=self.iam,
            audit=self.audit,
            output_dir=str(output_dir) if output_dir else None,
        )
        self._ensure_store()

    def _ensure_store(self) -> None:
        if not self.data_path.exists():
            self._write_store({"runs": {}, "active_run_id": None})

    def _read_store(self) -> dict[str, Any]:
        if not self.data_path.exists():
            return {"runs": {}, "active_run_id": None}
        return json.loads(self.data_path.read_text(encoding="utf-8"))

    def _write_store(self, data: dict[str, Any]) -> None:
        tmp = self.data_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(self.data_path)

    def _save_run(self, run: ProductionRun) -> ProductionRun:
        with self._lock:
            store = self._read_store()
            store.setdefault("runs", {})[run.run_id] = run.to_dict()
            store["active_run_id"] = run.run_id
            self._write_store(store)
        return run

    def _get_run(self, run_id: str) -> Optional[ProductionRun]:
        with self._lock:
            store = self._read_store()
            raw = (store.get("runs") or {}).get(run_id)
            if not raw:
                return None
            return ProductionRun.from_dict(raw)

    # ── public API ───────────────────────────────────────────────────────

    def health(self) -> dict[str, Any]:
        return {
            "status": "ok",
            "service": "second-unit",
            "version": "0.1.0",
            "provider": os.getenv("VERTEX_AI_ENABLED", "false").lower() == "true"
            and "vertex-gemini"
            or "local-deterministic",
            "agents": [
                "director",
                "researcher_agent",
                "editor_agent",
                "clearance_officer_agent",
                "distributor_agent",
            ],
            "governance": {
                "iam_roles": [
                    "roles/secondunit.briefSubmitter",
                    "roles/secondunit.clearanceReviewer",
                    "roles/secondunit.releasingProducer",
                ],
                "publish_gate": "before_tool_callback",
            },
        }

    def list_principals(self) -> list[dict[str, Any]]:
        return self.iam.list_principals()

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            store = self._read_store()
            runs = list((store.get("runs") or {}).values())
        runs.sort(key=lambda r: r.get("updated_at") or r.get("created_at") or "", reverse=True)
        return runs[:limit]

    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        run = self._get_run(run_id)
        return run.to_dict() if run else None

    def get_active_run(self) -> Optional[dict[str, Any]]:
        with self._lock:
            store = self._read_store()
            rid = store.get("active_run_id")
        if not rid:
            return None
        return self.get_run(rid)

    def start_production(
        self,
        creative_brief: str,
        submitter: str = "marketing@studio.demo",
        defaults: Optional[dict] = None,
    ) -> dict[str, Any]:
        brief = (creative_brief or "").strip()
        if not brief:
            return {"error": "validation", "message": "creative_brief is required"}
        if not self.iam.can_submit_brief(submitter):
            return {
                "error": "unauthorized",
                "message": f"{submitter} cannot submit briefs",
            }

        run = self.pipeline.run_until_approval_gate(brief, defaults=defaults)
        # Tag submitter on first event context
        run.events.insert(
            0,
            {
                "ts": now_iso(),
                "stage": "intake",
                "agent": "director",
                "message": f"brief_received_from:{submitter}",
                "payload": {"submitter": submitter},
            },
        )
        self._save_run(run)
        return run.to_dict()

    def approve_run(self, run_id: str, principal: str) -> dict[str, Any]:
        run = self._get_run(run_id)
        if not run:
            return {"error": "not_found", "message": f"run {run_id} not found"}
        run, result = self.pipeline.approve(run, principal)
        self._save_run(run)
        if not result.get("ok"):
            return {
                "ok": False,
                "run": run.to_dict(),
                "reason": result.get("reason"),
                "auth": result.get("auth"),
            }
        # Auto-deliver after successful approval (demo flow)
        run = self.pipeline.complete_delivery(run)
        self._save_run(run)
        return {"ok": True, "run": run.to_dict(), "auth": result.get("auth")}

    def reject_run(self, run_id: str, principal: str, reason: str = "") -> dict[str, Any]:
        run = self._get_run(run_id)
        if not run:
            return {"error": "not_found", "message": f"run {run_id} not found"}
        run = self.pipeline.reject(run, principal, reason=reason)
        self._save_run(run)
        return {"ok": True, "run": run.to_dict()}

    def deliver_run(self, run_id: str) -> dict[str, Any]:
        run = self._get_run(run_id)
        if not run:
            return {"error": "not_found", "message": f"run {run_id} not found"}
        run = self.pipeline.complete_delivery(run)
        self._save_run(run)
        return run.to_dict()

    def get_audit(self, run_id: str) -> list[dict[str, Any]]:
        return self.audit.read_for_run(run_id)

    def check_rights(self, asset_id: str, platform: str, territory: str) -> dict[str, Any]:
        return self.rights.check_clip_rights(asset_id, platform, territory)

    def archive_search(self, **kwargs) -> list[dict[str, Any]]:
        return self.archive.archive_search(**kwargs)

    def list_archive(self) -> list[dict[str, Any]]:
        return self.archive.list_assets()

    def rights_summary(self) -> dict[str, Any]:
        restricted = self.rights.list_restricted()
        with self.rights._lock:
            total = len(self.rights._ledger)
        return {
            "total_assets": total,
            "restricted_or_unknown": len(restricted),
            "sample_restricted": restricted[:8],
        }

    def reset_store(self) -> dict[str, Any]:
        with self._lock:
            self._write_store({"runs": {}, "active_run_id": None})
        return {"ok": True, "message": "store cleared"}
