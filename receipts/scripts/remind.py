#!/usr/bin/env python3
"""Daily renewal reminders. One per service+date. Never repeats."""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from mail_fetch import parse_now
from store import load_state, read_csv, save_state, window_days


def in_window(row: dict, now: date, window: int) -> bool:
    nxt = row.get("next_renewal") or ""
    try:
        renew = date.fromisoformat(nxt)
    except ValueError:
        return False
    delta = (renew - now).days
    return 0 <= delta <= window


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Renewal reminders.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--now")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = Path(args.data)
    now = parse_now(args.now)
    state = load_state(data / "state.json")
    window = window_days(state)
    reminded = state.get("reminded")
    if not isinstance(reminded, dict):
        reminded = {}
    else:
        reminded = dict(reminded)
    rows = read_csv(data / "subscriptions.csv")
    lines = []
    for row in rows:
        if row.get("status") not in {"active", "trial"}:
            continue
        if not in_window(row, now, window):
            continue
        key = f"{row['service']}|{row.get('next_renewal')}"
        if reminded.get(key):
            continue
        amount = row.get("amount") or "unknown"
        lines.append(
            f"{row['service']} {amount} on {row.get('next_renewal')} — keep / cancel help / snooze"
        )
        reminded[key] = True
    if lines:
        save_state(data / "state.json", {"reminded": reminded})
        print("\n".join(lines) + "\n", end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
