#!/usr/bin/env python3
"""A6/A7 — feedback weights and monthly first-Monday gate."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import make_env, run_script


def test_feedback_and_monthly() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        topic = "benchmark claims"
        first = run_script(
            "feedback.py",
            ["--data", str(data), "--topic", topic, "--dir", "down", "--now", "2026-11-06T12:00:00Z"],
            env,
        )
        assert first.returncode == 0, first.stderr
        assert "ranked lower" in first.stdout.casefold()
        second = run_script(
            "feedback.py",
            ["--data", str(data), "--topic", topic, "--dir", "down", "--now", "2026-11-06T12:00:00Z"],
            env,
        )
        assert second.returncode == 0, second.stderr
        third = run_script(
            "feedback.py",
            ["--data", str(data), "--topic", topic, "--dir", "down", "--now", "2026-11-06T12:00:00Z"],
            env,
        )
        assert third.returncode == 0, third.stderr
        assert "only if major" in third.stdout.casefold()
        assert "material" in third.stdout.casefold()
        up = run_script(
            "feedback.py",
            ["--data", str(data), "--topic", "local model releases", "--dir", "up", "--now", "2026-11-06T12:00:00Z"],
            env,
        )
        assert "ranked higher" in up.stdout.casefold()
        weights = json.loads((data / "topic-weights.json").read_text(encoding="utf-8"))
        assert weights[topic]["only_if_major"] is True

        quiet = run_script(
            "monthly.py",
            ["--data", str(data), "--now", "2026-11-09T12:00:00Z"],
            env,
        )
        assert quiet.returncode == 0, quiet.stderr
        assert quiet.stdout.strip() == ""
        fire = run_script(
            "monthly.py",
            ["--data", str(data), "--now", "2026-11-02T12:00:00Z"],
            env,
        )
        assert fire.returncode == 0, fire.stderr
        assert "Tune-up" in fire.stdout
    print("A6A7 PASS")


if __name__ == "__main__":
    test_feedback_and_monthly()
