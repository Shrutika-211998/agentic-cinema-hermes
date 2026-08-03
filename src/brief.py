"""Brief parsing and pure domain helpers (no I/O)."""

from __future__ import annotations

import re
from typing import Any, Optional

from .models import BriefParams, PLATFORM_ASPECT


DURATION_RE = re.compile(
    r"(?P<num>\d+(?:\.\d+)?)\s*(?P<unit>s|sec|secs|second|seconds|m|min|mins|minute|minutes)\b",
    re.I,
)
PLATFORM_ALIASES = {
    "ig": "instagram",
    "insta": "instagram",
    "reels": "instagram",
    "instagram reels": "instagram",
    "yt": "youtube",
    "you tube": "youtube",
    "tv": "broadcast",
    "broadcast": "broadcast",
    "tik tok": "tiktok",
}
TERRITORY_ALIASES = {
    "usa": "US",
    "u.s.": "US",
    "u.s.a.": "US",
    "united states": "US",
    "india": "IN",
    "uk": "GB",
    "u.k.": "GB",
    "global": "GLOBAL",
    "worldwide": "GLOBAL",
    "world": "GLOBAL",
}
MOOD_KEYWORDS = [
    "energetic",
    "uplifting",
    "cinematic",
    "dramatic",
    "joyful",
    "inspirational",
    "calm",
    "intense",
    "celebratory",
    "nostalgic",
    "heroic",
    "warm",
]


def _normalize_platform(text: str) -> Optional[str]:
    lower = text.lower()
    for alias, canon in PLATFORM_ALIASES.items():
        if alias in lower:
            return canon
    for name in ("instagram", "youtube", "tiktok", "broadcast", "web", "reels"):
        if name in lower:
            return "instagram" if name == "reels" else name
    return None


def _normalize_territory(text: str) -> Optional[str]:
    lower = text.lower()
    # Prefer explicit phrases before bare codes (avoid matching English "in")
    for alias, canon in TERRITORY_ALIASES.items():
        if re.search(rf"\b{re.escape(alias)}\b", lower):
            return canon
    # Bare country codes — do NOT match English preposition "in"
    m = re.search(r"\b(US|USA|GB|EU|GLOBAL)\b", text, re.I)
    if m:
        token = m.group(1).upper()
        return "US" if token == "USA" else token
    # India code only as standalone "IN" with non-letter boundaries and not part of "in the"
    if re.search(r"(?<![A-Za-z])IN(?![A-Za-z])", text) and not re.search(r"\bin\s+the\b", lower):
        # still too ambiguous; require explicit "territory IN" or ", IN"
        if re.search(r"\bterritory\s*[:\s]*IN\b", text, re.I) or re.search(r",\s*IN\b", text):
            return "IN"
    return None

def _extract_duration_seconds(text: str) -> Optional[int]:
    m = DURATION_RE.search(text)
    if not m:
        # bare "30s" already covered; try "30 second spot"
        m2 = re.search(r"\b(\d{1,3})\s*(?:second|sec|s)\b", text, re.I)
        if m2:
            return int(m2.group(1))
        return None
    num = float(m.group("num"))
    unit = m.group("unit").lower()
    if unit.startswith("m"):
        return int(num * 60)
    return int(num)


def _extract_mood(text: str) -> Optional[str]:
    lower = text.lower()
    for mood in MOOD_KEYWORDS:
        if mood in lower:
            return mood
    return None


def _extract_constraints(text: str) -> list[str]:
    constraints: list[str] = []
    lower = text.lower()
    if "music" in lower and ("clear" in lower or "rights" in lower or "licensed" in lower):
        constraints.append("only_music_rights_cleared")
    if "no logo" in lower or "logo-free" in lower or "no logos" in lower:
        constraints.append("no_logos")
    if "family friendly" in lower or "safe for work" in lower or "sfw" in lower:
        constraints.append("family_friendly")
    if "must include" in lower:
        constraints.append("must_include_requested")
    return constraints


def _extract_subject(text: str, mood: Optional[str], platform: Optional[str]) -> str:
    cleaned = text.strip()
    # Drop leading filler
    cleaned = re.sub(
        r"^(make|create|produce|cut|edit|build)\s+(me\s+)?(a|an|the)?\s*",
        "",
        cleaned,
        flags=re.I,
    )
    # Keep first clause as subject seed
    subject = re.split(r"[.!?]\s+", cleaned)[0]
    subject = re.sub(r"\s+", " ", subject).strip()
    if len(subject) > 160:
        subject = subject[:157] + "..."
    return subject or "brand montage"


def parse_brief(creative_brief: str, defaults: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Parse a natural-language creative brief into structured brief_params.

    Returns:
        {
          "brief_params": BriefParams-as-dict,
          "missing": ["duration_seconds"|"platform"|...],
          "clarifying_question": str|None,
        }
    """
    defaults = defaults or {}
    text = (creative_brief or "").strip()
    duration = _extract_duration_seconds(text)
    platform = _normalize_platform(text)
    territory = _normalize_territory(text)
    mood = _extract_mood(text)
    constraints = _extract_constraints(text)

    if duration is None and defaults.get("duration_seconds") is not None:
        duration = int(defaults["duration_seconds"])
    if platform is None and defaults.get("platform"):
        platform = str(defaults["platform"]).lower()
    if territory is None and defaults.get("territory"):
        territory = str(defaults["territory"]).upper()
    if mood is None and defaults.get("mood"):
        mood = str(defaults["mood"])

    # Apply safe defaults for demo velocity after one missing field attempt
    missing: list[str] = []
    if duration is None:
        missing.append("duration_seconds")
    if platform is None:
        missing.append("platform")

    question = None
    if "duration_seconds" in missing and "platform" in missing:
        question = "What duration (seconds) and target platform (Instagram, YouTube, broadcast)?"
    elif "duration_seconds" in missing:
        question = "What target duration should the cut be (e.g. 15s, 30s, 60s)?"
    elif "platform" in missing:
        question = "Which platform is this for (Instagram/Reels, YouTube, broadcast)?"

    # Proceed with defaults if only one field missing and caller set force_defaults
    if defaults.get("force_defaults"):
        duration = duration or 30
        platform = platform or "instagram"
        missing = []
        question = None

    params = BriefParams(
        duration_seconds=int(duration or 30),
        platform=str(platform or "instagram"),
        mood=str(mood or "energetic"),
        subject=_extract_subject(text, mood, platform),
        territory=str(territory or "US"),
        constraints=constraints,
    )
    return {
        "brief_params": params.to_dict(),
        "missing": missing if not defaults.get("force_defaults") else [],
        "clarifying_question": question if not defaults.get("force_defaults") else None,
        "aspect_ratio": PLATFORM_ASPECT.get(params.platform, "16:9"),
    }


def score_clip_for_brief(clip: dict[str, Any], brief: dict[str, Any]) -> float:
    """Rank a candidate clip against brief params. Higher is better."""
    score = 0.0
    mood = (brief.get("mood") or "").lower()
    subject = (brief.get("subject") or "").lower()
    tags = [t.lower() for t in (clip.get("mood_tags") or clip.get("tags") or [])]
    entities = [e.lower() for e in (clip.get("entities") or [])]
    title = (clip.get("title") or "").lower()
    desc = (clip.get("description") or "").lower()
    blob = " ".join([title, desc, *tags, *entities])

    if mood and mood in tags:
        score += 40
    elif mood and mood in blob:
        score += 25

    subject_tokens = [t for t in re.split(r"\W+", subject) if len(t) > 3]
    hits = sum(1 for t in subject_tokens if t in blob)
    score += min(40, hits * 10)

    # Prefer mid-length usable clips
    dur = float(clip.get("duration_seconds") or 0)
    if 3 <= dur <= 12:
        score += 10
    elif dur > 0:
        score += 4

    # Slight preference for music-cleared when constraint present
    constraints = brief.get("constraints") or []
    if "only_music_rights_cleared" in constraints and clip.get("music_cleared"):
        score += 8

    return score


def select_clips_for_duration(
    candidates: list[dict[str, Any]],
    brief: dict[str, Any],
    *,
    target_overshoot: float = 1.15,
) -> list[dict[str, Any]]:
    """Greedy pack highest-scoring clips until duration is met."""
    target = float(brief.get("duration_seconds") or 30)
    ranked = sorted(
        candidates,
        key=lambda c: score_clip_for_brief(c, brief),
        reverse=True,
    )
    selected: list[dict[str, Any]] = []
    total = 0.0
    for i, clip in enumerate(ranked):
        if total >= target:
            break
        # Avoid near-duplicates by title prefix
        title = (clip.get("title") or "").lower()[:24]
        if any((s.get("title") or "").lower()[:24] == title for s in selected):
            continue
        usable = min(float(clip.get("duration_seconds") or 5), max(2.0, target - total + 1))
        # take from start of proxy for demo
        item = dict(clip)
        item["order"] = len(selected)
        item["in_tc"] = 0.0
        item["out_tc"] = round(usable, 2)
        selected.append(item)
        total += usable
        if total >= target * target_overshoot:
            break

    # If still short, pad with remaining highest ranked
    if total < target * 0.85:
        for clip in ranked:
            if any(s.get("asset_id") == clip.get("asset_id") for s in selected):
                continue
            usable = min(float(clip.get("duration_seconds") or 5), target - total)
            if usable <= 0.5:
                break
            item = dict(clip)
            item["order"] = len(selected)
            item["in_tc"] = 0.0
            item["out_tc"] = round(usable, 2)
            selected.append(item)
            total += usable
            if total >= target:
                break

    return selected


def total_selected_duration(selected: list[dict[str, Any]]) -> float:
    return sum(max(0.0, float(c.get("out_tc") or 0) - float(c.get("in_tc") or 0)) for c in selected)
