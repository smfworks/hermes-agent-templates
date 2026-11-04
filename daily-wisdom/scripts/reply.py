#!/usr/bin/env python3
"""Record one night reply, then recompute the streak from sittings.csv."""

from __future__ import annotations

import argparse
import sys
from datetime import date, timedelta
from pathlib import Path

from sitting import atomic_write, load_state, read_sittings, save_state, write_sittings

THANKS = "Thank you. That one line is enough."


def as_int(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def consecutive_ending(replied: set[date], end: date) -> int:
    streak = 0
    cursor = end
    while cursor in replied:
        streak += 1
        cursor -= timedelta(days=1)
    return streak


def longest_run(replied: set[date]) -> int:
    best = 0
    for day in replied:
        if day - timedelta(days=1) in replied:
            continue
        run = 1
        cursor = day + timedelta(days=1)
        while cursor in replied:
            run += 1
            cursor += timedelta(days=1)
        best = max(best, run)
    return best


def append_note(path: Path, day: str, note: str) -> None:
    existing = path.read_text(encoding="utf-8") if path.is_file() else ""
    one_line = " ".join(note.splitlines()).strip()
    addition = f"{day} | {day} | {one_line}\n"
    atomic_write(path, existing + addition)


def mark_replied(data: Path, day: date, note: str) -> None:
    day_s = day.isoformat()
    csv_path = data / "sittings.csv"
    rows = read_sittings(csv_path)
    found = False
    for row in rows:
        if row["date"] == day_s:
            row["replied"] = "y"
            found = True
    if not found:
        raise SystemExit(f"no sitting logged for {day_s}")
    write_sittings(csv_path, rows)
    append_note(data / "notes.md", day_s, note)
    replied = {
        date.fromisoformat(row["date"])
        for row in rows
        if row["replied"] == "y"
    }
    state_path = data / "state.json"
    state = load_state(state_path)
    streak = consecutive_ending(replied, day)
    state["streak"] = streak
    state["longest"] = max(as_int(state.get("longest")), longest_run(replied), streak)
    state["last_reply_date"] = day_s
    save_state(state_path, state)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record a one-line night reply.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--date", required=True)
    parser.add_argument("--note", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    mark_replied(Path(args.data), date.fromisoformat(args.date), args.note)
    sys.stdout.write(THANKS + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
