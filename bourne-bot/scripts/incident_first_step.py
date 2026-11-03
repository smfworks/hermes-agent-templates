#!/usr/bin/env python3
"""Map an owner message to the one-line first step already in SOUL.md.

Pure function. No model call. No file reads. No network.
"""

from __future__ import annotations

import re
import sys

EMAIL = "Secure primary email."
DEVICE = "Locate, lock, or remote-erase it from the platform's find-my-device service."
CREDENTIAL = "Rotate the leaked credential and every place it was reused."
DOXX = "Document it with screenshots, URLs, and timestamps."
FINANCIAL = "Freeze credit and call the bank's fraud line."

RULES: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(
            r"hacked email|email (?:was|is|got)[^.!\n]{0,40}hacked|"
            r"hacked account|account compromise|email compromise|suspected account",
            re.I,
        ),
        EMAIL,
    ),
    (
        re.compile(
            r"lost (?:my |the )?(?:phone|device)|stolen (?:my |the )?(?:phone|device)|"
            r"phone was stolen|device was stolen|lost or stolen device",
            re.I,
        ),
        DEVICE,
    ),
    (
        re.compile(
            r"credential leak|leaked credential|leaked password|"
            r"password (?:was )?leaked|credentials leaked",
            re.I,
        ),
        CREDENTIAL,
    ),
    (
        re.compile(r"\bdoxx(?:ed|ing)?\b|\bdox(?:ed|xed|ing)?\b", re.I),
        DOXX,
    ),
    (
        re.compile(
            r"\bfinancial\b|bank fraud|fraudulent charge|unauthorized charge",
            re.I,
        ),
        FINANCIAL,
    ),
)


def first_step(text: str) -> str | None:
    if not text or not str(text).strip():
        return None
    best: str | None = None
    best_at: int | None = None
    for rx, step in RULES:
        match = rx.search(text)
        if match and (best_at is None or match.start() < best_at):
            best = step
            best_at = match.start()
    return best


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 1:
        sys.stderr.write("usage: incident_first_step.py TEXT\n")
        return 64
    step = first_step(args[0])
    if step is None:
        return 1
    sys.stdout.write(step + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
