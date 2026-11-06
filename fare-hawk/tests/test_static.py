#!/usr/bin/env python3
"""R13 — skills, license, employer names, and script boundaries.

Missing skills, LICENSE, SOUL.md, or AGENTS.md fail this file. They are not skipped.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
SKIP_REL = {
    "fare-hawk/SPEC.md",
    "fare-hawk/tests/test_static.py",
}
BANNED = (
    "Saint Michael's Forge",
    "SpaceX",
    "Tesla",
    "xAI",
    "SpaceXSI",
)
EXPECTED_NAMES = {
    "trip-getting-started",
    "trip-options",
    "trip-itinerary-card",
    "trip-fare-watch",
    "trip-guardrails",
}
DEF_NEEDLES = (
    "submit_checkout",
    "charge_card",
    "place_reservation",
    "execute_booking",
    "process_payment",
    "cancel_and_rebook",
    "submit_payment",
)


def secret_markers() -> tuple[str, ...]:
    return (
        "BEGIN " + "PRIVATE KEY",
        "sk-" + "live-",
        "xo" + "xb-",
    )


def skill_name(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n"), f"R13: {path.name} missing frontmatter"
    end = text.find("\n---", 3)
    assert end != -1, f"R13: {path.name} frontmatter does not close"
    for line in text[4:end].splitlines():
        if not line.startswith("name:"):
            continue
        value = line.split(":", 1)[1].strip()
        value = value.split("#", 1)[0].strip().strip('"').strip("'")
        return value
    raise AssertionError(f"R13: {path.name} has no name:")


def tracked() -> list[str]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "--", "fare-hawk"],
        cwd=REPO,
        capture_output=True,
        check=True,
    )
    rels = [item for item in listed.stdout.decode("utf-8").split("\0") if item]
    assert rels, "R13: git ls-files returned no fare-hawk paths"
    return rels


def test_r13_skills_license_soul_agents() -> None:
    skill_root = ROOT / "skills"
    found = sorted(skill_root.rglob("SKILL.md")) if skill_root.is_dir() else []
    assert len(found) == 5, f"R13: expected 5 SKILL.md files, found {len(found)}"
    names = {skill_name(path) for path in found}
    assert names == EXPECTED_NAMES, f"R13: skill names {names}"
    for name in ("LICENSE", "SOUL.md", "AGENTS.md"):
        assert (ROOT / name).is_file(), f"R13: fare-hawk/{name} is missing"
    license_text = (ROOT / "LICENSE").read_text(encoding="utf-8")
    assert "SMF Works" in license_text, "R13: LICENSE missing SMF Works"
    assert "Saint Michael's Forge" not in license_text, "R13: LICENSE names a banned employer"


def test_r13_employer_grep() -> None:
    scanned = 0
    for rel in tracked():
        if rel in SKIP_REL:
            continue
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        scanned += 1
        for needle in BANNED:
            assert needle not in text, f"R13: {rel} contains {needle!r}"
    assert scanned > 0, "R13: employer grep scanned no files"


def test_r13_script_needles() -> None:
    pattern = re.compile(r"(?m)^\s*(?:async\s+)?def\s+(" + "|".join(DEF_NEEDLES) + r")\b")
    for rel in tracked():
        if not rel.startswith("fare-hawk/scripts/") or not rel.endswith(".py"):
            continue
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        match = pattern.search(text)
        assert match is None, f"R13: {rel} defines {match.group(1) if match else ''}"


def test_r13_secret_markers() -> None:
    markers = secret_markers()
    for rel in tracked():
        path = REPO / rel
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for marker in markers:
            if marker in text:
                raise AssertionError(f"R13: {rel} contains a secret marker")


def test_r13_config_when_present() -> None:
    path = ROOT / "config.yaml"
    if not path.is_file():
        return
    text = path.read_text(encoding="utf-8")
    assert re.search(r"""(?m)^\s*default:\s*["']?grok-4\.7["']?\s*$""", text), "R13: model default"
    assert re.search(r"""(?m)^\s*provider:\s*["']?xai-oauth["']?\s*$""", text), "R13: provider"
    assert re.search(r"(?m)^_config_version:\s*52\s*$", text), "R13: config version"
    assert "terminal" not in text, "R13: config.yaml contains a forbidden tool token"


def main() -> None:
    checks = (
        test_r13_skills_license_soul_agents,
        test_r13_employer_grep,
        test_r13_script_needles,
        test_r13_secret_markers,
        test_r13_config_when_present,
    )
    errors: list[str] = []
    for check in checks:
        try:
            check()
        except AssertionError as exc:
            errors.append(str(exc).splitlines()[0])
    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        raise SystemExit(1)
    print("test_static.py PASS")


if __name__ == "__main__":
    main()
