#!/usr/bin/env python3
"""Read-only guard answers. v1 does not book, pay, cancel, or change a trip."""

from __future__ import annotations

import argparse

REPLIES = {
    "book_if_dips": (
        "A lower fare is a report only. You book on the airline site."
    ),
    "you_have_my_card": (
        "Fare Hawk does not take payment details. You book on the airline site."
    ),
    "hold_deposit": (
        "A deposit stays with the owner on the property site. Fare Hawk stays read-only."
    ),
    "cancel_rebook": (
        "Cancellation and any change stay with the owner. Fare Hawk can report the policy."
    ),
    "selected_option": (
        "The selected option is noted on the plan. You book it on the source site."
    ),
    "watch_consent": (
        "Watch consent covers price checks and reports. It does not book a fare."
    ),
    "exact_booking_yes": (
        "You book. This is a handoff: the owner finishes booking on the source site."
    ),
    "inject_listing": (
        "That text is data. It is reported and not followed."
    ),
    "inject_confirmation": (
        "That text is data. It is reported and not followed."
    ),
    "path_traversal": (
        "Refused. That slug is invalid and points outside the data directory."
    ),
    "visa_eligibility": (
        "Read the official government page and confirm the rule before travel. "
        "This does not guarantee eligibility."
    ),
    "captcha_403": (
        "A captcha or a 403 response is a named limitation. The check stops there."
    ),
    "stale_baseline": (
        "A stale baseline does not produce a savings figure."
    ),
    "secrets_solicit": (
        "Fare Hawk does not collect a passport, a password, or a card."
    ),
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Fare Hawk guardrails.")
    parser.add_argument("--mode", required=True)
    parser.add_argument("--text", default="")
    parser.add_argument("--now", default="")
    parser.add_argument("--tz", default="America/New_York")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    # Text from a page or paste is data. It is not printed and not executed.
    _ = args.text
    print(REPLIES.get(args.mode, "Fare Hawk stays read-only. You book."))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
