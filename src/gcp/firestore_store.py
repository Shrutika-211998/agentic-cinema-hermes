"""Firestore adapters for runs + rights ledger (production)."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Optional

from ..gcp.config import project_id, use_firestore


def _client():
    from google.cloud import firestore

    pid = project_id() or None
    return firestore.Client(project=pid)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class FirestoreRunStore:
    def __init__(self, collection: str = "productions"):
        self.collection = collection
        self._db = _client()

    def save_run(self, run: dict[str, Any]) -> None:
        rid = run["run_id"]
        run = dict(run)
        run["updated_at"] = run.get("updated_at") or now_iso()
        self._db.collection(self.collection).document(rid).set(run)
        self._db.collection("meta").document("active").set(
            {"active_run_id": rid, "updated_at": now_iso()}, merge=True
        )

    def get_run(self, run_id: str) -> Optional[dict[str, Any]]:
        snap = self._db.collection(self.collection).document(run_id).get()
        return snap.to_dict() if snap.exists else None

    def list_runs(self, limit: int = 20) -> list[dict[str, Any]]:
        q = (
            self._db.collection(self.collection)
            .order_by("updated_at", direction="DESCENDING")
            .limit(limit)
        )
        return [d.to_dict() for d in q.stream() if d.to_dict()]

    def get_active_run_id(self) -> Optional[str]:
        snap = self._db.collection("meta").document("active").get()
        if not snap.exists:
            return None
        return (snap.to_dict() or {}).get("active_run_id")

    def reset(self) -> None:
        # Soft reset active pointer only (keeps audit history)
        self._db.collection("meta").document("active").set(
            {"active_run_id": None, "updated_at": now_iso()}, merge=True
        )


class FirestoreRightsLedger:
    """Rights ledger collection matching architecture §8."""

    def __init__(
        self,
        ledger_collection: str = "rights_ledger",
        rules_collection: str = "territory_rules",
    ):
        self.ledger_collection = ledger_collection
        self.rules_collection = rules_collection
        self._db = _client()

    def get(self, asset_id: str) -> Optional[dict[str, Any]]:
        snap = self._db.collection(self.ledger_collection).document(asset_id).get()
        return snap.to_dict() if snap.exists else None

    def all_assets(self) -> list[dict[str, Any]]:
        return [d.to_dict() for d in self._db.collection(self.ledger_collection).stream() if d.to_dict()]

    def upsert(self, asset_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        row = dict(payload)
        row["asset_id"] = asset_id
        row["updated_at"] = now_iso()
        self._db.collection(self.ledger_collection).document(asset_id).set(row, merge=True)
        return row

    def get_territory(self, territory: str) -> Optional[dict[str, Any]]:
        t = (territory or "US").upper()
        snap = self._db.collection(self.rules_collection).document(t).get()
        if snap.exists:
            return snap.to_dict()
        snap = self._db.collection(self.rules_collection).document("GLOBAL").get()
        return snap.to_dict() if snap.exists else None

    def seed_from_json(self, ledger_path: str, rules_path: str) -> dict[str, int]:
        with open(ledger_path, encoding="utf-8") as f:
            ledger = json.load(f)
        with open(rules_path, encoding="utf-8") as f:
            rules = json.load(f)
        n_assets = 0
        for row in ledger.get("assets") or []:
            aid = row.get("asset_id")
            if not aid:
                continue
            self._db.collection(self.ledger_collection).document(aid).set(row, merge=True)
            n_assets += 1
        n_rules = 0
        for row in rules.get("territories") or []:
            t = row.get("territory")
            if not t:
                continue
            self._db.collection(self.rules_collection).document(t).set(row, merge=True)
            n_rules += 1
        return {"assets": n_assets, "territories": n_rules}


def firestore_available() -> bool:
    if not use_firestore():
        return False
    try:
        _client()
        return True
    except Exception:
        return False
