#!/usr/bin/env python3
"""forget_memory removes the named field and does not print the file."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "forget_memory.py"
SECRET = "ghp_" + ("c" * 36)
TRAVEL_VALUE = "TRAVELVALUE99-quarterly-international"


def run(path: Path, phrase: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(path), phrase],
        text=True,
        capture_output=True,
        check=False,
    )


def test_user_travel() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "USER.md"
        path.write_text(
            "\n".join(
                [
                    "# USER.md — owner context",
                    "",
                    "## Intake",
                    "",
                    "- Public exposure (name or face in public): media",
                    "- Small business or client data: [unset]",
                    "- Family in scope (partner, kids, aging parents): partner",
                    f"- Travel, including international: {TRAVEL_VALUE}",
                    "- Prior incidents (hacked account, leak, harassment, scam, doxx attempt): none",
                    "- Inconvenience tolerance (low, medium, or high): low",
                    "",
                    "## Notes",
                    "",
                    f"- kept note {SECRET}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        mode = path.stat().st_mode & 0o777
        result = run(path, "forget my travel info")
        assert result.returncode == 0, result.stderr
        assert SECRET not in result.stdout
        assert SECRET not in result.stderr
        assert TRAVEL_VALUE not in result.stdout
        assert TRAVEL_VALUE not in result.stderr
        assert "Forgot travel." in result.stdout
        text = path.read_text(encoding="utf-8")
        assert TRAVEL_VALUE not in text
        assert "Travel, including international" not in text
        assert SECRET in text
        assert "Family in scope" in text
        assert "Public exposure" in text
        assert (path.stat().st_mode & 0o777) == mode


def test_memory_travel_keeps_comment_and_secret() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "MEMORY.md"
        path.write_text(
            "\n".join(
                [
                    "# MEMORY.md — durable facts",
                    "",
                    "<!-- Non-secret posture only: exposure level, business, family in scope, travel, prior incidents, tolerance, completed actions. -->",
                    "",
                    "## Entries",
                    "",
                    f"- 2026-11-03 travel: {TRAVEL_VALUE}",
                    "- 2026-11-03 tolerance: low",
                    f"- 2026-11-01 note: {SECRET}",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        result = run(path, "forget my travel info")
        assert result.returncode == 0, result.stderr
        assert SECRET not in result.stdout + result.stderr
        assert TRAVEL_VALUE not in result.stdout + result.stderr
        text = path.read_text(encoding="utf-8")
        assert TRAVEL_VALUE not in text
        assert "travel, prior incidents" in text
        assert SECRET in text
        assert "tolerance: low" in text


def test_phrase_with_secret_is_not_echoed() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "USER.md"
        path.write_text("- Travel, including international: home\n", encoding="utf-8")
        phrase = f"forget my {SECRET} travel info"
        result = run(path, phrase)
        assert result.returncode == 0
        assert SECRET not in result.stdout
        assert SECRET not in result.stderr
        assert "Travel, including international" not in path.read_text(encoding="utf-8")

        other = Path(tmp) / "OTHER.md"
        other.write_text(f"keep {SECRET}\n", encoding="utf-8")
        result = run(other, SECRET)
        assert result.returncode == 2
        assert SECRET not in result.stdout
        assert SECRET not in result.stderr
        assert SECRET in other.read_text(encoding="utf-8")


def main() -> None:
    test_user_travel()
    test_memory_travel_keeps_comment_and_secret()
    test_phrase_with_secret_is_not_echoed()
    print("forget_memory: PASS")


if __name__ == "__main__":
    main()
