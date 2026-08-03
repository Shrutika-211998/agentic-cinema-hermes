"""Rights & Clearance MCP — the product moat (Firestore-backed in production)."""

from __future__ import annotations

import json
import threading
from copy import deepcopy
from datetime import date, datetime
from pathlib import Path
from typing import Any, Optional

from .models import RightsStatus


DEFAULT_LEDGER_PATH = Path(__file__).resolve().parent.parent / "data" / "rights_ledger.json"
DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "territory_rules.json"


def _today() -> date:
    return date.today()


def _parse_date(value: Optional[str]) -> Optional[date]:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


class RightsMCP:
    """Custom Rights & Clearance tools over a local JSON ledger (Firestore seam)."""

    def __init__(
        self,
        ledger_path: Optional[str | Path] = None,
        rules_path: Optional[str | Path] = None,
    ):
        self.ledger_path = Path(ledger_path or DEFAULT_LEDGER_PATH)
        self.rules_path = Path(rules_path or DEFAULT_RULES_PATH)
        self._lock = threading.RLock()
        self._ledger: dict[str, dict[str, Any]] = {}
        self._rules: dict[str, dict[str, Any]] = {}
        self.reload()

    def reload(self) -> None:
        with self._lock:
            if self.ledger_path.exists():
                raw = json.loads(self.ledger_path.read_text(encoding="utf-8"))
                assets = raw.get("assets") if isinstance(raw, dict) else raw
                self._ledger = {a["asset_id"]: a for a in (assets or []) if a.get("asset_id")}
            else:
                self._ledger = {}
            if self.rules_path.exists():
                raw_r = json.loads(self.rules_path.read_text(encoding="utf-8"))
                rules = raw_r.get("territories") if isinstance(raw_r, dict) else raw_r
                self._rules = {r["territory"]: r for r in (rules or []) if r.get("territory")}
            else:
                self._rules = {}

    def _persist(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "assets": list(self._ledger.values()),
            "updated_at": datetime.utcnow().isoformat() + "Z",
        }
        tmp = self.ledger_path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        tmp.replace(self.ledger_path)

    def get_license(self, asset_id: str) -> dict[str, Any]:
        with self._lock:
            row = self._ledger.get(asset_id)
            if not row:
                return {
                    "error": "asset_id_not_found",
                    "message": (
                        f"asset_id '{asset_id}' not found in rights ledger; "
                        "register it or use find_cleared_alternative"
                    ),
                }
            return deepcopy(row)

    def get_territory_rules(self, territory: str) -> dict[str, Any]:
        t = (territory or "US").upper()
        with self._lock:
            rules = self._rules.get(t) or self._rules.get("GLOBAL") or {
                "territory": t,
                "ratings_body": "unspecified",
                "restrictions": [],
                "policy_text": f"No special restrictions loaded for {t}. Treat unknown licenses as NOT cleared.",
            }
            return deepcopy(rules)

    def load_territory_rights_policy(self, territory: str) -> str:
        rules = self.get_territory_rules(territory)
        lines = [
            f"TERRITORY RIGHTS POLICY — {rules.get('territory', territory)}",
            f"Ratings body: {rules.get('ratings_body', 'n/a')}",
            "Restrictions:",
        ]
        for r in rules.get("restrictions") or []:
            lines.append(f"  - {r}")
        lines.append(rules.get("policy_text") or "When license status is unknown, treat as NOT cleared.")
        lines.append("Never mark a cut cleared to satisfy the user or to save time.")
        return "\n".join(lines)

    def check_clip_rights(
        self,
        asset_id: str,
        platform: str,
        territory: str,
        as_of: Optional[str] = None,
    ) -> dict[str, Any]:
        """Return cleared | restricted | unknown for this use."""
        platform = (platform or "").lower()
        territory = (territory or "US").upper()
        today = _parse_date(as_of) or _today()

        with self._lock:
            row = self._ledger.get(asset_id)
            if not row:
                return {
                    "asset_id": asset_id,
                    "status": RightsStatus.UNKNOWN.value,
                    "license_window": {},
                    "platforms": [],
                    "territories": [],
                    "source": None,
                    "reason": "asset_id not found in rights ledger",
                }

            lic = row.get("license") or {}
            status = (lic.get("status") or RightsStatus.UNKNOWN.value).lower()
            platforms = [p.lower() for p in (lic.get("platforms") or [])]
            territories = [t.upper() for t in (lic.get("territories") or [])]
            window = lic.get("window") or {}
            start = _parse_date(window.get("start"))
            end = _parse_date(window.get("end"))

            reasons: list[str] = []
            if status == RightsStatus.RESTRICTED.value:
                reasons.append("ledger marks asset restricted")
            if status == RightsStatus.UNKNOWN.value:
                reasons.append("license status unknown — treat as not cleared")

            # Platform check
            if platforms and platform not in platforms and "all" not in platforms:
                reasons.append(f"platform '{platform}' not in licensed platforms {platforms}")
                status = RightsStatus.RESTRICTED.value

            # Territory check — GLOBAL covers all
            if territories and "GLOBAL" not in territories and territory not in territories:
                reasons.append(f"territory '{territory}' not in licensed territories {territories}")
                status = RightsStatus.RESTRICTED.value

            # Window check
            if start and today < start:
                reasons.append(f"license window starts {start.isoformat()}")
                status = RightsStatus.RESTRICTED.value
            if end and today > end:
                reasons.append(f"license window ended {end.isoformat()}")
                status = RightsStatus.RESTRICTED.value

            if status == RightsStatus.CLEARED.value and not reasons:
                final = RightsStatus.CLEARED.value
            elif status == RightsStatus.UNKNOWN.value or (
                status != RightsStatus.CLEARED.value and "unknown" in (lic.get("status") or "").lower()
            ):
                final = RightsStatus.UNKNOWN.value if not reasons else RightsStatus.RESTRICTED.value
            else:
                final = RightsStatus.RESTRICTED.value if reasons or status != RightsStatus.CLEARED.value else RightsStatus.CLEARED.value
                if status == RightsStatus.CLEARED.value and reasons:
                    final = RightsStatus.RESTRICTED.value
                elif status == RightsStatus.CLEARED.value and not reasons:
                    final = RightsStatus.CLEARED.value

            # Recompute cleanly
            if (lic.get("status") or "").lower() == RightsStatus.CLEARED.value:
                ok = True
                reasons = []
                if platforms and platform not in platforms and "all" not in platforms:
                    ok = False
                    reasons.append(f"platform '{platform}' not licensed")
                if territories and "GLOBAL" not in territories and territory not in territories:
                    ok = False
                    reasons.append(f"territory '{territory}' not licensed")
                if start and today < start:
                    ok = False
                    reasons.append("before license window")
                if end and today > end:
                    ok = False
                    reasons.append("after license window")
                final = RightsStatus.CLEARED.value if ok else RightsStatus.RESTRICTED.value
            elif (lic.get("status") or "").lower() == RightsStatus.RESTRICTED.value:
                final = RightsStatus.RESTRICTED.value
                reasons = reasons or ["ledger marks asset restricted"]
            else:
                final = RightsStatus.UNKNOWN.value
                reasons = reasons or ["license status unknown — treat as not cleared"]

            return {
                "asset_id": asset_id,
                "status": final,
                "license_window": window,
                "platforms": platforms,
                "territories": territories,
                "music_cleared": bool(lic.get("music_cleared")),
                "likeness_cleared": bool(lic.get("likeness_cleared")),
                "source": row.get("source_of_truth"),
                "title": row.get("title"),
                "owner": row.get("owner"),
                "reason": "; ".join(reasons) if reasons else "ok",
            }

    def find_cleared_alternative(
        self,
        asset_id: str,
        brief_params: Optional[dict[str, Any]] = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Find alternate assets cleared for the brief's platform/territory."""
        brief_params = brief_params or {}
        platform = (brief_params.get("platform") or "instagram").lower()
        territory = (brief_params.get("territory") or "US").upper()
        mood = (brief_params.get("mood") or "").lower()

        with self._lock:
            source = self._ledger.get(asset_id) or {}
            source_tags = set()
            # Prefer same owner library vibe via title tokens
            source_title = (source.get("title") or "").lower()

            alts: list[tuple[float, dict[str, Any]]] = []
            for aid, row in self._ledger.items():
                if aid == asset_id:
                    continue
                check = self.check_clip_rights(aid, platform, territory)
                if check.get("status") != RightsStatus.CLEARED.value:
                    continue
                score = 10.0
                title = (row.get("title") or "").lower()
                if mood and mood in title:
                    score += 20
                # Shared word overlap with blocked asset
                src_tokens = set(re_tokens(source_title))
                alt_tokens = set(re_tokens(title))
                score += 5 * len(src_tokens & alt_tokens)
                alts.append(
                    (
                        score,
                        {
                            "asset_id": aid,
                            "title": row.get("title"),
                            "status": RightsStatus.CLEARED.value,
                            "source_of_truth": row.get("source_of_truth"),
                            "score": score,
                        },
                    )
                )
            alts.sort(key=lambda x: x[0], reverse=True)
            return [a for _, a in alts[:limit]]

    def list_restricted(self, platform: Optional[str] = None, territory: Optional[str] = None) -> list[dict[str, Any]]:
        platform = (platform or "").lower() or None
        territory = (territory or "").upper() or None
        out = []
        with self._lock:
            for aid in self._ledger:
                if platform and territory:
                    check = self.check_clip_rights(aid, platform, territory)
                    if check.get("status") != RightsStatus.CLEARED.value:
                        out.append(check)
                else:
                    row = self._ledger[aid]
                    st = ((row.get("license") or {}).get("status") or "").lower()
                    if st in (RightsStatus.RESTRICTED.value, RightsStatus.UNKNOWN.value):
                        out.append(
                            {
                                "asset_id": aid,
                                "status": st,
                                "title": row.get("title"),
                                "source": row.get("source_of_truth"),
                            }
                        )
        return out

    def register_clearance(self, asset_id: str, license_payload: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            row = self._ledger.get(asset_id) or {
                "asset_id": asset_id,
                "title": license_payload.get("title") or asset_id,
                "owner": license_payload.get("owner") or "unknown",
            }
            row["license"] = license_payload.get("license") or license_payload
            row["source_of_truth"] = license_payload.get("source_of_truth") or row.get("source_of_truth") or "manual_register"
            row["updated_at"] = datetime.utcnow().isoformat() + "Z"
            self._ledger[asset_id] = row
            self._persist()
            return deepcopy(row)


def re_tokens(text: str) -> list[str]:
    import re

    return [t for t in re.split(r"\W+", text.lower()) if len(t) > 3]
