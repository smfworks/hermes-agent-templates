#!/usr/bin/env python3
"""A2 and A3 — SPEC §10.2 ten days, SPEC §10.3 same-day rerun."""

from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "sitting.py"

COLUMNS = ["date", "tradition", "source", "reading", "question", "replied"]
TRADITIONS = {
    "Stoic",
    "Greek/classical",
    "Christian (patristic, contemplative)",
    "Jewish",
    "Buddhist",
    "Islamic/Sufi",
    "Confucian/Taoist",
    "Hindu",
    "modern essayists",
}
THEMES = {
    "flourishing",
    "contemplation and action",
    "faith and reason",
    "attention",
    "gratitude",
    "courage",
    "death and time",
    "friendship",
    "work",
}
CLOSE = "Reply with one line tonight if you like."
HEADER_RE = re.compile(r"^\*\*Today's reading — (.+)\*\*$")
QUESTION_RE = re.compile(r"^\*\*Question for today:\*\* (.+)$")
CITATION_RE = re.compile(r",\s+\*[^*]+\*")


def make_env(tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    env["HOME"] = str(home)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def run_sitting(
    data: Path, day: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), f"missing {SCRIPT}"
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--data", str(data), "--date", day],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )


def parse_sitting(text: str) -> dict[str, object]:
    """Parse SPEC §4 stdout. Blank lines are ignored. Em dash is U+2014."""
    raw = text.replace("\r\n", "\n")
    assert raw.count("**Question for today:**") == 1, "sitting: question count"
    assert raw.count(CLOSE) == 1, "sitting: close count"
    content = [line.rstrip() for line in raw.strip("\n").split("\n") if line.strip()]
    assert content, "sitting: empty stdout"
    header = HEADER_RE.fullmatch(content[0])
    assert header, f"sitting: header {content[0]!r}"
    tradition = header.group(1).strip()
    assert tradition in TRADITIONS, tradition
    index = 1
    quote: list[str] = []
    while index < len(content) and content[index].startswith(">"):
        body = content[index][1:]
        if body.startswith(" "):
            body = body[1:]
        assert body.strip(), "sitting: empty quote line"
        quote.append(body)
        index += 1
    assert 2 <= len(quote) <= 5, quote
    assert index < len(content), "sitting: missing attribution"
    attribution = content[index]
    assert attribution.startswith("—"), attribution
    source = attribution.lstrip("—").strip()
    if "(paraphrase)" in source.lower():
        kind = "paraphrase"
    else:
        assert CITATION_RE.search(source), source
        kind = "attributed"
    index += 1
    assert index < len(content), "sitting: missing context"
    context = content[index]
    assert not context.startswith("**"), context
    assert context.endswith("."), context
    index += 1
    assert index < len(content), "sitting: missing question"
    question_match = QUESTION_RE.fullmatch(content[index])
    assert question_match, content[index]
    question = question_match.group(1).strip()
    assert question, "sitting: empty question"
    assert "\n" not in question
    index += 1
    assert index < len(content), "sitting: missing close"
    assert content[index] == CLOSE, content[index]
    index += 1
    assert index == len(content), content[index:]
    return {
        "tradition": tradition,
        "quote": quote,
        "source": source,
        "kind": kind,
        "context": context,
        "question": question,
    }


def read_sittings(path: Path) -> list[dict[str, str]]:
    assert path.is_file(), f"missing {path}"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        assert list(reader.fieldnames or []) == COLUMNS, reader.fieldnames
        return list(reader)


def load_state(data: Path) -> dict:
    state = json.loads((data / "state.json").read_text(encoding="utf-8"))
    assert isinstance(state, dict), state
    return state


def assert_row(row: dict[str, str], day: str, parsed: dict[str, object]) -> None:
    assert row["date"] == day
    assert row["tradition"] == parsed["tradition"]
    assert row["source"] == parsed["source"]
    assert row["reading"].replace("\r\n", "\n").splitlines() == parsed["quote"]
    assert row["question"] == parsed["question"]
    assert "\n" not in row["question"]
    assert row["replied"] == "n"


def assert_tradition_gap(rows: list[dict[str, str]]) -> None:
    parsed_rows = [(date.fromisoformat(row["date"]), row["tradition"]) for row in rows]
    for day, tradition in parsed_rows:
        for older, other in parsed_rows:
            delta = (day - older).days
            if 1 <= delta <= 3:
                assert tradition.casefold() != other.casefold(), (day, tradition, older)


def assert_theme_weeks(themes: dict) -> None:
    by_week: dict[date, list[str]] = {}
    for key, theme in themes.items():
        assert theme in THEMES, theme
        day = date.fromisoformat(key)
        monday = day - timedelta(days=day.weekday())
        by_week.setdefault(monday, []).append(theme)
    for monday, values in by_week.items():
        assert len(values) == len(set(values)), (monday.isoformat(), values)


def test_a2_ten_days() -> None:
    start = date(2026, 11, 2)  # Monday
    days = [(start + timedelta(days=offset)).isoformat() for offset in range(10)]
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        (data / "state.json").write_text(
            json.dumps({"tz": "America/New_York", "sentinel": "keep-me"}),
            encoding="utf-8",
        )
        env = make_env(tmp)
        parsed_by_day: dict[str, dict[str, object]] = {}
        for day in days:
            result = run_sitting(data, day, env)
            assert result.returncode == 0, result.stderr
            parsed = parse_sitting(result.stdout)
            parsed_by_day[day] = parsed
            state = load_state(data)
            assert state.get("sentinel") == "keep-me"
            assert state.get("tz") == "America/New_York"
            themes = state.get("themes")
            assert isinstance(themes, dict), state
            assert themes.get(day) in THEMES, themes
        rows = read_sittings(data / "sittings.csv")
        assert [row["date"] for row in rows] == days
        assert len(rows) == 10
        for row in rows:
            assert_row(row, row["date"], parsed_by_day[row["date"]])
        assert_tradition_gap(rows)
        questions = [row["question"] for row in rows]
        assert len(questions) == len(set(questions)), questions
        themes = load_state(data)["themes"]
        assert set(themes) == set(days)
        assert_theme_weeks(themes)
    print("A2 PASS")


def test_a3_same_day_idempotent() -> None:
    day = "2026-11-02"
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        env = make_env(tmp)
        first = run_sitting(data, day, env)
        assert first.returncode == 0, first.stderr
        parsed = parse_sitting(first.stdout)
        before = read_sittings(data / "sittings.csv")
        assert len(before) == 1
        assert_row(before[0], day, parsed)
        theme = load_state(data)["themes"][day]
        second = run_sitting(data, day, env)
        assert second.returncode == 0, second.stderr
        assert second.stdout == first.stdout, "A3: stdout changed on the same date"
        after = read_sittings(data / "sittings.csv")
        assert len(after) == len(before), "A3: sittings.csv row count changed"
        assert after == before, "A3: logged sitting changed"
        assert load_state(data)["themes"][day] == theme
    print("A3 PASS")


def main() -> None:
    test_a2_ten_days()
    test_a3_same_day_idempotent()


if __name__ == "__main__":
    main()
