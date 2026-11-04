#!/usr/bin/env python3
"""Overwrite the weekly page in place from logged sittings and notes."""

from __future__ import annotations

import argparse
import html
from datetime import date, timedelta
from pathlib import Path

from sitting import atomic_write, load_state, read_sittings

FOCUS = "Next week's focus: carry one question into a single ordinary hour."


def as_int_fallback_local(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def week_note_lines(text: str, start: date) -> list[str]:
    days = [(start + timedelta(days=offset)).isoformat() for offset in range(7)]
    kept: list[str] = []
    for line in text.splitlines():
        if line.strip() and any(day in line for day in days):
            kept.append(line)
    return kept


def reading_blocks(rows: list[dict[str, str]]) -> list[str]:
    blocks: list[str] = []
    for row in rows:
        blocks.append(row["tradition"])
        blocks.append(row["source"])
        blocks.extend(row["reading"].replace("\r\n", "\n").splitlines())
        blocks.append("")
    return blocks


def theme_line(state: dict, start: date) -> str:
    themes = state.get("themes")
    if not isinstance(themes, dict):
        return ""
    ordered: list[str] = []
    for offset in range(7):
        theme = themes.get((start + timedelta(days=offset)).isoformat())
        if isinstance(theme, str) and theme not in ordered:
            ordered.append(theme)
    if not ordered:
        return ""
    return "Themes this week: " + "; ".join(ordered) + "."


def build_markdown(
    rows: list[dict[str, str]],
    start: date,
    end: date,
    streak: int,
    notes: list[str],
    themes: str,
) -> str:
    parts = [
        "# What changed in me",
        "",
        f"Week of {start.isoformat()} through {end.isoformat()}.",
        "",
        "## Readings",
        "",
    ]
    parts.extend(reading_blocks(rows))
    parts.append(f"Streak: {streak}.")
    if themes:
        parts.append(themes)
    if notes:
        parts.extend(["", "## In your words", ""])
        parts.extend(notes)
    parts.extend(["", FOCUS, ""])
    return "\n".join(parts)


def build_html(
    rows: list[dict[str, str]],
    start: date,
    end: date,
    streak: int,
    notes: list[str],
    themes: str,
) -> str:
    def paragraph(text: str) -> str:
        return f"<p>{html.escape(text, quote=False)}</p>"

    chunks = [
        "<!DOCTYPE html>",
        '<html lang="en">',
        "<head>",
        '<meta charset="utf-8">',
        "<title>What changed in me</title>",
        "</head>",
        "<body>",
        "<article>",
        "<h1>What changed in me</h1>",
        paragraph(f"Week of {start.isoformat()} through {end.isoformat()}."),
        "<h2>Readings</h2>",
    ]
    for row in rows:
        chunks.append(paragraph(row["tradition"]))
        chunks.append(paragraph(row["source"]))
        for line in row["reading"].replace("\r\n", "\n").splitlines():
            chunks.append(paragraph(line))
    chunks.append(paragraph(f"Streak: {streak}."))
    if themes:
        chunks.append(paragraph(themes))
    if notes:
        chunks.append("<h2>In your words</h2>")
        chunks.extend(paragraph(line) for line in notes)
    chunks.append(paragraph(FOCUS))
    chunks.extend(["</article>", "</body>", "</html>", ""])
    return "\n".join(chunks)


def write_week(data: Path, week_start: str) -> None:
    start = date.fromisoformat(week_start)
    end = start + timedelta(days=6)
    rows = [
        row
        for row in read_sittings(data / "sittings.csv")
        if start <= date.fromisoformat(row["date"]) <= end
    ]
    rows.sort(key=lambda row: row["date"])
    state = load_state(data / "state.json")
    streak = as_int_fallback_local(state.get("streak"))
    notes_path = data / "notes.md"
    notes_text = notes_path.read_text(encoding="utf-8") if notes_path.is_file() else ""
    notes = week_note_lines(notes_text, start)
    themes = theme_line(state, start)
    atomic_write(
        data / "what-changed-in-me.md",
        build_markdown(rows, start, end, streak, notes, themes),
    )
    atomic_write(
        data / "what-changed-in-me.html",
        build_html(rows, start, end, streak, notes, themes),
    )


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write the weekly page in place.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--week-start", required=True, help="Monday YYYY-MM-DD")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    write_week(Path(args.data), args.week_start)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
