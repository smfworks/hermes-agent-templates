#!/usr/bin/env python3
"""Onboarding. One question per turn. Cron waits for yes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from store import INTRO, mutate_json

QUESTIONS = {
    "use": "What's your main AI use: coding, writing, research, running a business, or just curious?",
    "stack": "Which tools or models do you care about? Coding agents, chat models, local weights, or something else?",
    "when": "What time should the brief arrive, and in which timezone? I suggest 07:00 local.",
    "style": "Quick or Standard for the write-up?",
    "delivery": "Deliver to a configured private gateway, or CLI/file only?",
    "daily-offer": "Want a Daily Brief at that time, with a Friday wrap on Fridays? I can add a cron job. Should I?",
    "monthly-offer": "Want a Monthly Tune-Up on the first Monday? Should I?",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Radar onboarding")
    parser.add_argument("--data", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--answer", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.data) / "profile.json"

    def set_step(state: dict, **updates: object) -> None:
        state.update(updates)

    if args.step == "intro":
        mutate_json(path, lambda state: set_step(state, setup_step="intro_done"))
        print(INTRO)
        return 0
    if args.step in QUESTIONS and not str(args.answer).strip():
        print(QUESTIONS[args.step])
        return 0
    if args.step == "use":
        mutate_json(path, lambda state: set_step(state, use=args.answer.strip(), setup_step="use_done"))
        print(args.answer.strip())
        return 0
    if args.step == "stack":
        mutate_json(path, lambda state: set_step(state, stack=args.answer.strip(), setup_step="stack_done"))
        print(args.answer.strip())
        return 0
    if args.step == "when":
        mutate_json(path, lambda state: set_step(state, when=args.answer.strip(), setup_step="when_done"))
        print(args.answer.strip())
        return 0
    if args.step == "style":
        style = args.answer.strip().casefold()
        if style not in {"quick", "standard"}:
            print("Please pick quick or standard.", file=sys.stderr)
            return 1
        mutate_json(path, lambda state: set_step(state, style=style, setup_step="style_done"))
        print(style)
        return 0
    if args.step == "delivery":
        mutate_json(
            path,
            lambda state: set_step(state, delivery=args.answer.strip(), setup_step="delivery_done"),
        )
        print(args.answer.strip())
        return 0
    if args.step in {"daily-offer", "monthly-offer"}:
        print(QUESTIONS[args.step])
        return 0
    print("Unknown step.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
