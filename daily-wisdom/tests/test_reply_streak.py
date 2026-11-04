#!/usr/bin/env python3
"""A4 — SPEC §10.4 reply thanks, notes row, streak, no guilt language."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from test_sitting import load_state, make_env, read_sittings, run_sitting

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "reply.py"
GUILT = (
    "should have",
    "you failed",
    "don't break your streak",
    "don’t break your streak",
    "guilty",
    "disappoint",
)


def run_reply(
    data: Path, day: str, note: str, env: dict[str, str]
) -> subprocess.CompletedProcess[str]:
    assert SCRIPT.is_file(), f"A4: missing {SCRIPT}"
    return subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
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


def assert_thanks(result: subprocess.CompletedProcess[str]) -> None:
    assert result.returncode == 0, result.stderr
    lines = [line for line in result.stdout.splitlines() if line.strip()]
    assert len(lines) == 1, result.stdout
    assert len(lines[0]) <= 200, lines[0]
    lowered = result.stdout.casefold()
    for phrase in GUILT:
        assert phrase.casefold() not in lowered, phrase


def assert_note_line(notes: str, day: str, note: str) -> None:
    assert any(day in line and note in line for line in notes.splitlines()), notes


def test_a4_reply_streak_and_gap() -> None:
    days = ["2026-12-01", "2026-12-02", "2026-12-03", "2026-12-04"]
    note_1 = "kept the question in my pocket"
    note_2 = "done"
    note_4 = "one quiet hour"
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = tmp / "data"
        data.mkdir()
        (data / "state.json").write_text(
            json.dumps({"sentinel": "keep-me"}),
            encoding="utf-8",
        )
        env = make_env(tmp)
        for day in days:
            sat = run_sitting(data, day, env)
            assert sat.returncode == 0, sat.stderr

        first = run_reply(data, days[0], note_1, env)
        assert_thanks(first)
        notes = (data / "notes.md").read_text(encoding="utf-8")
        assert_note_line(notes, days[0], note_1)
        state = load_state(data)
        assert state["sentinel"] == "keep-me"
        assert state["streak"] == 1
        assert state["last_reply_date"] == days[0]
        assert isinstance(state["longest"], int) and not isinstance(state["longest"], bool)
        assert state["longest"] >= 1
        rows = {row["date"]: row for row in read_sittings(data / "sittings.csv")}
        assert rows[days[0]]["replied"] == "y"
        assert rows[days[1]]["replied"] == "n"

        second = run_reply(data, days[1], note_2, env)
        assert_thanks(second)
        notes = (data / "notes.md").read_text(encoding="utf-8")
        assert_note_line(notes, days[0], note_1)
        assert_note_line(notes, days[1], note_2)
        state = load_state(data)
        assert state["sentinel"] == "keep-me"
        assert state["streak"] == 2
        assert state["last_reply_date"] == days[1]
        assert state["longest"] >= 2
        rows = {row["date"]: row for row in read_sittings(data / "sittings.csv")}
        assert rows[days[1]]["replied"] == "y"
        assert rows[days[2]]["replied"] == "n"
        assert len(read_sittings(data / "sittings.csv")) == 4

        # 2026-12-03 has a sitting and no reply. The next reply is not consecutive.
        third = run_reply(data, days[3], note_4, env)
        assert_thanks(third)
        notes = (data / "notes.md").read_text(encoding="utf-8")
        assert_note_line(notes, days[3], note_4)
        assert_note_line(notes, days[0], note_1)
        state = load_state(data)
        assert state["sentinel"] == "keep-me"
        assert state["streak"] in (0, 1), state["streak"]
        assert state["longest"] >= 2
        rows = {row["date"]: row for row in read_sittings(data / "sittings.csv")}
        assert rows[days[2]]["replied"] == "n"
        assert rows[days[3]]["replied"] == "y"
        assert "themes" in state and days[0] in state["themes"]
    print("A4 PASS")


def main() -> None:
    test_a4_reply_streak_and_gap()


if __name__ == "__main__":
    main()
