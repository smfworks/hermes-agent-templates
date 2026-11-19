#!/usr/bin/env python3
"""Regression: separator-bearing handles refuse before any write
(hsf_38898d94 audit.py, hsf_05a2c2e3 card.py)."""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "scripts"

HOSTILE = ["../evil", "a/b", "a\\b", "..", ".", "sub/../../x"]


def test_contained_handle_unit() -> None:
    sys.path.insert(0, str(HERE))
    from store import contained_handle, strip_handle

    for h in HOSTILE:
        try:
            contained_handle(strip_handle(h))
        except ValueError:
            continue
        raise AssertionError(f"contained_handle accepted {h!r}")
    # Legit handles pass through unchanged.
    assert contained_handle(strip_handle("@legit_user")) == "legit_user"
    assert contained_handle(strip_handle("disney+roast")) == "disney+roast"


def test_card_refuses_before_write() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for h in HOSTILE:
            r = subprocess.run(
                [sys.executable, str(HERE / "card.py"), "--handle", h, "--data", str(tmp)],
                capture_output=True, text=True, timeout=60, cwd=str(HERE))
            assert r.returncode == 2, f"card.py accepted {h!r}"
            assert "profile not found" in r.stderr
        # Nothing escaped the data dir.
        assert list(tmp.iterdir()) == [], f"wrote outside: {list(tmp.iterdir())}"


def test_audit_refuses_before_write() -> None:
    with tempfile.TemporaryDirectory() as raw:
        tmp = Path(raw)
        for h in HOSTILE:
            r = subprocess.run(
                [sys.executable, str(HERE / "audit.py"), "--handle", h, "--data", str(tmp)],
                capture_output=True, text=True, timeout=60, cwd=str(HERE))
            assert r.returncode == 2, f"audit.py accepted {h!r}"
            assert "profile not found" in r.stderr
        assert list(tmp.iterdir()) == [], f"wrote outside: {list(tmp.iterdir())}"
