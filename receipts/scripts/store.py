#!/usr/bin/env python3
"""Atomic file helpers for Receipts. Merge state. Never log secrets."""

from __future__ import annotations

import csv
import io
import json
import os
import time
from pathlib import Path

COLUMNS = [
    "service",
    "plan",
    "amount",
    "currency",
    "cadence",
    "last_charge",
    "next_renewal",
    "renewal_is_estimate",
    "status",
    "kind",
    "source_msg_ids",
    "evidence_quote",
    "notes",
    "sender",
]


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


def window_days(state: dict | None = None) -> int:
    """Heads-up window from state.json: 3, 5 (default), or 7."""
    if not state:
        return 5
    raw = state.get("window", 5)
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return 5
    if value in (3, 5, 7):
        return value
    return 5


def load_state(path: Path) -> dict:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return loaded


def save_state(path: Path, updates: dict) -> None:
    with FileLock(path):
        state = load_state(path)
        state.update(updates)
        atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    ordered = sorted(
        rows,
        key=lambda row: (
            row.get("service", ""),
            row.get("plan", ""),
            row.get("cadence", ""),
        ),
    )
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLUMNS, lineterminator="\n")
    writer.writeheader()
    for row in ordered:
        writer.writerow({key: row.get(key, "") for key in COLUMNS})
    atomic_write(path, buf.getvalue())


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    atomic_write(path, ("\n".join(lines) + ("\n" if lines else "")))


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows
