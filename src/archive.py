"""Partner Archive MCP mock — maps to Iconik / Perfect Memory / VionLabs style search."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Optional


DEFAULT_ARCHIVE_PATH = Path(__file__).resolve().parent.parent / "data" / "archive_seed.json"


class ArchiveMCP:
    """In-process stand-in for the hackathon partner archive MCP server."""

    def __init__(self, seed_path: Optional[str | Path] = None):
        self.seed_path = Path(seed_path or DEFAULT_ARCHIVE_PATH)
        self._assets: list[dict[str, Any]] = []
        self.reload()

    def reload(self) -> None:
        if self.seed_path.exists():
            raw = json.loads(self.seed_path.read_text(encoding="utf-8"))
            if isinstance(raw, list):
                self._assets = list(raw)
            else:
                self._assets = list((raw or {}).get("assets") or [])
        else:
            self._assets = []

    def list_assets(self) -> list[dict[str, Any]]:
        return [dict(a) for a in self._assets]

    def archive_search(
        self,
        concept: str = "",
        mood: Optional[list[str] | str] = None,
        entities: Optional[list[str]] = None,
        time_range: Optional[dict[str, str]] = None,
        limit: int = 24,
    ) -> list[dict[str, Any]]:
        """Search archive. Never invents asset_ids — only returns seeded assets."""
        moods = mood if isinstance(mood, list) else ([mood] if mood else [])
        moods = [m.lower() for m in moods if m]
        ents = [e.lower() for e in (entities or []) if e]
        concept_l = (concept or "").lower()
        tokens = [t for t in re.split(r"\W+", concept_l) if len(t) > 2]

        scored: list[tuple[float, dict[str, Any]]] = []
        for asset in self._assets:
            tags = [t.lower() for t in (asset.get("mood_tags") or asset.get("tags") or [])]
            a_ents = [e.lower() for e in (asset.get("entities") or [])]
            blob = " ".join(
                [
                    str(asset.get("title") or ""),
                    str(asset.get("description") or ""),
                    " ".join(tags),
                    " ".join(a_ents),
                ]
            ).lower()
            score = 0.0
            for m in moods:
                if m in tags or m in blob:
                    score += 30
            for e in ents:
                if e in a_ents or e in blob:
                    score += 25
            for t in tokens:
                if t in blob:
                    score += 12
            # Soft year filter if time_range provided
            if time_range and asset.get("year"):
                try:
                    y = int(asset["year"])
                    start = int((time_range.get("start") or "1900")[:4])
                    end = int((time_range.get("end") or "2100")[:4])
                    if start <= y <= end:
                        score += 5
                    else:
                        score -= 20
                except (TypeError, ValueError):
                    pass
            if score > 0 or not (tokens or moods or ents):
                # If no filters, return everything with baseline
                scored.append((score if (tokens or moods or ents) else 1.0, asset))

        scored.sort(key=lambda x: x[0], reverse=True)
        hits = []
        for score, asset in scored[:limit]:
            hits.append(
                {
                    "asset_id": asset["asset_id"],
                    "title": asset.get("title"),
                    "proxy_uri": asset.get("proxy_uri"),
                    "duration_seconds": asset.get("duration_seconds"),
                    "mood_tags": asset.get("mood_tags") or asset.get("tags") or [],
                    "entities": asset.get("entities") or [],
                    "year": asset.get("year"),
                    "thumbnail_uri": asset.get("thumbnail_uri") or asset.get("proxy_uri"),
                    "score": round(score, 2),
                }
            )
        return hits

    def archive_get_asset(self, asset_id: str) -> dict[str, Any]:
        for asset in self._assets:
            if asset.get("asset_id") == asset_id:
                return {
                    "asset_id": asset["asset_id"],
                    "title": asset.get("title"),
                    "timecodes": {
                        "start": 0.0,
                        "end": float(asset.get("duration_seconds") or 0),
                    },
                    "proxy_uri": asset.get("proxy_uri"),
                    "tags": asset.get("mood_tags") or asset.get("tags") or [],
                    "mood_tags": asset.get("mood_tags") or asset.get("tags") or [],
                    "entities": asset.get("entities") or [],
                    "description": asset.get("description") or "",
                    "duration_seconds": float(asset.get("duration_seconds") or 0),
                    "year": asset.get("year"),
                    "music_cleared": bool(asset.get("music_cleared", False)),
                    "thumbnail_uri": asset.get("thumbnail_uri") or asset.get("proxy_uri"),
                }
        return {
            "error": "asset_not_found",
            "message": f"asset_id '{asset_id}' not found in archive; do not invent clips.",
        }
