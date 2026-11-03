#!/usr/bin/env python3
"""SPEC §8 items 2 and 3: incident phrases map to the SOUL first step."""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "incident_first_step.py"

spec = importlib.util.spec_from_file_location("incident_first_step", SCRIPT)
mod = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)


def test_phrases() -> None:
    # §8 item 2
    assert mod.first_step("My email was just hacked") == mod.EMAIL
    # §8 item 3
    assert mod.first_step("I lost my phone") == mod.DEVICE
    assert mod.first_step("lost phone") == mod.DEVICE
    assert mod.first_step("This is a credential leak") == mod.CREDENTIAL
    assert mod.first_step("doxx attempt") == mod.DOXX
    assert mod.first_step("financial exposure") == mod.FINANCIAL

    # SOUL parentheticals
    assert mod.first_step("hacked account") == mod.EMAIL
    assert mod.first_step("suspected account compromise") == mod.EMAIL
    assert mod.first_step("lost or stolen device") == mod.DEVICE

    assert mod.first_step("How often do you travel?") is None
    assert mod.first_step("") is None


def test_steps_are_the_soul_lines() -> None:
    soul = (ROOT / "SOUL.md").read_text(encoding="utf-8").lower()
    for step in (mod.EMAIL, mod.DEVICE, mod.CREDENTIAL, mod.DOXX, mod.FINANCIAL):
        needle = step.rstrip(".").lower()
        assert needle in soul, needle


def test_cli() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "My email was just hacked"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0
    assert result.stdout.strip() == mod.EMAIL
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "How often do you travel?"],
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 1
    assert result.stdout == ""


def main() -> None:
    test_phrases()
    test_steps_are_the_soul_lines()
    test_cli()
    print("incident_first_step: PASS")


if __name__ == "__main__":
    main()
