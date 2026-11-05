#!/usr/bin/env python3
"""Atomic state helpers for Roast My Feed. Merge state. Never log secrets."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

PROTECTED_MESSAGE = "I can't read that account."
FOOTER = "Try Hermes: Roast My Feed by SMF Works"
PROFILE_LINK_MESSAGE = (
    "I could not find that account. Send a profile link and I will try again."
)
NO_TOKEN_MESSAGE = (
    "No X_BEARER_TOKEN is set. Add X_BEARER_TOKEN in the environment "
    "or the secret store, then run the read again. "
    "You can also pass a tweets.js archive with --archive."
)
INTRO = (
    "I'm Roast My Feed. Give me an X handle and in about 2 minutes you get a "
    "Wrapped-style audit: your archetype, best post, worst habit, a 7-day plan, "
    "and 3 posts drafted in your voice. Witty, never cruel, and every number is "
    "real. No X login needed. What's the handle?"
)
NO_EARLIER = "No earlier roast for this handle."


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


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return loaded


def save_state(path: Path, updates: dict) -> None:
    """Merge updates into the existing object and keep unknown keys."""
    with FileLock(path):
        state = load_state(path)
        state.update(updates)
        atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def append_jsonl(path: Path, row: dict) -> None:
    line = json.dumps(row, ensure_ascii=False)
    with FileLock(path):
        existing = path.read_text(encoding="utf-8") if path.is_file() else ""
        if existing and not existing.endswith("\n"):
            existing += "\n"
        atomic_write(path, existing + line + "\n")


def parse_time(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_time(value: datetime) -> str:
    utc = value.astimezone(timezone.utc).replace(microsecond=0)
    return utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def shift_days(now_text: str, days: int) -> str:
    return format_time(parse_time(now_text) + timedelta(days=days))


def utc_now_text() -> str:
    return format_time(datetime.now(timezone.utc))


def strip_handle(raw: str) -> str:
    """Drop one leading @ and, for an X or Twitter URL, keep the username segment."""
    text = (raw or "").strip()
    if text.startswith("@"):
        text = text[1:].strip()
    parsed = urlparse(text)
    scheme = (parsed.scheme or "").lower()
    if scheme in {"http", "https"} and parsed.netloc:
        host = parsed.netloc.lower()
        if "@" in host:
            host = host.split("@", 1)[1]
        host = host.split(":", 1)[0]
        x_host = host == "x.com" or host.endswith(".x.com")
        twitter_host = host == "twitter.com" or host.endswith(".twitter.com")
        if x_host or twitter_host:
            segments = [segment for segment in parsed.path.split("/") if segment]
            if segments:
                return segments[0]
    return text.strip()
