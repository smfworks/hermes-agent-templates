#!/usr/bin/env python3
"""A12 — four skills, LICENSE, SOUL, AGENTS, employer grep, config."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SKIP_REL = {
    "ai-daily-radar/SPEC.md",
    "ai-daily-radar/tests/test_static.py",
}
BANNED = (
    "Saint Michael's Forge",
    "SpaceX",
    "Tesla",
    "xAI",
)
INJECTION = "disregard " + "prior " + "instructions"
EXPECTED_NAMES = {
    "radar-getting-started",
    "radar-evidence-tagging",
    "radar-ai-news-dedup",
    "radar-brief-formatting",
}


def secret_markers() -> tuple[str, ...]:
    return (
        "BEGIN " + "PRIVATE KEY",
        "sk-" + "live-",
        "xo" + "xb-",
    )


def skill_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), path
    end = text.find("\n---", 3)
    for line in text[4:end].splitlines():
        if line.startswith("name:"):
            return line.split(":", 1)[1].strip().strip('"').strip("'")
    raise AssertionError(path)


def test_static() -> None:
    found = sorted((ROOT / "skills").rglob("SKILL.md"))
    assert len(found) == 4, found
    names = {skill_name(path) for path in found}
    assert names == EXPECTED_NAMES, names
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "SMF Works" in license_text
    for name in ("SOUL.md", "AGENTS.md"):
        assert (ROOT / name).is_file(), name
    config = (ROOT / "config.yaml").read_text(encoding="utf-8")
    assert 'default: "grok-4.7"' in config
    assert "xai-oauth" in config
    assert "_config_version: 52" in config
    assert "terminal" not in config
    assert re.search(r"\bweb\b", config)

    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "ai-daily-radar"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    rels = [item for item in listed.stdout.decode().split("\0") if item]
    if not rels:
        rels = [
            str(path.relative_to(REPO))
            for path in ROOT.rglob("*")
            if path.is_file() and "__pycache__" not in path.parts and path.suffix != ".pyc"
        ]
    scanned = 0
    for rel in rels:
        if rel in SKIP_REL:
            continue
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        scanned += 1
        for needle in BANNED:
            assert needle not in text, f"{rel} contains {needle!r}"
        assert INJECTION not in text.casefold(), rel
        for marker in secret_markers():
            assert marker not in text, rel
    assert scanned > 0
    print("A12 PASS")


if __name__ == "__main__":
    test_static()
