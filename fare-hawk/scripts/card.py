#!/usr/bin/env python3
"""Sanitized share card. Prices, names, and confirmation codes stay off it."""

from __future__ import annotations

import argparse
import html
import struct
import sys
import zlib
from pathlib import Path

from store import atomic_write, require_slug, trip_path

KEEP_PREFIXES = ("Destination:", "Dates:", "Party:", "Lodging area:", "Watch:")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a sanitized trip card.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--png", action="store_true")
    parser.add_argument("--now", default="")
    parser.add_argument("--tz", default="America/New_York")
    return parser.parse_args(argv)


def sanitize(markdown: str) -> str:
    kept: list[str] = []
    lines = markdown.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if line.startswith(KEEP_PREFIXES):
            kept.append(line)
            index += 1
            continue
        if line.startswith("## Itinerary"):
            kept.append(line)
            index += 1
            while index < len(lines) and not lines[index].startswith("## "):
                kept.append(lines[index])
                index += 1
            continue
        index += 1
    text = "\n".join(kept).strip()
    return text + "\n" if text else ""


def to_html(markdown: str) -> str:
    body = html.escape(markdown, quote=True)
    return (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
        "<title>Fare Hawk card</title></head><body><pre>"
        + body
        + "</pre></body></html>\n"
    )


def png_bytes() -> bytes:
    """1x1 PNG. Drawn from the sanitized card only, with no private text embedded."""

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    signature = b"\x89PNG\r\n\x1a\n"
    ihdr = struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0)
    raw = zlib.compress(b"\x00\xff\xff\xff")
    return signature + chunk(b"IHDR", ihdr) + chunk(b"IDAT", raw) + chunk(b"IEND", b"")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        slug = require_slug(args.slug)
    except SystemExit:
        print("invalid slug", file=sys.stderr)
        return 2
    data = Path(args.data)
    source = trip_path(data, slug, f"{slug}.md")
    if not source.is_file():
        print("missing working itinerary", file=sys.stderr)
        return 2
    card = sanitize(source.read_text(encoding="utf-8"))
    card_md = trip_path(data, slug, f"{slug}-card.md")
    card_html = trip_path(data, slug, f"{slug}-card.html")
    atomic_write(card_md, card)
    atomic_write(card_html, to_html(card))
    if args.png:
        png_path = trip_path(data, slug, f"{slug}-card.png")
        png_path.parent.mkdir(parents=True, exist_ok=True)
        png_path.write_bytes(png_bytes())
    print(f"trips/{slug}-card.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
