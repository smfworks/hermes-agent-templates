#!/usr/bin/env python3
"""Shared helpers for Roast My Feed contract tests. No model calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
NOW = "2026-11-05T12:00:00Z"
TZ = "America/New_York"
WINDOW_7 = "2026-10-29T12:00:00Z"
WINDOW_30 = "2026-10-06T12:00:00Z"
FOOTER = "Try Hermes: Roast My Feed by SMF Works"
INTRO = (
    "I'm Roast My Feed. Give me an X handle and in about 2 minutes you get a "
    "Wrapped-style audit: your archetype, best post, worst habit, a 7-day plan, "
    "and 3 posts drafted in your voice. Witty, never cruel, and every number is "
    "real. No X login needed. What's the handle?"
)
PROTECTED = "I can't read that account."
NO_EARLIER = "No earlier roast for this handle."
REPORT_HEADINGS = (
    "## Window",
    "## Archetype",
    "## Stats",
    "## Best post",
    "## Worst habit",
    "## 7-day plan",
    "## Drafts",
)
DAY_HEADINGS = tuple(f"### Day {number}" for number in range(1, 8))
DRAFT_HEADINGS = tuple(f"### Draft {number}" for number in range(1, 4))


def make_env(tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env.pop("X_BEARER_TOKEN", None)
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


def run_audit(
    data: Path,
    handle: str,
    fixture: Path,
    env: dict[str, str],
    extra: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    args = [
        "--data",
        str(data),
        "--handle",
        handle,
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
    return run_script("audit.py", args, env)


def read_state(data: Path) -> dict:
    return json.loads((data / "state.json").read_text(encoding="utf-8"))


def read_history(data: Path) -> list[dict]:
    path = data / "history.jsonl"
    assert path.is_file(), "missing history.jsonl"
    lines = [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [json.loads(line) for line in lines]


def prior_habit_sentence(habit: str, count: int) -> str:
    return f"Last run worst habit {habit} count was {count}."


def status_url(handle: str, post_id: str) -> str:
    return f"https://x.com/{handle}/status/{post_id}"


def assert_no_live_hermes(tmp: Path) -> None:
    assert not (tmp / "home" / ".hermes").exists()
