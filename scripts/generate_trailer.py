"""Generate Second Unit hackathon trailer (slideshow MP4) + simple proxy color clips."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "trailer"
PROXIES = ROOT / "media" / "proxies"
OUT.mkdir(parents=True, exist_ok=True)
PROXIES.mkdir(parents=True, exist_ok=True)

W, H = 1280, 720
FPS = 24


def font(size: int):
    candidates = [
        r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arial.ttf",
        r"C:\Windows\Fonts\calibri.ttf",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


F_TITLE = font(64)
F_SUB = font(36)
F_BODY = font(28)
F_SMALL = font(22)


def gradient(c1, c2):
    img = Image.new("RGB", (W, H), c1)
    px = img.load()
    for y in range(H):
        t = y / (H - 1)
        r = int(c1[0] * (1 - t) + c2[0] * t)
        g = int(c1[1] * (1 - t) + c2[1] * t)
        b = int(c1[2] * (1 - t) + c2[2] * t)
        for x in range(W):
            px[x, y] = (r, g, b)
    return img


def center_text(draw, text, y, fnt, fill=(232, 238, 249)):
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw = bbox[2] - bbox[0]
    draw.text(((W - tw) // 2, y), text, font=fnt, fill=fill)


def wrap_lines(text, fnt, max_width=1000):
    words = text.split()
    lines, cur = [], ""
    dummy = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for w in words:
        trial = (cur + " " + w).strip()
        if dummy.textbbox((0, 0), trial, font=fnt)[2] <= max_width:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def slide(title: str, lines: list[str], accent=(110, 168, 255), badge: str | None = None):
    img = gradient((11, 13, 18), (18, 28, 48))
    draw = ImageDraw.Draw(img)
    # top bar
    draw.rectangle([0, 0, W, 8], fill=accent)
    # brand
    draw.rounded_rectangle([40, 30, 130, 90], radius=16, fill=accent)
    draw.text((58, 42), "SU", font=F_SUB, fill=(6, 16, 24))
    draw.text((150, 45), "SECOND UNIT", font=F_SMALL, fill=(180, 196, 220))
    if badge:
        bw = 280
        draw.rounded_rectangle([W - bw - 40, 36, W - 40, 84], radius=20, fill=(40, 30, 70))
        draw.text((W - bw - 15, 48), badge, font=F_SMALL, fill=(217, 200, 255))

    center_text(draw, title, 200, F_TITLE, fill=(255, 255, 255))
    y = 300
    for line in lines:
        for wl in wrap_lines(line, F_BODY):
            center_text(draw, wl, y, F_BODY, fill=(197, 208, 228))
            y += 44
    # footer
    draw.text((40, H - 50), "Agentic Cinema · Google Cloud · Gemini + ADK + MCP + IAM", font=F_SMALL, fill=(120, 135, 160))
    return img


def beat_card(stage: str, detail: str, color):
    img = gradient((10, 12, 18), (20, 24, 36))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 0, W, 8], fill=color)
    draw.ellipse([W // 2 - 70, 140, W // 2 + 70, 280], fill=color)
    center_text(draw, stage, 320, F_TITLE)
    for i, wl in enumerate(wrap_lines(detail, F_SUB, 980)):
        center_text(draw, wl, 420 + i * 50, F_SUB, fill=(210, 220, 235))
    return img


SCENES = [
    # title ~4s
    (slide("SECOND UNIT", ["Autonomous studio crew", "Brief → rights-cleared cut"], badge="AGENTIC CINEMA"), 4.0),
    # problem ~18s
    (slide("The problem", [
        "Marketing needs a 20s reel today.",
        "Archives are huge. Rights are unclear.",
        "Approval is email chains. Weeks, not minutes.",
    ], accent=(255, 107, 122), badge="PAIN"), 12.0),
    (beat_card("4 WEEKS", "Typical rights-cleared social cut", (240, 180, 41)), 6.0),
    # brief ~20s
    (slide("1. Creative brief in", [
        "“20s energetic Instagram reel about stadium football for the US”",
        "Director parses duration · platform · mood · territory",
    ], badge="DIRECTOR"), 10.0),
    (beat_card("RESEARCHER", "Partner Archive MCP pulls candidates", (110, 168, 255)), 8.0),
    # edit ~15s
    (slide("2. Editor assembles the cut", [
        "Selects & sequences clips to duration",
        "Emits EDL + proxy rough-cut",
        "Gemini captions + platform metadata",
    ], accent=(53, 208, 186), badge="EDITOR"), 12.0),
    # clearance ~30s
    (slide("3. Clearance Officer — the moat", [
        "check_clip_rights on every asset",
        "Restricted / unknown → find_cleared_alternative",
        "Swaps on camera. Audit every decision.",
    ], accent=(180, 140, 255), badge="RIGHTS MCP"), 14.0),
    (beat_card("SWAP", "Restricted promo → cleared alternative", (240, 180, 41)), 8.0),
    (beat_card("CLEARED", "All assets licensed for platform + territory", (61, 214, 140)), 8.0),
    # gate ~35s
    (slide("4. Studio Head gate", [
        "Awaiting Releasing Producer sign-off",
        "before_tool_callback blocks publish in code",
        "Not a UI toggle — real IAM enforcement",
    ], accent=(180, 140, 255), badge="GOVERNANCE"), 12.0),
    (beat_card("DENIED BY IAM", "briefSubmitter cannot approve release", (255, 107, 122)), 10.0),
    (beat_card("APPROVED", "roles/secondunit.releasingProducer", (61, 214, 140)), 10.0),
    # delivery ~20s
    (slide("5. Governed delivery", [
        "Distributor publishes release package",
        "EDL + rough cut + clearance report + audit trail",
        "Cloud Logging correlates every stage",
    ], accent=(53, 208, 186), badge="DISTRIBUTOR"), 12.0),
    (beat_card("AUDIT TRAIL", "Every decision exportable. Enterprise-ready.", (110, 168, 255)), 8.0),
    # close ~20s
    (slide("Brief to rights-cleared cut", [
        "in minutes, not weeks.",
        "Gemini · Google Cloud ADK · Partner MCP · Rights MCP · IAM",
    ], badge="SECOND UNIT"), 10.0),
    (slide("Try the live demo", [
        "second-unit-dashboard-fytheknb4a-el.a.run.app",
        "github.com/Shrutika-211998/agentic-cinema-hermes",
    ], accent=(110, 168, 255)), 10.0),
]


def write_trailer():
    import imageio.v2 as imageio

    frames = []
    total = 0.0
    for img, secs in SCENES:
        n = max(1, int(secs * FPS))
        arr = np.asarray(img)
        for _ in range(n):
            frames.append(arr)
        total += secs
        print(f"  scene {secs:.1f}s → {n} frames")

    path = OUT / "second-unit-trailer.mp4"
    # imageio-ffmpeg writer
    writer = imageio.get_writer(
        str(path),
        fps=FPS,
        codec="libx264",
        quality=8,
        pixelformat="yuv420p",
        macro_block_size=1,
    )
    for f in frames:
        writer.append_data(f)
    writer.close()
    print(f"trailer written: {path} ({total:.1f}s, {len(frames)} frames)")
    return path, total


def write_proxy_clips():
    """Simple branded color bars as stand-in proxies for demo library."""
    import imageio.v2 as imageio

    clips = [
        ("stadium_roar_01.mp4", (30, 80, 160), "STADIUM ROAR"),
        ("stadium_lights_02.mp4", (20, 40, 90), "STADIUM LIGHTS"),
        ("player_sprint_03.mp4", (160, 60, 40), "PLAYER SPRINT"),
        ("cleared_montage_25.mp4", (40, 120, 90), "CLEARED MONTAGE"),
        ("confetti_alt_21.mp4", (140, 90, 40), "CONFETTI ALT"),
        ("aerial_pitch_12.mp4", (30, 100, 60), "AERIAL PITCH"),
    ]
    written = []
    for name, color, label in clips:
        img = Image.new("RGB", (640, 360), color)
        draw = ImageDraw.Draw(img)
        draw.rectangle([0, 0, 640, 8], fill=(255, 255, 255))
        draw.text((24, 150), label, font=F_BODY, fill=(255, 255, 255))
        draw.text((24, 300), "Second Unit proxy", font=F_SMALL, fill=(220, 220, 220))
        arr = np.asarray(img)
        path = PROXIES / name
        w = imageio.get_writer(str(path), fps=12, codec="libx264", quality=7, pixelformat="yuv420p", macro_block_size=1)
        for _ in range(36):  # 3s
            w.append_data(arr)
        w.close()
        written.append(path)
        print("proxy", path)
    return written


if __name__ == "__main__":
    print("Generating trailer...")
    trailer, dur = write_trailer()
    print("Generating proxies...")
    proxies = write_proxy_clips()
    print("DONE", trailer, f"{dur:.1f}s", "proxies", len(proxies))
