#!/usr/bin/env python3
"""Normalize a fixtures-backend trip or watch file. No network calls."""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlparse

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


def _link_allowed(link: str, fixture_home: str) -> bool:
    """hsf_ba7e3355: observation links are travel-page-derived and reach the
    owner's alert body. Only https URLs whose host matches the fixture's own
    domain (or its parent domain) pass; everything else is flagged off."""
    try:
        parsed = urlparse(link)
    except ValueError:
        return False
    if (parsed.scheme or "").lower() != "https" or not parsed.netloc:
        return False
    host = parsed.netloc.rsplit("@", 1)[-1].split(":", 1)[0].strip("[]").lower()
    home = (fixture_home or "").lower()
    if not home:
        return False
    return host == home or host.endswith("." + home)


def observation_rows(payload: dict) -> list[dict]:
    defaults = {
        key: payload.get(key)
        for key in OBSERVATION_DEFAULTS
        if payload.get(key) is not None
    }
    # The fixture's own domain anchors the link allowlist (the watch is set
    # up from a travel page; its host is the trusted booking origin).
    fixture_home = urlparse(str(payload.get("link") or "")).netloc.lower()
    if not fixture_home:
        fixture_home = urlparse(str(payload.get("source") or "")).netloc.lower()
    rows = []
    for obs in payload.get("observations") or []:
        if not isinstance(obs, dict):
            continue
        merged = dict(defaults)
        merged.update(obs)
        link = str(merged.get("link") or "")
        if link and not _link_allowed(link, fixture_home):
            # Flag, don't drop: the price observation stays valid, the link
            # does not travel to the owner's alert.
            merged["link"] = ""
            merged["link_flag"] = "rejected: not an https link on the watched domain"
        rows.append(merged)
    return rows
