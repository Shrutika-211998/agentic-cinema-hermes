#!/usr/bin/env python
"""Seed Firestore rights_ledger + territory_rules + optional archive catalog."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("STORAGE_BACKEND", "firestore")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", os.getenv("GOOGLE_CLOUD_PROJECT", "project-41b01091-4313-42ff-8d8"))

from src.gcp.firestore_store import FirestoreRightsLedger  # noqa: E402


def main() -> None:
    ledger = ROOT / "data" / "rights_ledger.json"
    rules = ROOT / "data" / "territory_rules.json"
    fs = FirestoreRightsLedger()
    result = fs.seed_from_json(str(ledger), str(rules))
    print("Seeded Firestore:", result)


if __name__ == "__main__":
    main()
