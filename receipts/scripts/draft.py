#!/usr/bin/env python3
"""Write a cancel or refund draft as .eml. Never sends."""

from __future__ import annotations

import argparse
from pathlib import Path

from store import atomic_write

TO_MAP = {
    "netflix": "help@netflix.com",
    "spotify": "support@spotify.com",
    "dropbox": "support@dropbox.com",
    "disney+": "help@disneyplus.com",
    "disney": "help@disneyplus.com",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Draft a cancel or refund email.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--service", required=True)
    parser.add_argument("--kind", choices=("cancel", "refund"), default="cancel")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = Path(args.data)
    drafts = data / "drafts"
    drafts.mkdir(parents=True, exist_ok=True)
    key = args.service.casefold()
    to_addr = TO_MAP.get(key, f"support@{key.replace(' ', '')}.com")
    if args.kind == "refund":
        subject = f"Refund request for {args.service}"
        body = (
            f"Hello,\n\nPlease refund my {args.service} charges. "
            "I am writing this myself and will send it if I choose.\n"
        )
    else:
        subject = f"Please cancel my {args.service} subscription"
        body = (
            f"Hello,\n\nPlease cancel my {args.service} subscription at the end of "
            "the current period. Do not charge me again.\n"
        )
    eml = f"To: {to_addr}\nSubject: {subject}\n\n{body}"
    slug = args.service.lower().replace(" ", "-").replace("+", "plus")
    path = drafts / f"{slug}-{args.kind}.eml"
    atomic_write(path, eml)
    print(body, end="" if body.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
