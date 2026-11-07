#!/usr/bin/env python3
"""Onboarding steps. A pasted claim interrupts setup. Weekly cron waits for yes."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from store import FOCUS_CHOICES, INTRO, STYLE_CHOICES, save_state

QUESTIONS = {
    "focus": (
        "What should I focus on: benchmarks, pricing, agent or tool capabilities, or all?"
    ),
    "evaluators": (
        "Any evaluators you trust or distrust? Balanced by default if you skip."
    ),
    "style": "Card or Brief for the write-up?",
    "weekly-offer": (
        "Want a weekly saved-claim re-check? I suggest Monday 8 AM in your timezone. Should I?"
    ),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AI Claim Checker onboarding")
    parser.add_argument("--data", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--answer", default="")
    parser.add_argument("--claim", default="")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    state_path = Path(args.data) / "state.json"
    if str(args.claim).strip():
        save_state(
            state_path,
            {
                "setup_interrupted": True,
                "pending_claim": args.claim.strip(),
                "setup_step": "interrupted",
            },
        )
        print("A real claim arrived. I will check it now, then finish setup.")
        return 0
    if args.step == "intro":
        save_state(state_path, {"setup_step": "intro_done"})
        print(INTRO)
        return 0
    if args.step == "focus":
        answer = (args.answer or "").strip().casefold()
        if answer:
            if answer not in FOCUS_CHOICES:
                print("Please pick benchmarks, pricing, capabilities, or all.", file=sys.stderr)
                return 1
            save_state(state_path, {"focus": answer, "setup_step": "focus_done"})
            print(answer)
            return 0
        print(QUESTIONS["focus"])
        return 0
    if args.step == "evaluators":
        answer = (args.answer or "").strip()
        if answer:
            save_state(
                state_path,
                {"evaluators": answer, "setup_step": "evaluators_done"},
            )
            print(answer)
            return 0
        print(QUESTIONS["evaluators"])
        return 0
    if args.step == "style":
        answer = (args.answer or "").strip().casefold()
        if answer:
            if answer not in STYLE_CHOICES:
                print("Please pick card or brief.", file=sys.stderr)
                return 1
            save_state(state_path, {"style": answer, "setup_step": "style_done"})
            print(answer)
            return 0
        print(QUESTIONS["style"])
        return 0
    if args.step == "weekly-offer":
        print(QUESTIONS["weekly-offer"])
        return 0
    print("Unknown step.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
