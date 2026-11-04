#!/usr/bin/env python3
"""Shared helpers for Receipts contract tests. No model calls."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
NOW = "2026-11-04"


def make_env(tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_script(script: str, args: list[str], env: dict[str, str], cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    path = ROOT / "scripts" / script
    assert path.is_file(), f"missing {path}"
    return subprocess.run(
        [sys.executable, str(path), *args],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(cwd or ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
