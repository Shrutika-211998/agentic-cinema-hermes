"""Captions + platform metadata — Gemini multimodal seam with deterministic fallback."""

from __future__ import annotations

import os
import re
from typing import Any, Optional


def generate_captions_metadata(
    rough_cut_uri: str,
    brief_params: dict[str, Any],
    selected_clips: Optional[list[dict[str, Any]]] = None,
) -> dict[str, Any]:
    """Generate on-screen captions + platform metadata.

    Uses Vertex/Gemini when VERTEX_AI_ENABLED=true and project is set; otherwise
    a deterministic on-brand fallback (credential-free demo).
    """
    if os.getenv("VERTEX_AI_ENABLED", "false").lower() == "true" and os.getenv("GOOGLE_CLOUD_PROJECT"):
        result = _gemini_captions(rough_cut_uri, brief_params, selected_clips or [])
        if result:
            return result
    return _deterministic_captions(brief_params, selected_clips or [])


def _deterministic_captions(
    brief: dict[str, Any],
    clips: list[dict[str, Any]],
) -> dict[str, Any]:
    subject = (brief.get("subject") or "Studio archive cut").strip()
    mood = (brief.get("mood") or "energetic").strip()
    platform = (brief.get("platform") or "instagram").lower()
    duration = int(brief.get("duration_seconds") or 30)
    territory = (brief.get("territory") or "US").upper()

    # Short on-screen beats from clip titles
    titles = [c.get("title") or c.get("asset_id") for c in clips[:6]]
    captions = []
    t = 0.0
    for i, title in enumerate(titles):
        dur = max(2.0, float(clips[i].get("out_tc", 5) or 5) - float(clips[i].get("in_tc", 0) or 0))
        captions.append(
            {
                "start": round(t, 2),
                "end": round(t + min(dur, 4.0), 2),
                "text": _short_caption(str(title), mood),
            }
        )
        t += dur

    if not captions:
        captions = [{"start": 0.0, "end": min(3.0, float(duration)), "text": subject[:48]}]

    hashtags = _hashtags(subject, mood, platform)
    title = _title_case(subject)[:80]
    description = (
        f"{title} — a {mood} {duration}s cut for {platform}. "
        f"Territory: {territory}. Rights-cleared via Second Unit. "
        f"Clips: {', '.join(str(t) for t in titles[:4])}."
    )

    return {
        "captions": captions,
        "title": title,
        "description": description[:500],
        "hashtags": hashtags,
        "platform": platform,
        "provider": "local-deterministic",
        "on_brand": True,
        "notes": "No unlicensed lyrics or third-party quotes included.",
    }


def _short_caption(title: str, mood: str) -> str:
    clean = re.sub(r"\s+", " ", title).strip()
    if len(clean) > 42:
        clean = clean[:39] + "…"
    # Avoid sounding like unlicensed copy
    return clean or mood.title()


def _title_case(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    if not text:
        return "Untitled Cut"
    return text[0].upper() + text[1:]


def _hashtags(subject: str, mood: str, platform: str) -> list[str]:
    tokens = [t for t in re.split(r"\W+", subject.lower()) if len(t) > 3][:4]
    tags = [f"#{t}" for t in tokens]
    tags.append(f"#{mood}")
    tags.append(f"#{platform}")
    tags.append("#SecondUnit")
    tags.append("#RightsCleared")
    # de-dupe preserve order
    seen = set()
    out = []
    for t in tags:
        tl = t.lower()
        if tl not in seen:
            seen.add(tl)
            out.append(t)
    return out[:12]


def _gemini_captions(
    rough_cut_uri: str,
    brief: dict[str, Any],
    clips: list[dict[str, Any]],
) -> Optional[dict[str, Any]]:
    try:
        from google import genai
        import json

        project = os.getenv("GOOGLE_CLOUD_PROJECT")
        location = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")
        model = os.getenv("VERTEX_AI_MODEL", "gemini-2.5-flash")
        client = genai.Client(vertexai=True, project=project, location=location)
        prompt = {
            "task": "Generate platform metadata and short on-screen captions for a rough cut.",
            "brief": brief,
            "clips": [{"asset_id": c.get("asset_id"), "title": c.get("title")} for c in clips],
            "rough_cut_uri": rough_cut_uri,
            "rules": [
                "No unlicensed lyrics or copyrighted quotes",
                "Keep captions under 48 chars",
                "Return JSON with captions[], title, description, hashtags[]",
            ],
        }
        response = client.models.generate_content(
            model=model,
            contents=json.dumps(prompt),
            config={"response_mime_type": "application/json"},
        )
        data = json.loads(response.text)
        if not isinstance(data, dict) or "title" not in data:
            return None
        data["provider"] = "vertex-gemini"
        return data
    except Exception:
        return None
