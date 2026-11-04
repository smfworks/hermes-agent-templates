#!/usr/bin/env python3
"""A5 — SPEC §10.5 weekly page with notes and without notes."""

from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

from test_sitting import load_state, make_env, parse_sitting, run_sitting

ROOT = Path(__file__).resolve().parents[1]
WEEKLY = ROOT / "scripts" / "weekly.py"
REPLY = ROOT / "scripts" / "reply.py"
BANNED = ("you realized", "you learned", "you grew")
HTML_MARK = re.compile(r"(?i)<html\b|<!doctype\b|<body\b|<p\b|<article\b")
OWNER_NOTE = "The courtyard bell stayed with me today."


def run_weekly(
    data: Path, week_start: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    assert WEEKLY.is_file(), f"A5: missing {WEEKLY}"
    return subprocess.run(
        [
            sys.executable,
            str(WEEKLY),
            "--data",
            str(data),
            "--week-start",
            week_start,
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )


def run_reply(data: Path, day: str, note: str, env: dict[str, str]) -> None:
    assert REPLY.is_file(), f"A5: missing {REPLY}"
    result = subprocess.run(
        [
            sys.executable,
            str(REPLY),
            "--data",
            str(data),
            "--date",
            day,
            "--note",
            note,
        ],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr


def visible_html(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text)


def without_readings(text: str, readings: list[dict[str, object]]) -> str:
    cleaned = text.casefold()
    for parsed in readings:
        for line in parsed["quote"]:
            cleaned = cleaned.replace(str(line).casefold(), "")
        cleaned = cleaned.replace(str(parsed["source"]).casefold(), "")
    return cleaned


def assert_no_invented(text: str, readings: list[dict[str, object]], notes: str) -> None:
    cleaned = without_readings(text, readings)
    notes_folded = notes.casefold()
    for phrase in BANNED:
        if phrase.casefold() in notes_folded:
            continue
        assert phrase.casefold() not in cleaned, phrase


def longest_line(parsed: dict[str, object]) -> str:
    lines = [str(line) for line in parsed["quote"]]
    return max(lines, key=len)


def assert_week_contents(
    text: str,
    current: list[dict[str, object]],
    previous: dict[str, object],
) -> None:
    for parsed in current:
        assert str(parsed["tradition"]) in text
        assert str(parsed["source"]) in text
        for line in parsed["quote"]:
            assert str(line) in text, line
    previous_source = str(previous["source"])
    current_sources = {str(parsed["source"]) for parsed in current}
    if previous_source not in current_sources:
        assert previous_source not in text
    assert longest_line(previous) not in text


def assert_outputs(
    data: Path,
    current: list[dict[str, object]],
    previous: dict[str, object],
    notes: str,
) -> None:
    md_path = data / "what-changed-in-me.md"
    html_path = data / "what-changed-in-me.html"
    assert md_path.is_file(), md_path
    assert html_path.is_file(), html_path
    names = sorted(path.name for path in data.iterdir() if path.name.startswith("what-changed"))
    assert names == ["what-changed-in-me.html", "what-changed-in-me.md"], names
    markdown = md_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    assert markdown.strip(), "A5: empty markdown"
    assert html.strip(), "A5: empty html"
    assert HTML_MARK.search(html), "A5: html has no document tag"
    assert_week_contents(markdown, current, previous)
    assert_week_contents(visible_html(html), current, previous)
    assert "streak" in markdown.casefold()
    assert "focus" in markdown.casefold()
    assert_no_invented(markdown, current + [previous], notes)
    assert_no_invented(visible_html(html), current + [previous], notes)
    if notes:
        assert OWNER_NOTE in markdown
        assert OWNER_NOTE in visible_html(html)


def sit_week(data: Path, env: dict[str, str]) -> tuple[list[dict[str, object]], dict[str, object]]:
    week = date(2026, 10, 5)  # Monday, not the current week
    previous_day = week - timedelta(days=1)
    ordered = [previous_day] + [week + timedelta(days=offset) for offset in range(3)]
    parsed: list[dict[str, object]] = []
    for day in ordered:
        result = run_sitting(data, day.isoformat(), env)
        assert result.returncode == 0, result.stderr
        parsed.append(parse_sitting(result.stdout))
    return parsed[1:], parsed[0]


def prepare(tmp: Path) -> tuple[Path, dict[str, str]]:
    data = tmp / "data"
    data.mkdir()
    (data / "state.json").write_text(
        json.dumps({"sentinel": "keep-me", "tz": "America/New_York", "streak": 0}),
        encoding="utf-8",
    )
    return data, make_env(tmp)


def test_a5_without_notes_and_with_notes() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data, env = prepare(tmp)
        current, previous = sit_week(data, env)
        result = run_weekly(data, "2026-10-05", env)
        assert result.returncode == 0, result.stderr
        assert_outputs(data, current, previous, notes="")
        assert load_state(data)["sentinel"] == "keep-me"

        md_path = data / "what-changed-in-me.md"
        html_path = data / "what-changed-in-me.html"
        md_path.write_text("SENTINEL_OLD_WEEKLY\n" + md_path.read_text(encoding="utf-8"), encoding="utf-8")
        html_path.write_text(
            "SENTINEL_OLD_WEEKLY\n" + html_path.read_text(encoding="utf-8"),
            encoding="utf-8",
        )
        again = run_weekly(data, "2026-10-05", env)
        assert again.returncode == 0, again.stderr
        assert "SENTINEL_OLD_WEEKLY" not in md_path.read_text(encoding="utf-8")
        assert "SENTINEL_OLD_WEEKLY" not in html_path.read_text(encoding="utf-8")
        assert_outputs(data, current, previous, notes="")
        assert md_path.resolve() == (data / "what-changed-in-me.md").resolve()
        assert html_path.resolve() == (data / "what-changed-in-me.html").resolve()

    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data, env = prepare(tmp)
        current, previous = sit_week(data, env)
        run_reply(data, "2026-10-05", OWNER_NOTE, env)
        notes = (data / "notes.md").read_text(encoding="utf-8")
        assert OWNER_NOTE in notes
        result = run_weekly(data, "2026-10-05", env)
        assert result.returncode == 0, result.stderr
        assert_outputs(data, current, previous, notes=notes)
        assert load_state(data)["sentinel"] == "keep-me"
    print("A5 PASS")


def main() -> None:
    test_a5_without_notes_and_with_notes()


if __name__ == "__main__":
    main()
