#!/usr/bin/env python3
"""Atomic helpers for AI Daily Radar. Merge state. Never log secrets."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

TAGS = (
    "Shipped",
    "Announced",
    "Vendor-claimed",
    "Independently tested",
    "Rumor",
)
FOOTER = "Try Hermes: AI Daily Radar by SMF Works."
INTRO = (
    "I'm Radar. Each morning I send up to 7 AI changes that matter to your stack, "
    "each tagged by how solid the evidence is, with links. I never post, email others, "
    "or buy anything."
)
FIXTURE_BANNER = "fixture/demo, not live news"
DATE_NOT_STATED = "date not stated"
DEFAULT_TZ = "America/New_York"
JOB_DAILY = "radar-daily-brief"
JOB_MONTHLY = "radar-monthly-tuneup"
MAX_ITEMS = 7
HEADLINE_WORDS = 12


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    with temporary.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


class FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path.with_name(f".{path.name}.lock")
        self.fd: int | None = None

    def __enter__(self) -> FileLock:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(100):
            try:
                self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
                return self
            except FileExistsError:
                time.sleep(0.02)
        raise TimeoutError(f"timed out waiting for {self.path}")

    def __exit__(self, *exc: object) -> None:
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def load_json(path: Path, default: object | None = None) -> object:
    if not path.is_file():
        return {} if default is None else default
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def write_json(path: Path, payload: object) -> None:
    with FileLock(path):
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def mutate_json(path: Path, apply) -> dict:
    with FileLock(path):
        state = load_json(path, default={})
        if not isinstance(state, dict):
            state = {}
        apply(state)
        atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        return state


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    text = "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows)
    with FileLock(path):
        atomic_write(path, text)


def parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def check_date(now_text: str) -> str:
    return parse_time(now_text).date().isoformat()


def iso_week(now_text: str) -> str:
    year, week, _ = parse_time(now_text).isocalendar()
    return f"{year}-W{week:02d}"


def is_safe_http_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc or parsed.username or parsed.password:
        return False
    return True


def word_count(text: str) -> int:
    return len([part for part in re.split(r"\s+", (text or "").strip()) if part])
