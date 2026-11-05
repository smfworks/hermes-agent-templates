#!/usr/bin/env python3
"""1080x1920 title, line, and end cards."""

from __future__ import annotations

import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

W, H = 1080, 1920
BG = (11, 11, 18)
GOLD = (201, 162, 39)
WHITE = (245, 245, 240)
MUTED = (168, 168, 178)
END_BAR = (80, 1640, 1000, 1688)

FONT_CANDIDATES = [
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/liberation/LiberationSans-Regular.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
    Path("/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf"),
]
BOLD_CANDIDATES = [
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/liberation/LiberationSans-Bold.ttf"),
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans-Bold.ttf"),
    Path("/usr/share/fonts/Adwaita/AdwaitaSans-Regular.ttf"),
]


def _load(candidates: list[Path], size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in candidates:
        if path.is_file():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font, width: int) -> list[str]:
    # Character wrap, then verify pixel width.
    lines: list[str] = []
    for para in text.splitlines() or [""]:
        if not para:
            lines.append("")
            continue
        for raw in textwrap.wrap(para, width=28) or [""]:
            lines.append(raw)
    return lines


def _draw_wrapped(draw, text, font, fill, top: int) -> int:
    y = top
    for line in _wrap(draw, text, font, 900):
        draw.text((90, y), line, font=font, fill=fill)
        y += int(font.size * 1.25) if hasattr(font, "size") else 48
    return y


def _base() -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)
    draw.rectangle((0, 0, W, 12), fill=GOLD)
    return img, draw


def title_card(path: Path, title: str) -> None:
    img, draw = _base()
    kicker = _load(FONT_CANDIDATES, 28)
    heading = _load(BOLD_CANDIDATES, 64)
    draw.text((90, 220), "EXPLAIN IT LIKE A MOVIE", font=kicker, fill=GOLD)
    _draw_wrapped(draw, title, heading, WHITE, 320)
    draw.text((90, 1760), "SMF Works", font=kicker, fill=MUTED)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def line_card(path: Path, label: str, text: str, cite: int, on_screen: str) -> None:
    img, draw = _base()
    kicker = _load(FONT_CANDIDATES, 28)
    body = _load(FONT_CANDIDATES, 48)
    small = _load(FONT_CANDIDATES, 32)
    draw.text((90, 200), label.upper(), font=kicker, fill=GOLD)
    _draw_wrapped(draw, text, body, WHITE, 280)
    draw.text((90, 1500), f"[{cite}]", font=small, fill=MUTED)
    _draw_wrapped(draw, on_screen, small, MUTED, 1560)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def end_card(path: Path) -> None:
    img, draw = _base()
    heading = _load(BOLD_CANDIDATES, 64)
    body = _load(FONT_CANDIDATES, 36)
    draw.rectangle(END_BAR, fill=GOLD)
    draw.text((90, 720), "Made with AI", font=heading, fill=WHITE)
    _draw_wrapped(draw, "Try Hermes: Explain It Like a Movie by SMF Works", body, MUTED, 840)
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(path, "PNG")


def poster(path: Path, title: str) -> None:
    title_card(path, title)
