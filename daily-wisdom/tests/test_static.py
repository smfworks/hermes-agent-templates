#!/usr/bin/env python3
"""A7 — SPEC §10.7 static contract.

Missing skills or LICENSE fail this file. They are not skipped.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

# Needles live in this file. The scan skips it, and skips SPEC.md per §10.7.
SKIP_REL = {
    "daily-wisdom/SPEC.md",
    "daily-wisdom/tests/test_static.py",
}
BANNED = (
    "Saint Michael's Forge",
    "SpaceX",
    "Tesla",
    "xAI",
)
EXPECTED_NAMES = {
    "wisdom-getting-started",
    "wisdom-daily-sitting",
    "wisdom-weekly-page",
    "wisdom-guardrails",
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


def test_a7_four_skills_and_license() -> None:
    skill_root = ROOT / "skills"
    found = sorted(skill_root.rglob("SKILL.md")) if skill_root.is_dir() else []
    assert len(found) == 4, f"A7: expected 4 SKILL.md files, found {len(found)}: {found}"
    names = {skill_name(path) for path in found}
    assert names == EXPECTED_NAMES, f"A7: skill names {names}"

    license_path = ROOT / "LICENSE"
    assert license_path.is_file(), "A7: daily-wisdom/LICENSE is missing"
    license_text = license_path.read_text(encoding="utf-8")
    assert "SMF Works" in license_text, "A7: LICENSE missing SMF Works"
    assert "Saint Michael's Forge" not in license_text, "A7: LICENSE names Saint Michael's Forge"


def test_a7_employer_grep() -> None:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "daily-wisdom"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    rels = [item for item in listed.stdout.decode("utf-8").split("\0") if item]
    assert rels, "A7: git ls-files returned no daily-wisdom paths"
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
    assert scanned > 0, "A7: employer grep scanned no files"


def main() -> None:
    test_a7_four_skills_and_license()
    test_a7_employer_grep()
    print("A7 PASS")


if __name__ == "__main__":
    main()
