#!/usr/bin/env python3
"""A2 — SPEC §8.2 metrics match expected_metrics.json exactly."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import FIXTURES, NOW, TZ, make_env, run_script


def canon(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        number = float(value)
        if number.is_integer():
            return int(number)
        return number
    if isinstance(value, dict):
        return {key: canon(item) for key, item in value.items()}
    if isinstance(value, list):
        return [canon(item) for item in value]
    return value


def assert_metrics(actual: dict, expected: dict) -> None:
    assert set(actual) == set(expected), (sorted(set(actual) ^ set(expected)))
    for key in expected:
        assert canon(actual[key]) == canon(expected[key]), (key, actual[key], expected[key])


def test_a2() -> None:
    feed = json.loads((FIXTURES / "feed.json").read_text(encoding="utf-8"))
    expected = json.loads((FIXTURES / "expected_metrics.json").read_text(encoding="utf-8"))
    assert expected["best_post_id"] == "best1"
    assert expected["worst_habit"] == "link_only"
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        env = make_env(tmp)
        posts_path = tmp / "posts.json"
        posts_path.write_text(json.dumps(feed["posts"]), encoding="utf-8")
        out_path = tmp / "metrics.json"
        proc = run_script(
            "roast_metrics.py",
            [
                "--posts",
                str(posts_path),
                "--out",
                str(out_path),
                "--now",
                NOW,
                "--tz",
                TZ,
            ],
            env,
        )
        assert proc.returncode == 0, proc.stderr
        actual = json.loads(out_path.read_text(encoding="utf-8"))
        assert actual["best_post_id"] == "best1"
        assert actual["worst_habit"] == "link_only"
        assert_metrics(actual, expected)

        wide_path = tmp / "wide.json"
        wide = run_script(
            "roast_metrics.py",
            [
                "--posts",
                str(posts_path),
                "--out",
                str(wide_path),
                "--now",
                NOW,
                "--tz",
                TZ,
                "--window-start",
                "2026-10-01T00:00:00Z",
            ],
            env,
        )
        assert wide.returncode == 0, wide.stderr
        widened = json.loads(wide_path.read_text(encoding="utf-8"))
        assert widened["posts_in_window"] == 46
        assert widened["best_post_id"] == "best1"
        assert widened["max_likes"] == 100
        assert widened["link_only"] == 5
        assert widened["emoji_only"] == 4
        assert "2026-10-01" in widened["posts_per_day"]
        assert "2026-11-06" not in widened["posts_per_day"]
    print("A2 PASS")


def main() -> None:
    test_a2()


if __name__ == "__main__":
    main()
