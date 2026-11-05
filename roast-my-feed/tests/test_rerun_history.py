#!/usr/bin/env python3
"""A4 — SPEC §8.4 re-run overwrites the same paths and compares history."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from helpers import (
    DAY_HEADINGS,
    DRAFT_HEADINGS,
    FIXTURES,
    FOOTER,
    NO_EARLIER,
    NOW,
    REPORT_HEADINGS,
    WINDOW_7,
    make_env,
    prior_habit_sentence,
    read_history,
    run_audit,
    status_url,
)


def test_a4() -> None:
    expected = json.loads((FIXTURES / "expected_metrics.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        fixture = FIXTURES / "feed.json"
        first = run_audit(data, "fixtureuser", fixture, env)
        assert first.returncode == 0, first.stderr
        roast = data / "roast" / "fixtureuser"
        md_path = roast / "roast.md"
        html_path = roast / "roast.html"
        assert md_path.is_file() and html_path.is_file()
        first_md = md_path.read_text(encoding="utf-8")
        first_html = html_path.read_text(encoding="utf-8")
        assert NO_EARLIER in first_md
        assert "Last run worst habit" not in first_md
        assert_report(first_md, first_html)
        history = read_history(data)
        assert len(history) == 1
        assert_history_line(history[0], expected)
        assert history[0]["window_start"] == WINDOW_7

        md_path.write_text(first_md + "\nFIRST_RUN_MARKER\n", encoding="utf-8")
        html_path.write_text(first_html + "\nFIRST_RUN_MARKER\n", encoding="utf-8")
        second = run_audit(data, "fixtureuser", fixture, env)
        assert second.returncode == 0, second.stderr
        assert md_path.is_file() and html_path.is_file()
        second_md = md_path.read_text(encoding="utf-8")
        second_html = html_path.read_text(encoding="utf-8")
        assert "FIRST_RUN_MARKER" not in second_md
        assert "FIRST_RUN_MARKER" not in second_html
        assert not list(roast.glob("roast-*.md"))
        assert not list(roast.glob("roast-*.html"))
        names = {path.name for path in roast.iterdir()}
        assert "roast.md" in names and "roast.html" in names
        sentence = prior_habit_sentence(history[0]["worst_habit"], history[0]["worst_habit_count"])
        assert sentence in second_md, sentence
        assert NO_EARLIER not in second_md
        assert_report(second_md, second_html)
        later = read_history(data)
        assert len(later) == 2
        assert later[0] == history[0]
        assert_history_line(later[1], expected)
        assert later[1]["handle"] == "fixtureuser"
    print("A4 PASS")


def assert_report(md: str, html: str) -> None:
    cursor = 0
    for heading in REPORT_HEADINGS:
        found = md.find(heading, cursor)
        assert found != -1, heading
        cursor = found + len(heading)
    for heading in DAY_HEADINGS + DRAFT_HEADINGS:
        assert heading in md, heading
    assert FOOTER in md and FOOTER in html
    assert "7 hooks in the first line" in md
    link = status_url("fixtureuser", "best1")
    assert link in md and link in html
    assert WINDOW_7 in md and NOW in md


def assert_history_line(line: dict, expected: dict) -> None:
    assert line["handle"] == "fixtureuser"
    assert line["at"] == NOW
    assert line["window_end"] == NOW
    assert line["posts_in_window"] == expected["posts_in_window"]
    assert line["worst_habit"] == expected["worst_habit"]
    assert line["worst_habit_count"] == expected["worst_habit_count"]
    assert line["best_post_id"] == expected["best_post_id"]
    assert isinstance(line["posts_in_window"], int)
    assert isinstance(line["worst_habit_count"], int)


def main() -> None:
    test_a4()


if __name__ == "__main__":
    main()
