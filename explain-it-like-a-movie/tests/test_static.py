#!/usr/bin/env python3
"""A6 — SPEC §8.6 static contract.

Missing skills or LICENSE fail this file. They are not skipped.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

SKIP_REL = {
    "explain-it-like-a-movie/SPEC.md",
    "explain-it-like-a-movie/tests/test_static.py",
    "explain-it-like-a-movie/tests/test_redteam_contract.py",
}
BANNED = (
    "Saint Michael's Forge",
    "SpaceX",
    "Tesla",
    "xAI",
)
POST_NEEDLES = (
    "smtplib",
    "create_tweet",
    "tweepy",
    "instagrapi",
)
SECRET_MARKERS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "sk-live-",
    "xoxb-",
)
EXPECTED_NAMES = {
    "movie-getting-started",
    "movie-script",
    "movie-produce",
    "movie-guardrails",
}


def skill_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"A6: {path} missing frontmatter"
    end = text.find("\n---", 3)
    assert end != -1, f"A6: {path} frontmatter does not close"
    for line in text[4:end].splitlines():
        if not line.startswith("name:"):
            continue
        value = line.split(":", 1)[1].strip()
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        return value
    raise AssertionError(f"A6: {path} has no name:")


def test_a6_four_skills_and_license() -> None:
    skill_root = ROOT / "skills"
    found = sorted(skill_root.rglob("SKILL.md")) if skill_root.is_dir() else []
    assert len(found) == 4, f"A6: expected 4 SKILL.md files, found {len(found)}: {found}"
    names = {skill_name(path) for path in found}
    assert names == EXPECTED_NAMES, f"A6: skill names {names}"

    license_path = ROOT / "LICENSE"
    assert license_path.is_file(), "A6: explain-it-like-a-movie/LICENSE is missing"
    license_text = license_path.read_text(encoding="utf-8")
    assert "SMF Works" in license_text, "A6: LICENSE missing SMF Works"
    assert "Saint Michael's Forge" not in license_text, "A6: LICENSE names Saint Michael's Forge"

    for name in ("SOUL.md", "AGENTS.md"):
        path = ROOT / name
        assert path.is_file(), f"A6: explain-it-like-a-movie/{name} is missing"
        text = path.read_text(encoding="utf-8")
        assert "ignore previous instructions" not in text.casefold(), f"A6: {name} has injection-scanner phrase"
        assert "disregard prior" not in text.casefold(), f"A6: {name} has override phrasing"


def git_tracked() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "explain-it-like-a-movie"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    return [item for item in listed.stdout.decode("utf-8").split("\0") if item]


def test_a6_employer_grep() -> None:
    rels = git_tracked()
    assert rels, "A6: git ls-files returned no explain-it-like-a-movie paths"
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
            assert needle not in text, f"A6: {rel} contains {needle!r}"
        for needle in POST_NEEDLES:
            assert needle not in text, f"A6: {rel} contains {needle!r}"
        for marker in SECRET_MARKERS:
            assert marker not in text, f"A6: {rel} looks like a committed secret ({marker})"
    assert scanned > 0, "A6: employer grep scanned no files"


def main() -> None:
    test_a6_four_skills_and_license()
    test_a6_employer_grep()
    print("A6 PASS")


if __name__ == "__main__":
    main()
