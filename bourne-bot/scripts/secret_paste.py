#!/usr/bin/env python3
"""Scan stdin and/or files for pasted secrets.

Exit 0 when nothing matches. Exit 2 on a hit, or when a supplied config is
empty or invalid (fail closed). The hit message names a class and a count.
It never includes the secret bytes.

No encryption. This only detects and stops.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

EXIT_HIT = 2
EXIT_USAGE = 64

CLASS_ORDER = (
    "api_key",
    "password",
    "seed_phrase",
    "recovery_code",
    "card_number",
    "account_number",
)

PLACEHOLDERS = {
    "[unset]",
    "unset",
    "none",
    "null",
    "redacted",
    "changeme",
    "password",
    "secret",
    "example",
    "placeholder",
    "your-password",
    "<password>",
    "***",
    "****",
    "n/a",
    "na",
    "todo",
}

API_KEY_RES = (
    re.compile(r"ghp_[A-Za-z0-9]{36}\b"),
    re.compile(r"gho_[A-Za-z0-9]{36}\b"),
    re.compile(r"github_pat_[A-Za-z0-9_]{22,}\b"),
    re.compile(r"sk-[A-Za-z0-9][A-Za-z0-9_\-]{16,}"),
    re.compile(r"sk_live_[A-Za-z0-9]{16,}\b"),
    re.compile(r"rk_live_[A-Za-z0-9]{16,}\b"),
    re.compile(r"AKIA[0-9A-Z]{16}\b"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|secret[_-]?key|access[_-]?token)\s*[:=]\s*['\"]?[A-Za-z0-9_\-]{12,}"
    ),
)

PASSWORD_RES = (
    re.compile(
        r"(?i)['\"]?\b(?:password|passwd|passphrase|pwd)\b['\"]?\s*[:=]\s*(['\"]?)([^\s'\"]+)\1"
    ),
    re.compile(r"(?i)\bmy password is\s+(\S+)"),
)

SEED_LABELED = re.compile(
    r"(?i)\b(?:seed phrase|mnemonic(?: phrase)?|recovery phrase)\b\s*[:=]\s*(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}"
)
SEED_BARE = re.compile(
    r"(?m)^(?:[a-z]{3,8} ){11}[a-z]{3,8}$|^(?:[a-z]{3,8} ){23}[a-z]{3,8}$"
)
RECOVERY = re.compile(
    r"(?i)\b(?:recovery code|backup code|one[- ]time code)\b\s*[:=]\s*[A-Za-z0-9][A-Za-z0-9\-]{5,}"
)
ACCOUNT = re.compile(
    r"(?i)\b(?:account|routing)\s*(?:number|#|no\.?)?\s*[:=]\s*[0-9][0-9 \-]{7,22}"
)
CARD_CANDIDATE = re.compile(r"(?<!\d)(?:\d[ -]?){13,19}(?!\d)")

FAIL_CONFIG = (
    "Stopped. Config is empty or invalid. Refusing to treat input as clean.\n"
)
FAIL_INPUT = (
    "Stopped. Input could not be read. Refusing to treat it as clean.\n"
)


def usage() -> int:
    sys.stderr.write("usage: secret_paste.py [--config FILE] [FILE ...]\n")
    return EXIT_USAGE


def count_matches(rx: re.Pattern, text: str) -> int:
    n = 0
    for match in rx.finditer(text):
        if match.end() == match.start():
            continue
        n += 1
    return n


def luhn_ok(digits: str) -> bool:
    if not digits.isdigit() or not 13 <= len(digits) <= 19:
        return False
    total = 0
    alt = False
    for ch in reversed(digits):
        n = ord(ch) - 48
        if alt:
            n *= 2
            if n > 9:
                n -= 9
        total += n
        alt = not alt
    return total % 10 == 0


def password_hit(text: str) -> int:
    n = 0
    for rx in PASSWORD_RES:
        for match in rx.finditer(text):
            if match.end() == match.start():
                continue
            value = match.group(match.lastindex).strip().strip("'\"")
            if len(value) < 4 or value.lower() in PLACEHOLDERS:
                continue
            n += 1
    return n


def overlaps(span: tuple[int, int], spans: list[tuple[int, int]]) -> bool:
    start, end = span
    for other_start, other_end in spans:
        if start < other_end and other_start < end:
            return True
    return False


def scan(text: str, extra: list[tuple[str, re.Pattern]] | None = None) -> dict[str, int]:
    counts = {name: 0 for name in CLASS_ORDER}
    for rx in API_KEY_RES:
        counts["api_key"] += count_matches(rx, text)
    counts["password"] += password_hit(text)
    counts["seed_phrase"] += count_matches(SEED_LABELED, text)
    if counts["seed_phrase"] == 0:
        counts["seed_phrase"] += count_matches(SEED_BARE, text)
    counts["recovery_code"] += count_matches(RECOVERY, text)

    card_spans: list[tuple[int, int]] = []
    for match in CARD_CANDIDATE.finditer(text):
        digits = re.sub(r"\D", "", match.group(0))
        if luhn_ok(digits):
            counts["card_number"] += 1
            card_spans.append(match.span())

    for match in ACCOUNT.finditer(text):
        if overlaps(match.span(), card_spans):
            continue
        digits = re.sub(r"\D", "", match.group(0))
        if len(digits) < 8:
            continue
        if luhn_ok(digits):
            counts["card_number"] += 1
        else:
            counts["account_number"] += 1

    for cls, rx in extra or []:
        if cls not in counts:
            continue
        counts[cls] += count_matches(rx, text)
    return {name: n for name, n in counts.items() if n}


def render(counts: dict[str, int]) -> str:
    parts = [f"{name}={counts[name]}" for name in CLASS_ORDER if counts.get(name)]
    listed = ", ".join(parts)
    return (
        "Stopped. Do not store this. Rotate it if it is live, and stop pasting it.\n"
        f"Classes: {listed}\n"
    )


def load_config(path: str) -> list[tuple[str, re.Pattern]] | None:
    """Extra patterns, or None when the config must fail closed.

    ``{"patterns": []}`` is valid: built-in rules still run. An empty file,
    invalid JSON, or a document with no patterns list is not.
    """
    try:
        raw = Path(path).read_bytes()
    except OSError:
        return None
    if not raw.strip():
        return None
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict) or not isinstance(data.get("patterns"), list):
        return None
    extra: list[tuple[str, re.Pattern]] = []
    for item in data["patterns"]:
        if not isinstance(item, dict):
            return None
        cls = item.get("class")
        pat = item.get("pattern")
        if cls not in CLASS_ORDER or not isinstance(pat, str) or not pat.strip():
            return None
        try:
            extra.append((cls, re.compile(pat)))
        except re.error:
            return None
    return extra


def read_stdin() -> str:
    return sys.stdin.buffer.read().decode("utf-8", errors="replace")


def read_inputs(paths: list[str]) -> str | None:
    if not paths:
        return read_stdin()
    chunks: list[str] = []
    for item in paths:
        if item == "-":
            chunks.append(read_stdin())
            continue
        try:
            chunks.append(Path(item).read_bytes().decode("utf-8", errors="replace"))
        except OSError:
            return None
    return "\n".join(chunks)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    config_path: str | None = None
    files: list[str] = []
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--config":
            if i + 1 >= len(args):
                return usage()
            config_path = args[i + 1]
            i += 2
            continue
        if arg == "--":
            files.extend(args[i + 1 :])
            break
        if arg.startswith("-") and arg != "-":
            return usage()
        files.append(arg)
        i += 1

    extra: list[tuple[str, re.Pattern]] | None = []
    if config_path is not None:
        extra = load_config(config_path)
        if extra is None:
            sys.stdout.write(FAIL_CONFIG)
            return EXIT_HIT

    text = read_inputs(files)
    if text is None:
        sys.stdout.write(FAIL_INPUT)
        return EXIT_HIT

    counts = scan(text, extra)
    if not counts:
        return 0
    sys.stdout.write(render(counts))
    return EXIT_HIT


if __name__ == "__main__":
    sys.exit(main())
