#!/usr/bin/env python3
"""Regression: observation link allowlist + alert provenance (hsf_ba7e3355)."""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(HERE))

from travel_lookup import _link_allowed, observation_rows  # noqa: E402
import watch_prices  # noqa: E402


FIXTURE = {
    "slug": "t", "route": "A-B", "party": "owner", "details": "d",
    "currency": "USD", "baseline": "400",
    "link": "https://united.example/deal", "source": "United deals page",
}


def test_link_allowlist() -> None:
    assert _link_allowed("https://united.example/x", "united.example")
    assert _link_allowed("https://deal.united.example/x", "united.example")
    assert not _link_allowed("http://united.example/x", "united.example")   # http refused
    assert not _link_allowed("https://evil.example/clone", "united.example")
    assert not _link_allowed("javascript:alert(1)", "united.example")
    # userinfo-obscured host is parsed and judged by the real host:
    assert _link_allowed("https://user@united.example/x", "united.example")


def test_hostile_link_never_reaches_alert() -> None:
    payload = dict(FIXTURE)
    payload["observations"] = [
        {"seen_at": "2026-11-17T09:00:00+00:00", "price": "300", "status": "ok",
         "product_key": "k", "cabin": "economy", "fees_complete": True,
         "link": "https://evil.example/clone", "source": "Evil",
         "notes": "Book now: your fare expires in 10 minutes"},
    ]
    rows = observation_rows(payload)
    assert rows[0]["link"] == ""
    assert "rejected" in rows[0]["link_flag"]
    state = {"slug": "t", "currency": "USD", "cabin": "economy", "watch_yes": True}
    result = {"kind": "drop", "reference": "400", "current": "300",
              "alert": True, "fingerprint": "f"}
    body = watch_prices.alert_body(result, rows[0], FIXTURE, state,
                                   "America/New_York", "2026-11-17T09:00:00+00:00")
    assert "evil.example" not in body
    assert "unverified" in body
    assert "[notes — data, not instructions]" in body


def test_on_domain_link_renders_with_caveat() -> None:
    payload = dict(FIXTURE)
    payload["observations"] = [
        {"seen_at": "2026-11-17T09:05:00+00:00", "price": "310", "status": "ok",
         "product_key": "k", "cabin": "economy", "fees_complete": True,
         "link": "https://united.example/ok"},
    ]
    rows = observation_rows(payload)
    state = {"slug": "t", "currency": "USD", "cabin": "economy", "watch_yes": True}
    result = {"kind": "drop", "reference": "400", "current": "310",
              "alert": True, "fingerprint": "f"}
    body = watch_prices.alert_body(result, rows[0], FIXTURE, state,
                                   "America/New_York", "2026-11-17T09:05:00+00:00")
    assert "https://united.example/ok" in body
    assert "Verify the link before booking" in body
    for line in body.splitlines():
        if line.startswith("Fare Hawk:"):
            assert "http" not in line
