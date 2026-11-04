#!/usr/bin/env python3
"""Print a text-only card of one day's reading. Never reads notes.md."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from sitting import read_sittings


def card(data: Path, day: str) -> str:
    for row in read_sittings(data / "sittings.csv"):
        if row["date"] == day:
            lines = row["reading"].replace("\r\n", "\n").splitlines()
            if not lines:
                raise SystemExit(f"sitting {day} has no reading lines")
            return "\n".join(lines) + "\n"
    raise SystemExit(f"no sitting logged for {day}")


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Text-only quote card for one date.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--date", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sys.stdout.write(card(Path(args.data), args.date))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
