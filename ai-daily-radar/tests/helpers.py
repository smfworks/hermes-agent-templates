#!/usr/bin/env python3
"""Shared helpers for AI Daily Radar contract tests."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
NOW = "2026-11-06T12:00:00Z"  # Friday
TZ = "America/New_York"
FOOTER = "Try Hermes: AI Daily Radar by SMF Works."
INTRO = (
    "I'm Radar. Each morning I send up to 7 AI changes that matter to your stack, "
    "each tagged by how solid the evidence is, with links. I never post, email others, "
    "or buy anything."
)


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


def run_script(script: str, args: list[str], env: dict[str, str], cwd: Path | None = None):
    path = ROOT / "scripts" / script
    assert path.is_file(), path
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


def primary(path: str = "a") -> dict:
    return {"url": f"https://example.com/{path}", "title": "Vendor blog", "retrieved_at": NOW}


def candidate(cid: str, **extra) -> dict:
    row = {
        "id": cid,
        "headline": extra.pop("headline", f"Change {cid} is out"),
        "what_changed": extra.pop("what_changed", "A product changed."),
        "why": extra.pop("why", "It touches your coding stack."),
        "primary": extra.pop("primary", primary(cid)),
        "usable_now": extra.pop("usable_now", True),
        "vendor": extra.pop("vendor", "Acme"),
        "product": extra.pop("product", cid),
        "event_type": extra.pop("event_type", "launch"),
        "topics": extra.pop("topics", ["vendor developer-portal news"]),
        "stack_match": extra.pop("stack_match", ["coding"]),
    }
    row.update(extra)
    return row


def write_fixture(path: Path, candidates: list[dict], **extra) -> Path:
    payload = {"candidates": candidates, "try_this": "Open the top primary link. That's 10 minutes."}
    payload.update(extra)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path
