#!/usr/bin/env python3
"""Onboarding steps. First scan and report before window/cadence. Cron is separate."""

from __future__ import annotations

import argparse
from pathlib import Path

from mail_fetch import parse_now
from page import run_page
from scan import run_scan
from store import load_state, save_state

INTRO = (
    "I'm Receipts, your money-back bot. Connect your email and in about 5 minutes "
    "I'll show you every subscription I can find, what renews this week, and your "
    "top 3 cancel candidates. I never cancel or send anything without your OK. "
    "Gmail or IMAP?"
)
WINDOW_Q = "Heads-up before charges: 3, 5 (default) or 7 days?"
CADENCE_Q = "Scan cadence: weekly Sunday 9:00 AM (default), daily 8:00 AM, or on demand only?"


def step_intro(data: Path) -> str:
    state = load_state(data / "state.json")
    lines = [INTRO]
    if state.get("setup_step"):
        lines.append(f"Resume from {state['setup_step']}? Say start over to reset.")
    save_state(data / "state.json", {"setup_step": "intro_done"})
    return "\n".join(lines) + "\n"


def step_email(data: Path, backend: str, account: str) -> str:
    save_state(
        data / "state.json",
        {"setup_step": "email_done", "backend": backend, "account": account},
    )
    if not account and backend != "fixtures":
        return (
            "No mail connected. Forward or paste receipts here, or drop .eml files "
            "in money-back/inbox/. I will not stall.\n"
        )
    return f"Email source recorded: {backend}. Scanning next.\n"


def step_scan(data: Path, inbox: Path | None, now, backend: str) -> str:
    run_scan(data, inbox, now, backend)
    run_page(data, now)
    save_state(data / "state.json", {"setup_step": "scanned"})
    report = data / "money-back.md"
    return (
        f"First scan is in. Report: {report}\n"
        f"{WINDOW_Q}\n"
    )


def step_window(data: Path, skip: bool, value: int | None) -> str:
    window = 5 if skip or value is None else value
    save_state(data / "state.json", {"setup_step": "window_done", "window": window})
    return f"Heads-up window: {window} days.\n{CADENCE_Q}\n"


def step_cadence(data: Path, skip: bool, cadence: str | None) -> str:
    chosen = "weekly" if skip or not cadence else cadence
    save_state(
        data / "state.json",
        {
            "setup_step": "cadence_done",
            "cadence": chosen,
            "tz": "America/New_York",
        },
    )
    return (
        f"Cadence: {chosen}. Timezone: America/New_York. "
        "Say yes to install the two cron jobs.\n"
    )


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Receipts onboarding.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--step", required=True)
    parser.add_argument("--backend", default="fixtures")
    parser.add_argument("--account", default="")
    parser.add_argument("--inbox")
    parser.add_argument("--now")
    parser.add_argument("--skip", action="store_true")
    parser.add_argument("--window", type=int)
    parser.add_argument("--cadence")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = Path(args.data)
    data.mkdir(parents=True, exist_ok=True)
    if args.step == "intro":
        print(step_intro(data), end="")
        return 0
    if args.step == "email":
        print(step_email(data, args.backend, args.account), end="")
        return 0
    if args.step == "scan":
        now = parse_now(args.now)
        inbox = Path(args.inbox) if args.inbox else data / "inbox"
        print(step_scan(data, inbox, now, args.backend), end="")
        return 0
    if args.step == "window":
        print(step_window(data, args.skip, args.window), end="")
        return 0
    if args.step == "cadence":
        print(step_cadence(data, args.skip, args.cadence), end="")
        return 0
    raise SystemExit(f"unknown step {args.step}")


if __name__ == "__main__":
    raise SystemExit(main())
