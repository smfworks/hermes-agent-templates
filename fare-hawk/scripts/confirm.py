#!/usr/bin/env python3
"""Append a private note. A confirmation updates booking status only."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from store import FileLock, atomic_write, require_slug, trip_path


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Store a private trip note.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--text", required=True)
    parser.add_argument("--now", default="")
    parser.add_argument("--tz", default="America/New_York")
    return parser.parse_args(argv)


def append_private(path: Path, text: str) -> None:
    with FileLock(path):
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        if existing and not existing.endswith("\n"):
            existing += "\n"
        atomic_write(path, existing + text + "\n")


def mark_booked(path: Path) -> None:
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    if "Booking status: booked" in text:
        return
    if "Booking status: planning" in text:
        text = text.replace("Booking status: planning", "Booking status: booked", 1)
        atomic_write(path, text)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        slug = require_slug(args.slug)
    except SystemExit:
        print("invalid slug", file=sys.stderr)
        return 2
    data = Path(args.data)
    private = trip_path(data, slug, f"{slug}-private.md")
    append_private(private, args.text)
    if "confirmation" in args.text.casefold():
        mark_booked(trip_path(data, slug, f"{slug}.md"))
        mark_booked(trip_path(data, slug, f"{slug}.html"))
    print(f"trips/{slug}-private.md")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
