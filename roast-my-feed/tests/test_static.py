#!/usr/bin/env python3
"""A7 — SPEC §8.7 static contract.

Missing skills, LICENSE, SOUL.md, or AGENTS.md fail this file. They are not skipped.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

SKIP_REL = {
    "roast-my-feed/SPEC.md",
    "roast-my-feed/tests/test_static.py",
}
BANNED = (
    "Saint Michael's Forge",
    "SpaceX",
    "Tesla",
    "xAI",
)
WRITE_NEEDLES = (
    "create_tweet",
    "statuses/update",
    "tweepy.Client.create",
)
SECRET_MARKERS = (
    "BEGIN PRIVATE KEY",
    "sk-live-",
    "xoxb-",
)
INJECTION = "disregard " + "prior " + "instructions"
EXPECTED_NAMES = {
    "roast-getting-started",
    "roast-audit",
    "roast-guardrails",
}
EXPECTED_PATHS = {
    ROOT / "skills" / "roast-my-feed" / "roast-getting-started" / "SKILL.md",
    ROOT / "skills" / "roast-my-feed" / "roast-audit" / "SKILL.md",
    ROOT / "skills" / "roast-my-feed" / "roast-guardrails" / "SKILL.md",
}


def skill_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"A7: {path} missing frontmatter"
    end = text.find("\n---", 3)
    assert end != -1, f"A7: {path} frontmatter does not close"
    for line in text[4:end].splitlines():
        if not line.startswith("name:"):
            continue
        value = line.split(":", 1)[1].strip()
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        return value
    raise AssertionError(f"A7: {path} has no name:")


def test_a7_three_skills_and_license() -> None:
    skill_root = ROOT / "skills"
    found = sorted(skill_root.rglob("SKILL.md")) if skill_root.is_dir() else []
    assert len(found) == 3, f"A7: expected 3 SKILL.md files, found {len(found)}: {found}"
    assert set(found) == EXPECTED_PATHS, f"A7: skill paths {found}"
    names = {skill_name(path) for path in found}
    assert names == EXPECTED_NAMES, f"A7: skill names {names}"

    license_path = ROOT / "LICENSE"
    assert license_path.is_file(), "A7: roast-my-feed/LICENSE is missing"
    license_text = license_path.read_text(encoding="utf-8")
    assert "SMF Works" in license_text, "A7: LICENSE missing SMF Works"
    assert BANNED[0] not in license_text, "A7: LICENSE names a banned employer"

    for name in ("SOUL.md", "AGENTS.md"):
        path = ROOT / name
        assert path.is_file(), f"A7: roast-my-feed/{name} is missing"


def git_tracked() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "roast-my-feed"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    return [item for item in listed.stdout.decode("utf-8").split("\0") if item]


def test_a7_employer_grep() -> None:
    rels = git_tracked()
    assert rels, "A7: git ls-files returned no roast-my-feed paths"
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
            assert needle not in text, f"A7: {rel} contains {needle!r}"
        folded = text.casefold()
        assert INJECTION not in folded, f"A7: {rel} has override-style phrasing"
        for marker in SECRET_MARKERS:
            assert marker not in text, f"A7: {rel} looks like a committed secret"
        if rel.startswith("roast-my-feed/scripts/"):
            for needle in WRITE_NEEDLES:
                assert needle not in text, f"A7: {rel} contains {needle!r}"
    assert scanned > 0, "A7: employer grep scanned no files"

    x_read = ROOT / "scripts" / "x_read.py"
    if x_read.is_file():
        source = x_read.read_text(encoding="utf-8", errors="replace")
        assert re.search(r"\bPOST\b", source) is None, "A7: scripts/x_read.py contains the HTTP method POST"


def main() -> None:
    test_a7_three_skills_and_license()
    test_a7_employer_grep()
    print("A7 PASS")


if __name__ == "__main__":
    main()
