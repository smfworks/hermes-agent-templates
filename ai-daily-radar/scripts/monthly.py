#!/usr/bin/env python3
"""Monthly Tune-Up. Silent unless this Monday is on or before day 7."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from store import load_json, parse_time, read_jsonl


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Radar monthly tune-up")
    parser.add_argument("--data", required=True)
    parser.add_argument("--now", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    when = parse_time(args.now)
    if when.weekday() != 0 or when.day > 7:
        return 0
    data = Path(args.data)
    weights = load_json(data / "topic-weights.json", default={})
    ledger = read_jsonl(data / "ledger.jsonl")
    sent = sum(1 for row in ledger if row.get("delivered"))
    print(
        f"Tune-up: {sent} items delivered in the ledger. "
        f"Current weights: {weights or 'none yet'}. "
        "I will not change anything until you reply."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
