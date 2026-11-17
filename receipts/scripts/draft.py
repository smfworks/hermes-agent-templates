#!/usr/bin/env python3
"""Write a cancel or refund draft as .eml. Never sends."""

from __future__ import annotations

import argparse
import sys
from email.message import EmailMessage
from pathlib import Path, PurePosixPath

from store import atomic_write

TO_MAP = {
    "netflix": "help@netflix.com",
    "spotify": "support@spotify.com",
    "dropbox": "support@dropbox.com",
    "disney+": "help@disneyplus.com",
    "disney": "help@disneyplus.com",
}

# The fallback address is derived from the service name. safe_service() has
# already restricted the value to a single-line, single-path-name label, so
# the derived domain is RFC-clean and the draft is EmailMessage-encoded —
# header injection (hsf_01f59bcf) is structurally impossible.


def safe_service(raw: str) -> str:
    """Validate the --service value once, for both mechanisms it feeds:
    the drafts filename (hsf_c1ee8922) and the To:/Subject: headers
    (hsf_01f59bcf). Returns the cleaned key, or falls back to a fixed name."""
    text = (raw or "").strip()
    # Header injection: CR/LF anywhere means the value must never reach a
    # header or a path; fall back rather than trying to sanitize prose.
    if "\r" in text or "\n" in text:
        return "unknown-service"
    # Traversal: the slug becomes a filename under data/drafts/ — the value
    # must be a single path name, nothing more.
    if ("/" in text or "\\" in text or ".." in text
            or text != PurePosixPath(text.replace("\\", "_")).name
            or text in (".", "..")):
        return "unknown-service"
    return text


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
    service = safe_service(args.service)
    key = service.casefold()
    if key in TO_MAP:
        to_addr = TO_MAP[key]
    else:
        to_addr = f"support@{key.replace(' ', '')}.com"
    if args.kind == "refund":
        subject = f"Refund request for {service}"
        body = (
            f"Hello,\n\nPlease refund my {service} charges. "
            "I am writing this myself and will send it if I choose.\n"
        )
    else:
        subject = f"Please cancel my {service} subscription"
        body = (
            f"Hello,\n\nPlease cancel my {service} subscription at the end of "
            "the current period. Do not charge me again.\n"
        )
    # Build the .eml with EmailMessage so headers are RFC 5322-encoded: a
    # header value can never fold a new header into the draft (hsf_01f59bcf).
    msg = EmailMessage()
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    eml = msg.as_string()
    slug = service.lower().replace(" ", "-").replace("+", "plus")
    slug = PurePosixPath(slug).name or "unknown-service"
    path = drafts / f"{slug}-{args.kind}.eml"
    atomic_write(path, eml)
    print(body, end="" if body.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
