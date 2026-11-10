#!/usr/bin/env python3
"""Adjust topic weights from thumbs and 'more/less' replies."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from store import load_json, write_json


def apply_feedback(weights: dict, topic: str, direction: str, now: str) -> tuple[dict, str]:
    info = dict(weights.get(topic) or {"rank": 0, "downs": 0, "only_if_major": False})
    if direction in {"down", "less"}:
        info["rank"] = int(info.get("rank") or 0) - 1
        info["downs"] = int(info.get("downs") or 0) + 1
        if info["downs"] >= 3:
            info["only_if_major"] = True
            line = f"{topic}: only if major. Material updates still come through."
        else:
            line = f"{topic}: ranked lower, still in the mix."
    else:
        info["rank"] = int(info.get("rank") or 0) + 1
        line = f"{topic}: ranked higher."
    info["at"] = now
    weights[topic] = info
    return weights, line


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Radar topic feedback")
    parser.add_argument("--data", required=True)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--dir", required=True, choices=["up", "down", "more", "less"])
    parser.add_argument("--now", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.data) / "topic-weights.json"
    weights = load_json(path, default={})
    if not isinstance(weights, dict):
        weights = {}
    direction = "down" if args.dir in {"down", "less"} else "up"
    weights, line = apply_feedback(weights, args.topic, direction, args.now)
    write_json(path, weights)
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
