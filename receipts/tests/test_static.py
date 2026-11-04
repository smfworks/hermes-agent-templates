#!/usr/bin/env python3
"""A8 — SPEC §10.8 static contract.

Missing skills or LICENSE fail this file. They are not skipped.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

SKIP_REL = {
    "receipts/SPEC.md",
    "receipts/tests/test_static.py",
}
BANNED = (
    "Saint Michael's Forge",
    "SpaceX",
    "Tesla",
    "xAI",
)
SEND_NEEDLES = (
    "smtplib",
    "gmail.send",
    "gmail.modify",
    "EXPUNGE",
)
# IMAP write command as a whole word, not the English verb "store".
STORE_NEEDLE = "STORE"
EXPECTED_NAMES = {
    "money-back-getting-started",
    "money-back-scan",
    "money-back-page",
    "money-back-guardrails",
}
SECRET_MARKERS = (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "sk-live-",
    "xoxb-",
)


def skill_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"A8: {path} missing frontmatter"
    end = text.find("\n---", 3)
    assert end != -1, f"A8: {path} frontmatter does not close"
    for line in text[4:end].splitlines():
        if not line.startswith("name:"):
            continue
        value = line.split(":", 1)[1].strip()
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        return value
    raise AssertionError(f"A8: {path} has no name:")


def test_a8_four_skills_and_license() -> None:
    skill_root = ROOT / "skills"
    found = sorted(skill_root.rglob("SKILL.md")) if skill_root.is_dir() else []
    assert len(found) == 4, f"A8: expected 4 SKILL.md files, found {len(found)}: {found}"
    names = {skill_name(path) for path in found}
    assert names == EXPECTED_NAMES, f"A8: skill names {names}"

    license_path = ROOT / "LICENSE"
    assert license_path.is_file(), "A8: receipts/LICENSE is missing"
    license_text = license_path.read_text(encoding="utf-8")
    assert "SMF Works" in license_text, "A8: LICENSE missing SMF Works"
    assert "Saint Michael's Forge" not in license_text, "A8: LICENSE names Saint Michael's Forge"

    for name in ("SOUL.md", "AGENTS.md"):
        path = ROOT / name
        assert path.is_file(), f"A8: receipts/{name} is missing"
        text = path.read_text(encoding="utf-8")
        assert "ignore previous instructions" not in text.casefold(), f"A8: {name} has injection-scanner phrase"


def git_tracked() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "receipts"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    return [item for item in listed.stdout.decode("utf-8").split("\0") if item]


def test_a8_employer_grep() -> None:
    rels = git_tracked()
    assert rels, "A8: git ls-files returned no receipts paths"
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
            assert needle not in text, f"A8: {rel} contains {needle!r}"
        for needle in SEND_NEEDLES:
            assert needle not in text, f"A8: {rel} contains {needle!r}"
        if STORE_NEEDLE in text and "IMAP" in text:
            raise AssertionError(f"A8: {rel} contains IMAP STORE")
        for marker in SECRET_MARKERS:
            assert marker not in text, f"A8: {rel} looks like a committed secret ({marker})"
    assert scanned > 0, "A8: employer grep scanned no files"


def main() -> None:
    test_a8_four_skills_and_license()
    test_a8_employer_grep()
    print("A8 PASS")


if __name__ == "__main__":
    main()
