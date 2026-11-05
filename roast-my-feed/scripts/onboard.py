#!/usr/bin/env python3
"""Onboarding steps. The weekly cron is offered here and installed only by install_cron --yes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from store import INTRO, save_state, strip_handle


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Roast My Feed onboarding")
    parser.add_argument("--data", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--handle", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    state_path = Path(args.data) / "state.json"
    if args.step == "intro":
        save_state(state_path, {"setup_step": "intro_done"})
        print(INTRO)
        return 0
    if args.step == "handle":
        if not str(args.handle).strip():
            print("A handle is required.", file=sys.stderr)
            return 1
        handle = strip_handle(args.handle)
        save_state(state_path, {"handle": handle})
        print(handle)
        return 0
    if args.step == "weekly-offer":
        print(
            "Want a weekly Monday re-roast? "
            "I can add a Monday morning cron. Should I?"
        )
        return 0
    print("Unknown step.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
