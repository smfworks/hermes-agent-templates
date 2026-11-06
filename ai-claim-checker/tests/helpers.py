#!/usr/bin/env python3
"""Shared helpers for AI Claim Checker contract tests. No model calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
FIXTURES = Path(__file__).resolve().parent / "fixtures"
NOW = "2026-11-06T12:00:00Z"
TZ = "America/New_York"
FOOTER = "Try Hermes: AI Claim Checker by SMF Works."
INTRO = (
    "Hi, I'm Verity, your AI Claim Checker. Paste any AI launch post, "
    "benchmark chart, or price claim and I'll give you a dated claim card: "
    "supported, vendor-only, contradicted, or unverifiable, with sources."
)
PLANT = "tok_PLANT99"
VERDICTS = {"supported", "vendor-only", "contradicted", "unverifiable"}


def make_env(tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.pop("SEARCH_API_KEY", None)
    env.pop("XAI_API_KEY", None)
    return env


def run_script(
    script: str,
    args: list[str],
    env: dict[str, str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
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


def run_check(
    data: Path,
    slug: str,
    fixture: Path,
    env: dict[str, str],
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        "--data",
        str(data),
        "--slug",
        slug,
        "--backend",
        "fixtures",
        "--fixtures",
        str(fixture),
        "--now",
        NOW,
        "--tz",
        TZ,
    ]
    if extra:
        args.extend(extra)
    return run_script("check.py", args, env)


def read_state(data: Path) -> dict:
    return json.loads((data / "state.json").read_text(encoding="utf-8"))


def read_claims(data: Path, slug: str) -> list:
    path = data / "claims" / slug / "claims.json"
    return json.loads(path.read_text(encoding="utf-8"))


def assert_no_live_hermes(tmp: Path) -> None:
    assert not (tmp / "home" / ".hermes").exists()
