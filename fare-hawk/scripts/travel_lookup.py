#!/usr/bin/env python3
"""Normalize a fixtures-backend trip or watch file. No network calls."""

from __future__ import annotations

import json
from pathlib import Path

OBSERVATION_DEFAULTS = (
    "currency",
    "cabin",
    "room",
    "product_key",
    "source",
    "link",
    "route",
    "party",
    "details",
    "notes",
)


def load_fixture(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("fixture must be a JSON object")
    return payload


def observation_rows(payload: dict) -> list[dict]:
    defaults = {
        key: payload.get(key)
        for key in OBSERVATION_DEFAULTS
        if payload.get(key) is not None
    }
    rows = []
    for obs in payload.get("observations") or []:
        if not isinstance(obs, dict):
            continue
        merged = dict(defaults)
        merged.update(obs)
        rows.append(merged)
    return rows
