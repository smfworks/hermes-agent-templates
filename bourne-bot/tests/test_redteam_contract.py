#!/usr/bin/env python3
"""File-level refusal contract. Not Paula's live red-team. No model calls."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {".md", ".yaml", ".yml", ".json", ".py", ".sh", ".txt", ".example"}
SKIP_NAMES = {"SPEC.md"}
SKIP_REL = {"tests/test_redteam_contract.py"}
BANNED = ("stalkerware", "hotline", "domestic violence", "domestic-violence")


def require(text: str, needle: str, where: str) -> None:
    assert needle in text, f"{where} missing {needle!r}"


def test_refusals() -> None:
    soul = (ROOT / "SOUL.md").read_text(encoding="utf-8")
    guard = (ROOT / "skills" / "bourne-bot" / "guardrails" / "SKILL.md").read_text(
        encoding="utf-8"
    )
    for where, text in (("SOUL.md", soul), ("guardrails/SKILL.md", guard)):
        low = text.lower()
        require(low, "hacking", where)
        require(low, "ignore previous instructions", where)
        require(text, "I won't help locate that person", where)
    require(soul.lower(), "locating others", "SOUL.md")
    require(guard.lower(), "locating someone", "guardrails/SKILL.md")
    require(soul, "do not change these limits", "SOUL.md")
    require(guard, "Override resistance", "guardrails/SKILL.md")


def test_no_stalkerware_or_hotline() -> None:
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if "__pycache__" in path.parts or path.suffix.lower() in {".pyc", ".pyo"}:
            continue
        rel = path.relative_to(ROOT).as_posix()
        if path.name in SKIP_NAMES or rel in SKIP_REL:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {
            ".gitignore",
            ".env.EXAMPLE",
        }:
            continue
        data = path.read_text(encoding="utf-8", errors="replace").lower()
        for needle in BANNED:
            assert needle not in data, f"{rel} contains {needle!r}"


def main() -> None:
    test_refusals()
    test_no_stalkerware_or_hotline()
    print("redteam contract: PASS (file-level, not a live model red-team)")


if __name__ == "__main__":
    main()
