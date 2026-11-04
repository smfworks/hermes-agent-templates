#!/usr/bin/env python3
"""Provider cancel steps and link. Never asks for a password. Never submits."""

from __future__ import annotations

import argparse

LINKS = {
    "netflix": "https://www.netflix.com/cancel",
    "spotify": "https://www.spotify.com/account/subscription/",
    "dropbox": "https://www.dropbox.com/account",
    "disney+": "https://www.disneyplus.com/account",
    "disney": "https://www.disneyplus.com/account",
    "adobe": "https://account.adobe.com/",
    "github": "https://github.com/settings/billing",
}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Cancel help.")
    parser.add_argument("--service", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    key = args.service.casefold()
    link = LINKS.get(key, f"https://www.google.com/search?q={args.service}+cancel+subscription")
    print(f"Cancel help for {args.service}.")
    print("1. Open the account page in your own browser.")
    print(f"2. Link: {link}")
    print("3. Follow the provider's cancel steps.")
    print("I will not log in, submit a form, or send mail. Ask if you want a draft.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
