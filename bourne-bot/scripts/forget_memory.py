#!/usr/bin/env python3
"""Remove one named intake field from a USER.md or MEMORY.md file.

"forget my travel info" maps to the travel field. The command prints only the
field name and a line count. It does not print the file.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

EXIT_NO = 2
EXIT_USAGE = 64

# Longest alias wins. Values are the fixed field names this script may print.
ALIASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("travel", ("travel info", "travel")),
    ("family", ("family in scope", "aging parents", "family", "partner", "kids")),
    ("exposure", ("public exposure", "name or face", "exposure")),
    ("business", ("client data", "small business", "business")),
    ("incidents", ("prior incidents", "incidents", "incident")),
    ("tolerance", ("inconvenience tolerance", "inconvenience", "tolerance")),
)

USER_LINE = {
    "exposure": re.compile(r"(?i)^\s*[-*]\s*Public exposure\b"),
    "business": re.compile(r"(?i)^\s*[-*]\s*Small business\b"),
    "family": re.compile(r"(?i)^\s*[-*]\s*Family in scope\b"),
    "travel": re.compile(r"(?i)^\s*[-*]\s*Travel\b"),
    "incidents": re.compile(r"(?i)^\s*[-*]\s*Prior incidents\b"),
    "tolerance": re.compile(r"(?i)^\s*[-*]\s*Inconvenience tolerance\b"),
}

MEMORY_LINE = {
    "exposure": re.compile(
        r"(?i)^\s*[-*]\s*(?:\d{4}-\d{2}-\d{2}\s+)?(?:public\s+)?exposure\b"
    ),
    "business": re.compile(
        r"(?i)^\s*[-*]\s*(?:\d{4}-\d{2}-\d{2}\s+)?(?:small\s+)?business\b"
    ),
    "family": re.compile(r"(?i)^\s*[-*]\s*(?:\d{4}-\d{2}-\d{2}\s+)?family\b"),
    "travel": re.compile(r"(?i)^\s*[-*]\s*(?:\d{4}-\d{2}-\d{2}\s+)?travel\b"),
    "incidents": re.compile(
        r"(?i)^\s*[-*]\s*(?:\d{4}-\d{2}-\d{2}\s+)?(?:prior\s+)?incidents?\b"
    ),
    "tolerance": re.compile(
        r"(?i)^\s*[-*]\s*(?:\d{4}-\d{2}-\d{2}\s+)?(?:inconvenience\s+)?tolerance\b"
    ),
}


def resolve_field(phrase: str) -> str | None:
    text = phrase.strip().lower()
    text = re.sub(r"^(please\s+)?forget(\s+(my|the|our))?\s+", "", text)
    text = text.strip(" .")
    best: str | None = None
    best_len = 0
    for field, names in ALIASES:
        for name in names:
            if name in text and len(name) > best_len:
                best = field
                best_len = len(name)
    return best


def line_matches(field: str, line: str) -> bool:
    stripped = line.lstrip()
    if stripped.startswith("<!--") or stripped.startswith("#"):
        return False
    body = line.rstrip("\r\n")
    return bool(USER_LINE[field].search(body) or MEMORY_LINE[field].search(body))


def forget_text(text: str, field: str) -> tuple[str, int]:
    kept: list[str] = []
    removed = 0
    for line in text.splitlines(keepends=True):
        if line_matches(field, line):
            removed += 1
            continue
        kept.append(line)
    return "".join(kept), removed


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        sys.stderr.write('usage: forget_memory.py FILE "forget my travel info"\n')
        return EXIT_USAGE
    field = resolve_field(args[1])
    if field is None:
        sys.stdout.write("No matching intake field. Nothing removed.\n")
        return EXIT_NO

    path = Path(args[0])
    if not path.is_file():
        sys.stdout.write("Memory file not found. Nothing removed.\n")
        return EXIT_NO
    try:
        original = path.read_text(encoding="utf-8")
    except OSError:
        sys.stdout.write("Memory file could not be read. Nothing removed.\n")
        return EXIT_NO

    updated, removed = forget_text(original, field)
    if updated != original:
        tmp = path.with_name(path.name + ".forget.tmp")
        try:
            mode = path.stat().st_mode & 0o777
            tmp.write_text(updated, encoding="utf-8")
            os.chmod(tmp, mode)
            os.replace(tmp, path)
        except OSError:
            try:
                tmp.unlink()
            except OSError:
                pass
            sys.stdout.write("Memory file could not be updated. Nothing removed.\n")
            return EXIT_NO

    noun = "line" if removed == 1 else "lines"
    sys.stdout.write(f"Forgot {field}. Removed {removed} {noun}.\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
