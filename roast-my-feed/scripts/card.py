#!/usr/bin/env python3
"""Text share card and a local PNG. No bios, follower counts, or post bodies."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from store import FOOTER, read_jsonl, strip_handle

ARCHETYPES = {
    "link_only": "Link Drop Machine",
    "emoji_only": "Emoji Stamp Habit",
    "reply_heavy": "Reply Lane Regular",
    "no_hook": "Soft Open Poster",
}


def archetype_for(habit: str) -> str:
    return ARCHETYPES.get(habit, "Steady Poster")


def share_card_text(handle: str, summary: dict | None, archetype: str) -> str:
    lines = [
        f"Share card for {handle}",
        f"Archetype: {archetype}",
    ]
    if summary:
        if "posts_in_window" in summary:
            lines.append(f"Posts in window: {int(summary['posts_in_window'])}")
        if "worst_habit" in summary:
            count = int(summary.get("worst_habit_count", 0))
            lines.append(f"Worst habit: {summary['worst_habit']} ({count})")
        if summary.get("best_post_id"):
            lines.append(f"Best post id: {summary['best_post_id']}")
    lines.append(FOOTER)
    return "\n".join(lines) + "\n"


def write_png(path: Path, text: str) -> None:
    from PIL import Image, ImageDraw

    image = Image.new("RGB", (960, 540), (24, 24, 28))
    draw = ImageDraw.Draw(image)
    draw.rectangle((24, 24, 936, 516), outline=(255, 196, 64), width=4)
    y = 48
    for line in text.splitlines():
        draw.text((48, y), line, fill=(255, 255, 255))
        y += 22
        if y > 500:
            break
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path, format="PNG")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the Roast My Feed share card")
    parser.add_argument("--data", required=True)
    parser.add_argument("--handle", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    handle = strip_handle(args.handle)
    data = Path(args.data)
    history = read_jsonl(data / "history.jsonl")
    summary = history[-1] if history else None
    habit = str(summary.get("worst_habit")) if summary else "no_hook"
    text = share_card_text(handle, summary, archetype_for(habit))
    write_png(data / "roast" / handle / "card.png", text)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
