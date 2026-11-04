#!/usr/bin/env python3
"""Text-only share card. Savings line only when verified savings > 0."""

from __future__ import annotations

import argparse
from pathlib import Path

from store import load_state, read_csv


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Share card.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--names", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = Path(args.data)
    rows = read_csv(data / "subscriptions.csv")
    state = load_state(data / "state.json")
    ledger = state.get("saved_ledger") or []
    verified = 0.0
    if isinstance(ledger, list):
        for item in ledger:
            if isinstance(item, dict):
                try:
                    verified += float(item.get("amount") or 0)
                except (TypeError, ValueError):
                    pass
    n = len(rows)
    print(f"found {n} subscriptions")
    if args.names:
        print(" ".join(row["service"] for row in rows))
    if verified > 0:
        print(f"verified savings {verified:.2f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
