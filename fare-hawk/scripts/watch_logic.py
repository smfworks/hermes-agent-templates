#!/usr/bin/env python3
"""Pure fare comparisons. Does not read the network or mutate caller state."""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

# Fingerprint is kind + product + current price. A repeat of 949 must still
# match the first alert after lowest_alerted moves off the original baseline.


def drop_threshold(reference: Decimal, currency: str, mode: str) -> Decimal:
    reference = Decimal(reference)
    mode = mode or "default_usd"
    if mode == "default_usd":
        if currency != "USD":
            raise ValueError("default_usd applies to USD only")
        return max(Decimal("25"), Decimal("0.05") * reference)
    if mode == "any":
        return Decimal("0")
    if mode.startswith("fixed:"):
        return Decimal(mode.split(":", 1)[1])
    if mode.startswith("percent:"):
        percent = Decimal(mode.split(":", 1)[1])
        return reference * percent / Decimal("100")
    raise ValueError(f"unknown threshold mode: {mode}")


def should_alert_drop(reference, current, currency: str, mode: str) -> bool:
    reference = Decimal(reference)
    current = Decimal(current)
    try:
        threshold = drop_threshold(reference, currency, mode)
    except Exception:
        return False
    return (reference - current) > threshold


def _money(value: Decimal) -> str:
    return format(value.quantize(Decimal("0.01")), "f")


def _decimal(value, fallback: str = "0") -> Decimal:
    if value is None or value == "":
        return Decimal(fallback)
    return Decimal(str(value))


def _price(value):
    if value is None or value == "":
        return None
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _civil(iso: str, tz: str) -> date:
    instant = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
    return instant.astimezone(ZoneInfo(tz)).date()


def _like(state: dict, obs: dict) -> bool:
    if not obs.get("fees_complete"):
        return False
    if (obs.get("currency") or "") != (state.get("currency") or ""):
        return False
    if (obs.get("cabin") or "") != (state.get("cabin") or ""):
        return False
    state_room = state.get("room")
    obs_room = obs.get("room")
    if state_room and obs_room and state_room != obs_room:
        return False
    return True


def _same_product(state: dict, obs: dict) -> bool:
    return obs.get("product_key") == state.get("product_key")


def _fingerprint(kind: str, obs: dict, state: dict, price: Decimal | None) -> str:
    product = obs.get("product_key") or state.get("product_key") or ""
    price_bit = _money(price) if price is not None else ""
    return f"{kind}|{product}|{price_bit}"


def _result(kind: str, alert: bool, fingerprint, reference: str, current, last) -> dict:
    if alert and fingerprint and fingerprint == last:
        alert = False
    return {
        "alert": bool(alert),
        "kind": kind,
        "fingerprint": fingerprint,
        "reference": reference,
        "current": current,
    }


def evaluate_observation(state: dict, obs: dict) -> dict:
    baseline = _decimal(state.get("baseline"), "0")
    lowest_raw = state.get("lowest_alerted")
    drop_ref = _decimal(lowest_raw, "0") if lowest_raw not in (None, "") else baseline
    reference_drop = _money(drop_ref)
    reference_base = _money(baseline)
    last = state.get("last_alert_fingerprint")
    currency = state.get("currency") or ""
    mode = state.get("threshold_mode") or "default_usd"

    if state.get("watch_yes") is not True:
        return _result("inactive", False, None, reference_drop, None, last)
    try:
        checks_today = int(state.get("checks_today") or 0)
    except (TypeError, ValueError):
        checks_today = 0
    if checks_today >= 4:
        return _result("stale", False, None, reference_drop, None, last)

    status = obs.get("status") or "ok"
    if status == "outage":
        fingerprint = _fingerprint("outage", obs, state, None)
        if state.get("outage_open"):
            return _result("outage", False, None, reference_drop, None, last)
        return _result("outage", True, fingerprint, reference_drop, None, last)
    if status == "ok" and state.get("outage_open"):
        price = _price(obs.get("price"))
        current = _money(price) if price is not None else None
        fingerprint = _fingerprint("recovery", obs, state, price)
        return _result("recovery", True, fingerprint, reference_drop, current, last)
    if status in ("failed", "empty"):
        return _result("none", False, None, reference_drop, None, last)

    price = _price(obs.get("price"))
    current = _money(price) if price is not None else None
    comparable = _like(state, obs) and _same_product(state, obs)

    if obs.get("sellout") and obs.get("sellout_verified") and _same_product(state, obs):
        fingerprint = _fingerprint("sellout", obs, state, None)
        return _result("sellout", True, fingerprint, reference_drop, None, last)

    if (
        obs.get("new_nonstop")
        and obs.get("nonstop")
        and _like(state, obs)
        and price is not None
        and price < drop_ref
    ):
        fingerprint = _fingerprint("nonstop", obs, state, price)
        return _result("nonstop", True, fingerprint, reference_drop, current, last)

    if comparable and price is not None and _within_rise_window(state):
        try:
            rise = (price - baseline) > drop_threshold(baseline, currency, mode)
        except Exception:
            rise = False
        if rise:
            fingerprint = _fingerprint("rise", obs, state, price)
            return _result("rise", True, fingerprint, reference_base, current, last)

    drop_fp = _fingerprint("drop", obs, state, price) if comparable and price is not None else None
    if comparable and price is not None and should_alert_drop(drop_ref, price, currency, mode):
        return _result("drop", True, drop_fp, reference_drop, current, last)
    if drop_fp and drop_fp == last:
        return _result("none", False, drop_fp, reference_drop, current, last)
    return _result("none", False, None, reference_drop, current, last)


def _within_rise_window(state: dict) -> bool:
    now = state.get("now")
    departure = state.get("departure")
    tz = state.get("tz") or "America/New_York"
    if not now or not departure:
        return False
    try:
        today = _civil(str(now), str(tz))
        leave = date.fromisoformat(str(departure))
    except (TypeError, ValueError):
        return False
    delta = (leave - today).days
    return 0 <= delta <= 21
