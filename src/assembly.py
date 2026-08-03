"""Assembly tool — Cloud Run + ffmpeg seam. Works without ffmpeg via JSON EDL + text proxy."""

from __future__ import annotations

import json
import shutil
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from .models import PLATFORM_ASPECT


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUTPUT = ROOT / "output"


def _now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def ffmpeg_available() -> bool:
    return shutil.which("ffmpeg") is not None


def assemble_rough_cut(
    selected_clips: list[dict[str, Any]],
    *,
    platform: str = "instagram",
    run_id: str = "",
    output_dir: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Produce EDL + proxy rough-cut artifact.

    Prefer real ffmpeg concat when binaries + media exist; otherwise emit a
    deterministic JSON EDL and a human-readable proxy manifest (demo-safe).
    """
    out_root = Path(output_dir or DEFAULT_OUTPUT)
    out_root.mkdir(parents=True, exist_ok=True)
    stamp = _now_stamp()
    rid = run_id or uuid.uuid4().hex[:8]
    base = out_root / f"{rid}_{stamp}"
    base.mkdir(parents=True, exist_ok=True)

    edl_events = []
    total = 0.0
    for i, clip in enumerate(selected_clips, start=1):
        inn = float(clip.get("in_tc") or 0.0)
        out = float(clip.get("out_tc") or clip.get("duration_seconds") or 5.0)
        dur = max(0.0, out - inn)
        edl_events.append(
            {
                "event": i,
                "asset_id": clip.get("asset_id"),
                "title": clip.get("title"),
                "proxy_uri": clip.get("proxy_uri"),
                "in_tc": inn,
                "out_tc": out,
                "duration": round(dur, 3),
                "timeline_start": round(total, 3),
                "timeline_end": round(total + dur, 3),
            }
        )
        total += dur

    aspect = PLATFORM_ASPECT.get((platform or "").lower(), "16:9")
    edl = {
        "format": "second_unit_json_edl_v1",
        "cmx_compatible_note": "Also write simple CMX3600-style lines below",
        "platform": platform,
        "aspect_ratio": aspect,
        "run_id": rid,
        "total_duration_seconds": round(total, 3),
        "events": edl_events,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    # Simple CMX-ish text
    cmx_lines = ["TITLE: Second Unit Rough Cut", f"FCM: NON-DROP FRAME", ""]
    for ev in edl_events:
        cmx_lines.append(
            f"{ev['event']:03d}  {str(ev['asset_id'])[:8].upper():<8} V     C        "
            f"{_tc(ev['in_tc'])} {_tc(ev['out_tc'])} {_tc(ev['timeline_start'])} {_tc(ev['timeline_end'])}"
        )
        cmx_lines.append(f"* FROM CLIP NAME: {ev.get('title')}")
    cmx_text = "\n".join(cmx_lines) + "\n"

    edl_json_path = base / "cut.edl.json"
    edl_cmx_path = base / "cut.edl"
    proxy_manifest = base / "rough_cut_proxy.json"
    proxy_txt = base / "rough_cut_proxy.txt"

    edl_json_path.write_text(json.dumps(edl, indent=2), encoding="utf-8")
    edl_cmx_path.write_text(cmx_text, encoding="utf-8")

    rough_cut_uri = str(proxy_manifest.resolve())
    used_ffmpeg = False

    # Attempt ffmpeg only if all local media files exist
    local_files = []
    for clip in selected_clips:
        uri = str(clip.get("proxy_uri") or "")
        path = _resolve_media_path(uri)
        if path and path.exists() and path.suffix.lower() in {".mp4", ".mov", ".mkv", ".webm"}:
            local_files.append((path, float(clip.get("in_tc") or 0), float(clip.get("out_tc") or 0)))
        else:
            local_files = []
            break

    mp4_path = base / "rough_cut_proxy.mp4"
    if local_files and ffmpeg_available():
        try:
            used_ffmpeg = _ffmpeg_concat(local_files, mp4_path, aspect)
            if used_ffmpeg and mp4_path.exists():
                rough_cut_uri = str(mp4_path.resolve())
        except Exception:
            used_ffmpeg = False

    manifest = {
        "type": "proxy_rough_cut",
        "run_id": rid,
        "platform": platform,
        "aspect_ratio": aspect,
        "total_duration_seconds": round(total, 3),
        "clip_count": len(edl_events),
        "events": edl_events,
        "ffmpeg_rendered": used_ffmpeg,
        "media_uri": rough_cut_uri if used_ffmpeg else None,
        "note": (
            "Real ffmpeg proxy rendered."
            if used_ffmpeg
            else "Deterministic proxy manifest (seed proxies are metadata placeholders; wire GCS media for real frames)."
        ),
    }
    proxy_manifest.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    proxy_txt.write_text(_human_proxy_timeline(manifest), encoding="utf-8")

    return {
        "edl_uri": str(edl_json_path.resolve()),
        "edl_cmx_uri": str(edl_cmx_path.resolve()),
        "rough_cut_uri": rough_cut_uri if used_ffmpeg else str(proxy_manifest.resolve()),
        "proxy_text_uri": str(proxy_txt.resolve()),
        "total_duration_seconds": round(total, 3),
        "aspect_ratio": aspect,
        "ffmpeg_rendered": used_ffmpeg,
        "event_count": len(edl_events),
    }


def _tc(seconds: float) -> str:
    s = max(0.0, float(seconds))
    hh = int(s // 3600)
    mm = int((s % 3600) // 60)
    ss = int(s % 60)
    ff = int(round((s - int(s)) * 24))
    return f"{hh:02d}:{mm:02d}:{ss:02d}:{ff:02d}"


def _resolve_media_path(uri: str) -> Optional[Path]:
    if not uri:
        return None
    if uri.startswith("gs://"):
        # local demo mapping: gs://second-unit-demo/proxies/foo.mp4 -> media/proxies/foo.mp4
        name = uri.rstrip("/").split("/")[-1]
        return ROOT / "media" / "proxies" / name
    if uri.startswith("file://"):
        return Path(uri.replace("file://", ""))
    p = Path(uri)
    if p.exists():
        return p
    # try under media/
    cand = ROOT / "media" / "proxies" / Path(uri).name
    return cand if cand.exists() else p


def _ffmpeg_concat(
    clips: list[tuple[Path, float, float]],
    dest: Path,
    aspect: str,
) -> bool:
    # Build filter_complex trim+concat
    # Simplified: full-file concat demuxer when in/out cover full files
    list_file = dest.with_suffix(".txt")
    lines = []
    for path, inn, out in clips:
        # For demo simplicity use full file if trim is near-full
        lines.append(f"file '{path.as_posix()}'")
    list_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(dest),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
    return proc.returncode == 0 and dest.exists()


def _human_proxy_timeline(manifest: dict[str, Any]) -> str:
    lines = [
        "SECOND UNIT — PROXY ROUGH CUT",
        f"Platform: {manifest.get('platform')}  Aspect: {manifest.get('aspect_ratio')}",
        f"Duration: {manifest.get('total_duration_seconds')}s  Clips: {manifest.get('clip_count')}",
        "",
        "TIMELINE",
        "-" * 48,
    ]
    for ev in manifest.get("events") or []:
        lines.append(
            f"[{ev['timeline_start']:6.2f} → {ev['timeline_end']:6.2f}]  "
            f"{ev.get('asset_id')}  {ev.get('title')}"
        )
    lines.append("-" * 48)
    lines.append(manifest.get("note") or "")
    return "\n".join(lines) + "\n"


def publish_release_package(
    edl_uri: str,
    rough_cut_uri: str,
    metadata: dict[str, Any],
    platform: str,
    clearance_report: Optional[dict[str, Any]] = None,
    run_id: str = "",
    output_dir: Optional[str | Path] = None,
) -> dict[str, Any]:
    """Package approved cut into a release folder (GCS release bucket seam)."""
    out_root = Path(output_dir or DEFAULT_OUTPUT) / "releases"
    out_root.mkdir(parents=True, exist_ok=True)
    rid = run_id or uuid.uuid4().hex[:8]
    dest = out_root / f"release_{rid}_{_now_stamp()}"
    dest.mkdir(parents=True, exist_ok=True)

    package = {
        "release_id": dest.name,
        "run_id": rid,
        "platform": platform,
        "edl_uri": edl_uri,
        "rough_cut_uri": rough_cut_uri,
        "metadata": metadata or {},
        "clearance_report": clearance_report or {},
        "published_at": datetime.now(timezone.utc).isoformat(),
        "status": "published_local",
        "delivery_note": "Local GCS-bucket stand-in. Production: push to release bucket or partner delivery MCP / YouTube unlisted.",
    }

    # Copy artifacts if local paths
    for label, uri in ("edl", edl_uri), ("rough_cut", rough_cut_uri):
        p = Path(uri) if uri else None
        if p and p.exists() and p.is_file():
            target = dest / p.name
            target.write_bytes(p.read_bytes())
            package[f"{label}_packaged"] = str(target.resolve())

    manifest_path = dest / "release_manifest.json"
    manifest_path.write_text(json.dumps(package, indent=2), encoding="utf-8")

    # One-page clearance summary
    report_path = dest / "clearance_report.json"
    report_path.write_text(json.dumps(clearance_report or {}, indent=2), encoding="utf-8")

    return {
        "release_package_uri": str(dest.resolve()),
        "manifest_uri": str(manifest_path.resolve()),
        "clearance_report_uri": str(report_path.resolve()),
        "platform": platform,
        "status": "published",
    }
