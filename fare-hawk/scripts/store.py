#!/usr/bin/env python3
"""Atomic JSON, CSV, and lock helpers. Writes stay inside the data directory."""

from __future__ import annotations

import csv
import io
import json
import os
import re
import time
from datetime import datetime
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from zoneinfo import ZoneInfo

TWOPLACES = Decimal("0.01")
SLUG_RE = re.compile(r"^[a-z0-9-]{1,64}$")
ZONE_SHORT = {"America/New_York": "ET"}
PRICE_COLUMNS = [
    "seen_at",
    "status",
    "price",
    "currency",
    "source",
    "link",
    "notes",
    "product_key",
]


def money(value: Decimal | str | int) -> str:
    decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    return format(decimal.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN), "f")


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
        for _ in range(400):
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


def valid_slug(slug: str) -> bool:
    return isinstance(slug, str) and SLUG_RE.fullmatch(slug) is not None


def require_slug(slug: str) -> str:
    if not valid_slug(slug):
        raise SystemExit(2)
    return slug


def inside(root: Path, path: Path) -> Path:
    root_real = root.resolve()
    path_real = path.resolve()
    if not path_real.is_relative_to(root_real):
        raise SystemExit(2)
    return path


def trip_path(data: Path, slug: str, name: str) -> Path:
    require_slug(slug)
    return inside(data, data / "trips" / name)


def load_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        return {}
    return loaded


def save_json(path: Path, updates: dict) -> dict:
    with FileLock(path):
        state = load_json(path)
        state.update(updates)
        atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        return state


def mutate_json(path: Path, mutator) -> dict:
    with FileLock(path):
        state = load_json(path)
        mutator(state)
        atomic_write(path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
        return state


def civil_date(iso: str, tz: str):
    instant = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return instant.astimezone(ZoneInfo(tz)).date()


def owner_stamp(iso: str, tz: str) -> str:
    instant = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))
    label = ZONE_SHORT.get(tz, tz)
    return instant.strftime("%Y-%m-%d %H:%M") + f" {label}"


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv_rows(path: Path, rows: list[dict[str, str]]) -> None:
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=PRICE_COLUMNS,
        lineterminator="\n",
        quoting=csv.QUOTE_MINIMAL,
        extrasaction="ignore",
    )
    writer.writeheader()
    for row in rows:
        writer.writerow({key: row.get(key, "") for key in PRICE_COLUMNS})
    atomic_write(path, buffer.getvalue())


def read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    text = ("\n".join(lines) + "\n") if lines else ""
    atomic_write(path, text)
