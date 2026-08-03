"""Service factory — local demo vs GCP production backends."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .archive import ArchiveMCP
from .audit import AuditLog
from .gcp.cloud_logging_audit import CloudAuditLog
from .gcp.config import ROOT, use_cloud_logging, use_firestore
from .gcp.iam_cloud import CloudIAMService
from .iam import IAMService
from .rights import RightsMCP


def build_services() -> dict[str, Any]:
    archive = ArchiveMCP(ROOT / "data" / "archive_seed.json")

    if use_firestore():
        rights = _firestore_rights()
    else:
        rights = RightsMCP(
            ROOT / "data" / "rights_ledger.json",
            ROOT / "data" / "territory_rules.json",
        )

    iam = CloudIAMService() if (use_firestore() or os.getenv("SECOND_UNIT_IAM_MODE") == "cloud") else IAMService()

    audit_path = ROOT / "data" / "audit_log.jsonl"
    if use_cloud_logging() or use_firestore():
        audit = CloudAuditLog(local_path=str(audit_path))
    else:
        audit = AuditLog(audit_path)

    return {
        "archive": archive,
        "rights": rights,
        "iam": iam,
        "audit": audit,
    }


def _firestore_rights() -> RightsMCP:
    """RightsMCP over Firestore-backed ledger snapshot (loaded into memory + write-through)."""
    from .gcp.firestore_store import FirestoreRightsLedger

    fs = FirestoreRightsLedger()
    rights = RightsMCP(
        ROOT / "data" / "rights_ledger.json",
        ROOT / "data" / "territory_rules.json",
    )
    try:
        assets = fs.all_assets()
        if not assets:
            # First boot: seed from JSON catalog
            fs.seed_from_json(
                str(ROOT / "data" / "rights_ledger.json"),
                str(ROOT / "data" / "territory_rules.json"),
            )
            assets = fs.all_assets()
        if assets:
            rights._ledger = {a["asset_id"]: a for a in assets if a.get("asset_id")}
        for t in ("US", "IN", "GLOBAL", "GB", "EU"):
            row = fs.get_territory(t)
            if row and row.get("territory"):
                rights._rules[row["territory"]] = row
        original_register = rights.register_clearance

        def register_clearance(asset_id: str, license_payload: dict):
            row = original_register(asset_id, license_payload)
            try:
                fs.upsert(asset_id, row)
            except Exception:
                pass
            return row

        rights.register_clearance = register_clearance  # type: ignore
    except Exception:
        pass
    return rights


def build_api(**kwargs):
    from .api import SecondUnitAPI
    from .pipeline import SecondUnitPipeline

    svc = build_services()
    data_path = kwargs.get("data_path")
    output_dir = kwargs.get("output_dir")

    api = SecondUnitAPI(
        data_path=data_path,
        archive=svc["archive"],
        rights=svc["rights"],
        iam=svc["iam"],
        audit=svc["audit"],
        output_dir=output_dir,
    )

    if use_firestore():
        _attach_firestore_persistence(api)
    return api


def _attach_firestore_persistence(api) -> None:
    """Monkey-patch run save/load to Firestore while keeping local cache."""
    from .gcp.firestore_store import FirestoreRunStore
    from .models import ProductionRun

    store = FirestoreRunStore()
    local_save = api._save_run
    local_get = api._get_run
    local_list = api.list_runs

    def save_run(run: ProductionRun):
        local_save(run)
        try:
            store.save_run(run.to_dict())
        except Exception as e:
            api.audit.write_audit_log(
                stage="persistence",
                decision="firestore_save_failed",
                actor="system",
                payload={"error": str(e), "run_id": run.run_id},
                run_id=run.run_id,
                audit_trail_id=run.audit_trail_id,
            )
        return run

    def get_run(run_id: str):
        run = local_get(run_id)
        if run:
            return run
        try:
            raw = store.get_run(run_id)
            if raw:
                return ProductionRun.from_dict(raw)
        except Exception:
            pass
        return None

    def list_runs(limit: int = 20):
        try:
            rows = store.list_runs(limit=limit)
            if rows:
                return rows
        except Exception:
            pass
        return local_list(limit=limit)

    api._save_run = save_run  # type: ignore
    api._get_run = get_run  # type: ignore
    api.list_runs = list_runs  # type: ignore
