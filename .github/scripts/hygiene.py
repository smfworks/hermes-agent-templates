#!/usr/bin/env python3
"""Repo hygiene for a public template checkout.

Validates JSON and YAML, requires name/description frontmatter on every
SKILL.md, and rejects build-machine paths, local usernames, and obvious
secret tokens. Patterns are assembled so this file does not contain the
strings it searches for.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    print("hygiene: install PyYAML", file=sys.stderr)
    sys.exit(1)

ROOT = Path(subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True).strip())

NEEDLES = (
    ("/" + "home" + "/", "home-directory path"),
    ("/" + "Users" + "/", "home-directory path"),
    ("mike" + "sai1", "local username"),
    ("omar" + "chy", "build-machine hostname"),
    ("mise/" + "installs", "machine-specific tool path"),
    (".local/share/" + "mise", "machine-specific tool path"),
)

SECRET = re.compile(
    "|".join(
        (
            r"ghp_[A-Za-z0-9]{20,}",
            r"github_pat_[A-Za-z0-9_]{20,}",
            r"xox[baprs]-[A-Za-z0-9-]{10,}",
            r"AKIA[0-9A-Z]{16}",
        )
    )
)

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pyc", ".woff", ".woff2"}


def tracked_files() -> list[Path]:
    raw = subprocess.check_output(
        ["git", "ls-files", "-z", "-c", "-o", "--exclude-standard"], cwd=ROOT
    )
    names = [name for name in raw.decode().split("\0") if name]
    return [ROOT / name for name in names]


def skill_frontmatter_errors(rel: str, text: str) -> list[str]:
    if not text.startswith("---\n"):
        return [f"{rel}: SKILL.md is missing a YAML frontmatter block"]
    end = text.find("\n---", 4)
    if end < 0:
        return [f"{rel}: SKILL.md frontmatter is not closed"]
    block = text[4:end]
    errors = []
    for key in ("name:", "description:"):
        if not any(line.startswith(key) for line in block.splitlines()):
            errors.append(f"{rel}: SKILL.md frontmatter is missing {key[:-1]}")
    return errors


def main() -> int:
    errors: list[str] = []
    for path in tracked_files():
        if not path.is_file() or path.suffix.lower() in SKIP_SUFFIXES:
            continue
        data = path.read_bytes()
        if b"\0" in data[:4096]:
            continue
        text = data.decode("utf-8", errors="replace")
        rel = str(path.relative_to(ROOT))
        for needle, why in NEEDLES:
            if needle in text:
                errors.append(f"{rel}: contains a {why}")
        if SECRET.search(text):
            errors.append(f"{rel}: contains a secret-shaped token")
        if path.suffix == ".json":
            try:
                json.loads(text)
            except json.JSONDecodeError as exc:
                errors.append(f"{rel}: invalid JSON ({exc})")
        if path.suffix in {".yaml", ".yml"}:
            try:
                yaml.safe_load(text)
            except yaml.YAMLError as exc:
                errors.append(f"{rel}: invalid YAML ({exc})")
        if path.name == "SKILL.md":
            errors.extend(skill_frontmatter_errors(rel, text))
    if errors:
        print("hygiene: FAIL")
        for line in errors:
            print(line)
        return 1
    print(f"hygiene: PASS ({len(tracked_files())} tracked files)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
