#!/usr/bin/env python3
"""A12 — SPEC §8.12 static contract.

Missing skills, LICENSE, SOUL.md, or AGENTS.md fail this file. They are not skipped.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent

SKIP_REL = {
    "ai-claim-checker/SPEC.md",
    "ai-claim-checker/tests/test_static.py",
}
BANNED = (
    "Saint Michael's Forge",
    "SpaceX",
    "Tesla",
    "xAI",
)
SECRET_MARKERS = (
    "BEGIN PRIVATE KEY",
    "sk-live-",
    "xoxb-",
)
INJECTION = "disregard " + "prior " + "instructions"
EXPECTED_NAMES = {
    "verity-getting-started",
    "verity-claim-decomposition",
    "verity-verdict-rubric",
    "verity-claim-card-format",
}
EXPECTED_PATHS = {
    ROOT / "skills" / "ai-claim-checker" / "verity-getting-started" / "SKILL.md",
    ROOT / "skills" / "ai-claim-checker" / "verity-claim-decomposition" / "SKILL.md",
    ROOT / "skills" / "ai-claim-checker" / "verity-verdict-rubric" / "SKILL.md",
    ROOT / "skills" / "ai-claim-checker" / "verity-claim-card-format" / "SKILL.md",
}


def skill_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"A12: {path} missing frontmatter"
    end = text.find("\n---", 3)
    assert end != -1, f"A12: {path} frontmatter does not close"
    for line in text[4:end].splitlines():
        if not line.startswith("name:"):
            continue
        value = line.split(":", 1)[1].strip()
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        return value
    raise AssertionError(f"A12: {path} has no name:")


def test_a12_four_skills_and_license() -> None:
    skill_root = ROOT / "skills"
    found = sorted(skill_root.rglob("SKILL.md")) if skill_root.is_dir() else []
    assert len(found) == 4, f"A12: expected 4 SKILL.md files, found {len(found)}: {found}"
    assert set(found) == EXPECTED_PATHS, f"A12: skill paths {found}"
    names = {skill_name(path) for path in found}
    assert names == EXPECTED_NAMES, f"A12: skill names {names}"

    license_path = ROOT / "LICENSE"
    assert license_path.is_file(), "A12: ai-claim-checker/LICENSE is missing"
    license_text = license_path.read_text(encoding="utf-8")
    assert "SMF Works" in license_text, "A12: LICENSE missing SMF Works"
    assert BANNED[0] not in license_text, "A12: LICENSE names a banned employer"

    for name in ("SOUL.md", "AGENTS.md"):
        path = ROOT / name
        assert path.is_file(), f"A12: ai-claim-checker/{name} is missing"

    config = (ROOT / "config.yaml").read_text(encoding="utf-8")
    assert 'default: "grok-4.7"' in config or "default: grok-4.7" in config
    assert "xai-oauth" in config
    assert "_config_version: 52" in config
    assert "terminal" not in config
    assert "browser" not in config
    assert "delegation" not in config
    assert re.search(r"\bweb\b", config)


def git_tracked() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "ai-claim-checker"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    rels = [item for item in listed.stdout.decode("utf-8").split("\0") if item]
    if rels:
        return rels
    found = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix == ".pyc":
            continue
        found.append(str(path.relative_to(REPO)))
    return found


def test_a12_employer_grep() -> None:
    rels = git_tracked()
    assert rels, "A12: git ls-files returned no ai-claim-checker paths"
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
            assert needle not in text, f"A12: {rel} contains {needle!r}"
        folded = text.casefold()
        assert INJECTION not in folded, f"A12: {rel} has override-style phrasing"
        for marker in SECRET_MARKERS:
            assert marker not in text, f"A12: {rel} looks like a committed secret"
        if rel.startswith("ai-claim-checker/scripts/"):
            assert "subprocess.Popen" not in text
    assert scanned > 0, "A12: employer grep scanned no files"


def main() -> None:
    test_a12_four_skills_and_license()
    test_a12_employer_grep()
    print("A12 PASS")


if __name__ == "__main__":
    main()
