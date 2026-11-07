#!/usr/bin/env python3
"""Load a fixture pack as evidence reads for this run. Never pretend it is live."""

from __future__ import annotations

import json
from pathlib import Path

from store import FIXTURE_BANNER


def load_fixture(path: Path) -> dict:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("fixture must be an object")
    payload["fixture"] = True
    payload.setdefault("backend", "fixtures")
    for source in payload.get("sources") or []:
        if isinstance(source, dict):
            source.setdefault("read_this_run", True)
            source.setdefault("run_id", payload.get("run_id"))
    return payload


def timeout_payload(run_id: str, title: str, source_id: str, url: str) -> dict:
    return {
        "title": title,
        "run_id": run_id,
        "fixture": True,
        "unreadable_input": f"{source_id} timed out or was unreachable ({url})",
        "claims": [
            {
                "id": "c1",
                "text": title,
                "missing": f"{source_id} was unreachable this run",
            }
        ],
        "sources": [
            {
                "id": source_id,
                "title": title,
                "url": url,
                "role": "independent",
                "read_this_run": True,
                "reachable": False,
                "run_id": run_id,
            }
        ],
        "not_checkable": [],
        "banner": FIXTURE_BANNER,
    }
