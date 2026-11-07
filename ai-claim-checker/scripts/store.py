#!/usr/bin/env python3
"""Atomic state helpers for AI Claim Checker. Merge state. Never log secrets."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

VERDICTS = ("supported", "vendor-only", "contradicted", "unverifiable")
SOURCE_ROLES = ("vendor", "vendor-derived", "independent", "relay", "snippet")
FOCUS_CHOICES = ("benchmarks", "pricing", "capabilities", "all")
STYLE_CHOICES = ("card", "brief")
FOOTER = "Try Hermes: AI Claim Checker by SMF Works."
INTRO = (
    "Hi, I'm Verity, your AI Claim Checker. Paste any AI launch post, "
    "benchmark chart, or price claim and I'll give you a dated claim card: "
    "supported, vendor-only, contradicted, or unverifiable, with sources."
)
DATE_NOT_STATED = "date not stated"
NONE_FOUND = "None found"
FIXTURE_BANNER = "fixture/demo, not live verification"
DEFAULT_TZ = "America/New_York"
JOB_ID = "verity-weekly-recheck"
SLUG_RE = re.compile(r"[^a-z0-9._-]+")


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


def read_json(path: Path, default: object | None = None) -> object:
    if not path.is_file():
        return {} if default is None else default
    loaded = json.loads(path.read_text(encoding="utf-8"))
    return loaded


def write_json(path: Path, payload: object) -> None:
    with FileLock(path):
        atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


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


def utc_now_text() -> str:
    return format_time(datetime.now(timezone.utc))


def check_date(now_text: str) -> str:
    return parse_time(now_text).date().isoformat()


def sanitize_slug(raw: str) -> str:
    text = (raw or "").strip().lower().replace("\\", "/")
    if "/" in text:
        text = text.split("/")[-1]
    text = SLUG_RE.sub("-", text).strip(".-")
    if not text or text in {".", ".."}:
        text = "claim"
    return text[:80]


def data_root(data: Path) -> Path:
    return Path(data).resolve()


def claim_dir(data: Path, slug: str) -> Path:
    root = (data_root(data) / "claims").resolve()
    path = (root / sanitize_slug(slug)).resolve()
    if path != root and root not in path.parents:
        raise ValueError("slug escapes profile root")
    return path


def is_safe_http_url(url: str) -> bool:
    parsed = urlparse((url or "").strip())
    if parsed.scheme not in {"http", "https"}:
        return False
    if not parsed.netloc:
        return False
    if parsed.username or parsed.password:
        return False
    return True


def scrub_secret_like(text: str) -> str:
    cleaned = text or ""
    cleaned = re.sub(r"tok_[A-Za-z0-9_]+", "", cleaned)
    cleaned = re.sub(r"sk-" r"[A-Za-z0-9_-]+", "", cleaned)
    cleaned = re.sub("xox" "b-[A-Za-z0-9-]+", "", cleaned)
    return cleaned
