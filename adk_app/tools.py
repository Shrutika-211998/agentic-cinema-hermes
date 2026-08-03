"""ADK-callable tools wrapping Second Unit domain services."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.factory import build_services

_SVC = None


def services():
    global _SVC
    if _SVC is None:
        _SVC = build_services()
    return _SVC


def archive_search(
    concept: str = "",
    mood: str = "",
    entities: str = "",
    limit: int = 24,
) -> dict[str, Any]:
    """Search the partner media archive for candidate clips."""
    moods = [m.strip() for m in (mood or "").split(",") if m.strip()]
    ents = [e.strip() for e in (entities or "").split(",") if e.strip()]
    hits = services()["archive"].archive_search(
        concept=concept, mood=moods, entities=ents, limit=limit
    )
    return {"hits": hits, "count": len(hits)}


def archive_get_asset(asset_id: str) -> dict[str, Any]:
    """Fetch full metadata for one archive asset_id. Never invent IDs."""
    return services()["archive"].archive_get_asset(asset_id)


def check_clip_rights(asset_id: str, platform: str = "instagram", territory: str = "US") -> dict[str, Any]:
    """Check rights ledger for platform+territory clearance."""
    return services()["rights"].check_clip_rights(asset_id, platform, territory)


def find_cleared_alternative(
    asset_id: str,
    platform: str = "instagram",
    territory: str = "US",
    mood: str = "",
    subject: str = "",
) -> dict[str, Any]:
    """Find cleared alternate assets when a clip is restricted/unknown."""
    alts = services()["rights"].find_cleared_alternative(
        asset_id,
        {"platform": platform, "territory": territory, "mood": mood, "subject": subject},
    )
    return {"alternatives": alts, "count": len(alts)}


def assemble_rough_cut_tool(
    selected_clips_json: str,
    platform: str = "instagram",
    run_id: str = "",
) -> dict[str, Any]:
    """Assemble EDL + proxy rough cut from selected clips JSON list."""
    from src.assembly import assemble_rough_cut

    try:
        clips = json.loads(selected_clips_json) if isinstance(selected_clips_json, str) else selected_clips_json
    except json.JSONDecodeError:
        return {"error": "invalid_json", "message": "selected_clips_json must be a JSON array"}
    if not isinstance(clips, list):
        return {"error": "invalid_clips", "message": "expected a list of clip objects"}
    return assemble_rough_cut(clips, platform=platform, run_id=run_id or "adk")


def generate_captions_metadata_tool(
    rough_cut_uri: str,
    brief_json: str = "{}",
    selected_clips_json: str = "[]",
) -> dict[str, Any]:
    """Generate captions + platform metadata (Gemini when enabled)."""
    from src.captions import generate_captions_metadata

    try:
        brief = json.loads(brief_json) if brief_json else {}
    except json.JSONDecodeError:
        brief = {}
    try:
        clips = json.loads(selected_clips_json) if selected_clips_json else []
    except json.JSONDecodeError:
        clips = []
    return generate_captions_metadata(rough_cut_uri, brief, clips)


def check_release_authorization(user_identity: str, resource: str = "") -> dict[str, Any]:
    """Live IAM check — only releasingProducer may approve publish."""
    return services()["iam"].check_release_authorization(user_identity, resource=resource or None)


def publish_release_package_tool(
    edl_uri: str,
    rough_cut_uri: str,
    metadata_json: str = "{}",
    platform: str = "instagram",
    clearance_report_json: str = "{}",
    run_id: str = "",
) -> dict[str, Any]:
    """Publish release package. Blocked by before_tool_callback unless approved+IAM."""
    from src.assembly import publish_release_package

    try:
        metadata = json.loads(metadata_json) if metadata_json else {}
    except json.JSONDecodeError:
        metadata = {}
    try:
        report = json.loads(clearance_report_json) if clearance_report_json else {}
    except json.JSONDecodeError:
        report = {}
    return publish_release_package(
        edl_uri=edl_uri,
        rough_cut_uri=rough_cut_uri,
        metadata=metadata,
        platform=platform,
        clearance_report=report,
        run_id=run_id or "adk",
    )


def write_audit_log_tool(
    stage: str,
    decision: str,
    actor: str,
    payload_json: str = "{}",
    audit_trail_id: str = "",
    run_id: str = "",
) -> dict[str, Any]:
    """Write structured audit log entry (Cloud Logging in production)."""
    try:
        payload = json.loads(payload_json) if payload_json else {}
    except json.JSONDecodeError:
        payload = {"raw": payload_json}
    return services()["audit"].write_audit_log(
        stage=stage,
        decision=decision,
        actor=actor,
        payload=payload,
        audit_trail_id=audit_trail_id or None,
        run_id=run_id or None,
    )
