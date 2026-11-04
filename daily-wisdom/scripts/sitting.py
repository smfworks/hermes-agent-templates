#!/usr/bin/env python3
"""Print one Daily Wisdom sitting and log it under --data.

A second run for the same local date reprints the logged sitting and does
not add a row. Corpus order is the rotation: the first reading that clears
the 3-day tradition gap, the Monday–Sunday theme set, and the 30-day
question window is the one that is logged.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path

EM = "\u2014"
CLOSE = "Reply with one line tonight if you like."
COLUMNS = ["date", "tradition", "source", "reading", "question", "replied"]
TRADITIONS = (
    "Stoic",
    "Greek/classical",
    "Christian (patristic, contemplative)",
    "Jewish",
    "Buddhist",
    "Islamic/Sufi",
    "Confucian/Taoist",
    "Hindu",
    "modern essayists",
)
THEMES = (
    "flourishing",
    "contemplation and action",
    "faith and reason",
    "attention",
    "gratitude",
    "courage",
    "death and time",
    "friendship",
    "work",
)
ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "data" / "readings.json"
YES_NO = (
    "do ",
    "does ",
    "did ",
    "is ",
    "are ",
    "was ",
    "were ",
    "can ",
    "could ",
    "will ",
    "would ",
    "should ",
    "has ",
    "have ",
    "had ",
)


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit(f"state is not an object: {path}")
    return loaded


def save_state(path: Path, state: dict) -> None:
    atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def read_sittings(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        if list(reader.fieldnames or []) != COLUMNS:
            raise SystemExit(f"sittings.csv columns must be {','.join(COLUMNS)}")
        return [dict(row) for row in reader]


def write_sittings(path: Path, rows: list[dict[str, str]]) -> None:
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=COLUMNS,
        lineterminator="\n",
        extrasaction="ignore",
        quoting=csv.QUOTE_ALL,
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({column: row.get(column, "") for column in COLUMNS})
    atomic_write(path, buffer.getvalue())


def format_source(entry: dict) -> str:
    section = str(entry.get("section") or "").strip()
    source = f"{entry['author']}, *{entry['work']}*"
    if section:
        source = f"{source}, {section}"
    if entry.get("paraphrase"):
        source = f"{source} (paraphrase)"
    return source


def load_readings() -> list[dict]:
    loaded = json.loads(CORPUS.read_text(encoding="utf-8"))
    if not isinstance(loaded, list) or len(loaded) < 18:
        raise SystemExit("readings.json needs at least 18 entries")
    seen: set[str] = set()
    traditions: set[str] = set()
    themes: set[str] = set()
    for entry in loaded:
        tradition = entry["tradition"]
        theme = entry["theme"]
        if tradition not in TRADITIONS:
            raise SystemExit(f"unknown tradition: {tradition}")
        if theme not in THEMES:
            raise SystemExit(f"unknown theme: {theme}")
        lines = entry["lines"]
        if not isinstance(lines, list) or not 2 <= len(lines) <= 5:
            raise SystemExit(f"reading lines must be 2-5: {entry.get('work')}")
        if any(not isinstance(line, str) or not line.strip() or "\n" in line for line in lines):
            raise SystemExit(f"bad reading line: {entry.get('work')}")
        context = entry["context"]
        question = entry["question"]
        if not isinstance(context, str) or "\n" in context or not context.endswith("."):
            raise SystemExit(f"context must be one sentence: {entry.get('work')}")
        if not isinstance(question, str) or not question.strip() or "\n" in question:
            raise SystemExit(f"question must be one line: {entry.get('work')}")
        if question.lower().startswith(YES_NO):
            raise SystemExit(f"question looks yes/no: {question}")
        if question in seen:
            raise SystemExit(f"duplicate question: {question}")
        seen.add(question)
        traditions.add(tradition)
        themes.add(theme)
    if traditions != set(TRADITIONS) or themes != set(THEMES):
        raise SystemExit("corpus must cover every tradition and every theme")
    return loaded


def render(tradition: str, lines: list[str], source: str, context: str, question: str) -> str:
    body = [f"**Today's reading {EM} {tradition}**"]
    body.extend(f"> {line}" for line in lines)
    body.append(f"{EM} {source}")
    body.append(context)
    body.append(f"**Question for today:** {question}")
    body.append(CLOSE)
    return "\n".join(body) + "\n"


def lookup_context(source: str, lines: list[str]) -> str | None:
    for entry in load_readings():
        if format_source(entry) == source and list(entry["lines"]) == lines:
            return str(entry["context"])
    return None


def week_bounds(day: date) -> tuple[date, date]:
    monday = day - timedelta(days=day.weekday())
    return monday, monday + timedelta(days=6)


def themes_used(state: dict, day: date) -> set[str]:
    themes = state.get("themes")
    if not isinstance(themes, dict):
        return set()
    monday, sunday = week_bounds(day)
    used: set[str] = set()
    for key, theme in themes.items():
        try:
            logged = date.fromisoformat(str(key))
        except ValueError:
            continue
        if monday <= logged <= sunday and logged != day and isinstance(theme, str):
            used.add(theme)
    return used


def pick(readings: list[dict], day: date, rows: list[dict[str, str]], state: dict) -> dict:
    recent: set[str] = set()
    used_questions: set[str] = set()
    for row in rows:
        logged = date.fromisoformat(row["date"])
        delta = (day - logged).days
        if 1 <= delta <= 3:
            recent.add(row["tradition"].casefold())
        if 1 <= delta <= 30:
            used_questions.add(row["question"])
    blocked_themes = themes_used(state, day)
    for entry in readings:
        if entry["tradition"].casefold() in recent:
            continue
        if entry["theme"] in blocked_themes:
            continue
        if entry["question"] in used_questions:
            continue
        return entry
    raise SystemExit("no reading clears the tradition, theme, and question rules")


def sitting_text(data: Path, day: date) -> str:
    day_s = day.isoformat()
    rows = read_sittings(data / "sittings.csv")
    existing = next((row for row in rows if row["date"] == day_s), None)
    if existing is not None:
        lines = existing["reading"].replace("\r\n", "\n").splitlines()
        context = lookup_context(existing["source"], lines)
        if context is None:
            raise SystemExit("logged sitting has no matching corpus context")
        return render(
            existing["tradition"],
            lines,
            existing["source"],
            context,
            existing["question"],
        )
    entry = pick(load_readings(), day, rows, load_state(data / "state.json"))
    source = format_source(entry)
    return render(
        str(entry["tradition"]),
        list(entry["lines"]),
        source,
        str(entry["context"]),
        str(entry["question"]),
    )


def missed_reply(state: dict, day: date) -> bool:
    """True when the streak should drop to 0: last reply is before yesterday."""
    last = state.get("last_reply_date")
    if not isinstance(last, str) or not last.strip():
        streak = state.get("streak")
        return isinstance(streak, int) and not isinstance(streak, bool) and streak > 0
    try:
        last_day = date.fromisoformat(last)
    except ValueError:
        return True
    return last_day < day - timedelta(days=1)


def log_sitting(data: Path, day: date) -> str:
    """Return stdout. Write csv and state only when this date is new.

    A missed local day (last reply before yesterday) writes streak 0 even on a
    same-day reprint, so the morning sitting shows 0 before the next reply.
    """
    day_s = day.isoformat()
    csv_path = data / "sittings.csv"
    rows = read_sittings(csv_path)
    state_path = data / "state.json"
    state = load_state(state_path)
    streak_reset = missed_reply(state, day)
    if streak_reset:
        state["streak"] = 0
    if any(row["date"] == day_s for row in rows):
        if streak_reset:
            save_state(state_path, state)
        return sitting_text(data, day)
    entry = pick(load_readings(), day, rows, state)
    source = format_source(entry)
    lines = list(entry["lines"])
    text = render(
        str(entry["tradition"]),
        lines,
        source,
        str(entry["context"]),
        str(entry["question"]),
    )
    rows.append(
        {
            "date": day_s,
            "tradition": str(entry["tradition"]),
            "source": source,
            "reading": "\n".join(lines),
            "question": str(entry["question"]),
            "replied": "n",
        }
    )
    write_sittings(csv_path, rows)
    themes = state.get("themes")
    if not isinstance(themes, dict):
        themes = {}
    else:
        themes = dict(themes)
    themes[day_s] = str(entry["theme"])
    state["themes"] = themes
    save_state(state_path, state)
    return text


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Log one Daily Wisdom sitting.")
    parser.add_argument("--data", required=True, help="Profile wisdom directory")
    parser.add_argument("--date", help="Local date YYYY-MM-DD (default: today)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    data = Path(args.data)
    if args.date:
        day = date.fromisoformat(args.date)
    else:
        day = date.today()
    sys.stdout.write(log_sitting(data, day))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except BrokenPipeError:
        raise SystemExit(0) from None
