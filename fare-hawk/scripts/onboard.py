#!/usr/bin/env python3
"""One onboarding field per call. No scheduler writes."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import timedelta
from pathlib import Path

from store import civil_date, load_json, mutate_json

INTRO = (
    "Tell me where and when. In 10 minutes you'll have a day-by-day itinerary card, "
    "3 flight and hotel options, and a price watch that pings you when fares drop. "
    "You book; I watch and report."
)
INTEGRATIONS = (
    "v1 does not write mail, calendar, or Drive, and it does not execute a booking."
)
FIELDS = (
    "home",
    "dest",
    "dates",
    "party",
    "cabin",
    "bags",
    "pace",
    "budget",
    "interests",
    "loyalty",
    "integrations",
    "threshold",
    "watch",
)
PROMPTS = {
    "home": "Which home airports?\nChoices: BOS / PVD / JFK / EWR",
    "dest": "Where to?",
    "dates": "Which dates?",
    "party": "How many adults and children?",
    "cabin": "Which cabin?\nChoices: economy / premium / business / first",
    "bags": "How many checked bags?",
    "pace": "What pace?\nChoices: light / balanced / packed",
    "budget": "What budget?\nChoices: modest / mid / comfortable",
    "interests": "What interests?\nChoices: food / museums / outdoors / neighborhoods",
    "loyalty": "Any loyalty program names?",
    "integrations": INTEGRATIONS,
    "threshold": "What drop threshold?",
    "watch": "Turn the price watch on?",
}
SECRET_RE = re.compile(r"password|passport|\d{13,}", re.IGNORECASE)
RELATIVE_RE = re.compile(r"in (\d+) days for (\d+) nights")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record one Fare Hawk setup field.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--value")
    parser.add_argument("--skip", action="store_true")
    parser.add_argument("--now", default="2026-11-06T15:00:00Z")
    parser.add_argument("--tz", default="America/New_York")
    return parser.parse_args(argv)


def add_skipped(state: dict, field: str) -> None:
    skipped = list(state.get("skipped") or [])
    if field not in skipped:
        skipped.append(field)
    state["skipped"] = skipped


def parse_dates(value: str, now: str, tz: str):
    if ".." in value:
        start, end = value.split("..", 1)
        return {"start": start.strip(), "end": end.strip()}
    match = RELATIVE_RE.fullmatch(value.strip())
    if not match:
        return None
    start = civil_date(now, tz) + timedelta(days=int(match.group(1)))
    end = start + timedelta(days=int(match.group(2)))
    return {"start": start.isoformat(), "end": end.isoformat()}


def parse_party(value: str) -> dict:
    parts = [part.strip() for part in value.split("+") if part.strip()]
    adults = int(parts[0])
    children = [int(part) for part in parts[1:]]
    return {"adults": adults, "children": children}


def stored_value(step: str, value: str, now: str, tz: str):
    if step == "home":
        return [part.strip() for part in value.split(",") if part.strip()]
    if step == "dates":
        return parse_dates(value, now, tz)
    if step == "party":
        return parse_party(value)
    if step == "bags":
        return int(value)
    if step == "loyalty":
        return [part.strip() for part in value.split(",") if part.strip()]
    if step == "watch":
        lowered = value.strip().casefold()
        if lowered in {"yes", "true", "y"}:
            return True
        if lowered in {"no", "false", "n"}:
            return False
        return None
    return value


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    path = Path(args.data) / "state.json"
    if args.step == "intro":
        state = load_json(path)
        if state.get("setup_step"):
            print("resume")
        print(INTRO)

        def mark_intro(current: dict) -> None:
            current["setup_step"] = "intro_done"

        mutate_json(path, mark_intro)
        return 0
    if args.step not in FIELDS:
        print("Unknown field.", file=sys.stderr)
        return 2
    if args.skip or (args.value or "").strip().casefold() == "later":
        def mark_skip(current: dict) -> None:
            add_skipped(current, args.step)
            if args.step == "loyalty":
                current["loyalty"] = "skipped"
            elif args.step == "threshold":
                current["threshold"] = {"mode": "default_usd", "amount": "25", "percent": "5"}
            elif args.step == "watch":
                current["watch_yes"] = False
            else:
                current[args.step] = "skipped"

        mutate_json(path, mark_skip)
        if args.step == "integrations":
            print(INTEGRATIONS)
        return 0
    if args.value is None:
        print(PROMPTS[args.step])
        return 2
    if args.step == "loyalty" and SECRET_RE.search(args.value):
        print("Loyalty stores a program name only. Refused.", file=sys.stderr)
        return 2
    value = stored_value(args.step, args.value, args.now, args.tz)
    if value is None:
        print(PROMPTS[args.step])
        return 2

    def save(current: dict) -> None:
        if args.step == "watch":
            current["watch_yes"] = value
        else:
            current[args.step] = value

    mutate_json(path, save)
    if args.step == "integrations":
        print(INTEGRATIONS)
    else:
        print(f"Saved {args.step}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
