#!/usr/bin/env python3
"""One price check. Fixtures backend only. No network and no hermes."""

from __future__ import annotations

import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

from store import (
    FileLock,
    atomic_write,
    civil_date,
    load_json,
    money,
    owner_stamp,
    read_csv_rows,
    read_jsonl,
    require_slug,
    trip_path,
    write_csv_rows,
    write_jsonl,
)
from travel_lookup import load_fixture, observation_rows
from watch_logic import evaluate_observation

# Outage and recovery are episode notices. Only drop, nonstop, sellout, and rise
# go to the outbox, and only after that write succeeds.


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check one fare watch.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--backend", default="fixtures")
    parser.add_argument("--fixtures")
    parser.add_argument("--now", default="2026-11-06T15:00:00Z")
    parser.add_argument("--tz", default="America/New_York")
    parser.add_argument("--fail-delivery", action="store_true")
    return parser.parse_args(argv)


def inactive_line(state: dict, local_day: str) -> str | None:
    if state.get("watch_yes") is not True:
        return "watch inactive"
    if state.get("paused") is True:
        return "watch inactive"
    end = state.get("end")
    if end and str(end) < local_day:
        return "watch inactive: travel end"
    return None


def display(fixture: dict, state: dict, key: str) -> str:
    if fixture.get(key) not in (None, ""):
        return str(fixture[key])
    if state.get(key) not in (None, ""):
        return str(state[key])
    return ""


def _keep_row(row: dict[str, str], existing: list[dict[str, str]]) -> bool:
    if row.get("price"):
        return True
    for old in existing:
        if (
            old.get("seen_at") == row.get("seen_at")
            and old.get("status") == row.get("status")
            and old.get("product_key") == row.get("product_key")
            and old.get("notes") == row.get("notes")
            and not old.get("price")
        ):
            return False
    return True


def csv_row(obs: dict) -> dict[str, str]:
    status = str(obs.get("status") or "ok")
    price = ""
    if status == "ok" and obs.get("price") not in (None, ""):
        price = money(Decimal(str(obs["price"])))
    notes = obs.get("notes")
    return {
        "seen_at": str(obs.get("seen_at") or ""),
        "status": status,
        "price": price,
        "currency": str(obs.get("currency") or ""),
        "source": str(obs.get("source") or ""),
        "link": str(obs.get("link") or ""),
        "notes": "" if notes is None else str(notes),
        "product_key": str(obs.get("product_key") or ""),
    }


def alert_body(result: dict, obs: dict, fixture: dict, state: dict, tz: str, now: str) -> str:
    route = display(fixture, state, "route")
    details = display(fixture, state, "details")
    party = display(fixture, state, "party")
    source = str(obs.get("source") or display(fixture, state, "source"))
    link = str(obs.get("link") or display(fixture, state, "link"))
    currency = str(obs.get("currency") or state.get("currency") or fixture.get("currency") or "")
    stamp = owner_stamp(str(obs.get("seen_at") or now), tz)
    kind = result["kind"]
    if kind == "drop":
        amount = money(Decimal(result["reference"]) - Decimal(result["current"]))
        return "\n".join(
            [
                f"Fare Hawk: {route} dropped {amount} {currency}",
                f"{details}, {party}: {result['reference']} → {result['current']}",
                f"Seen {stamp} on {source} · lowest alerted since watch began",
                f"{link} · You book; total may change at checkout.",
            ]
        )
    if kind == "nonstop":
        return "\n".join(
            [
                f"Fare Hawk: {route} new nonstop {result['current']} {currency}",
                f"{details}, {party}: nonstop",
                f"Seen {stamp} on {source}",
                f"{link} · You book; total may change at checkout.",
            ]
        )
    if kind == "sellout":
        return "\n".join(
            [
                f"Fare Hawk: {route} sellout",
                f"{details}, {party}: sold out",
                f"Seen {stamp} on {source}",
                f"{link} · You book; total may change at checkout.",
            ]
        )
    return "\n".join(
        [
            f"Fare Hawk: {route} rise {result['current']} {currency}",
            f"{details}, {party}: rise versus baseline {result['reference']}",
            f"Seen {stamp} on {source}",
            f"{link} · You book; total may change at checkout.",
        ]
    )


def apply_observations(state: dict, fixture: dict, observations: list[dict], now: str, tz: str, count: int, fail: bool):
    logic = {
        "watch_yes": state.get("watch_yes") is True,
        "checks_today": count,
        "outage_open": bool(state.get("outage_open")),
        "baseline": state.get("baseline") if state.get("baseline") not in (None, "") else fixture.get("baseline"),
        "lowest_alerted": state.get("lowest_alerted"),
        "last_alert_fingerprint": state.get("last_alert_fingerprint"),
        "currency": state.get("currency") or fixture.get("currency") or "USD",
        "threshold_mode": state.get("threshold_mode") or "default_usd",
        "cabin": state.get("cabin") or fixture.get("cabin"),
        "room": state.get("room") or fixture.get("room"),
        "product_key": state.get("product_key") or fixture.get("product_key"),
        "departure": state.get("departure") or fixture.get("departure"),
        "now": now,
        "tz": tz,
    }
    messages: list[str] = []
    alerts: list[dict] = []
    rows: list[dict[str, str]] = []
    for obs in observations:
        result = evaluate_observation(logic, obs)
        rows.append(csv_row(obs))
        status = obs.get("status") or "ok"
        if status == "empty":
            messages.append("availability not confirmed")
        if result["kind"] == "outage" and result["alert"]:
            messages.append("degraded-watch")
            logic["outage_open"] = True
            continue
        if result["kind"] == "recovery" and result["alert"]:
            messages.append("watch recovered")
            logic["outage_open"] = False
            continue
        if result["alert"] and result["kind"] in {"drop", "nonstop", "sellout", "rise"}:
            body = alert_body(result, obs, fixture, state, tz, now)
            if fail:
                messages.append("retry")
            else:
                messages.append(body)
                alerts.append(
                    {
                        "slug": state.get("slug"),
                        "kind": result["kind"],
                        "fingerprint": result["fingerprint"],
                        "reference": result["reference"],
                        "current": result["current"],
                        "body": body,
                    }
                )
                logic["last_alert_fingerprint"] = result["fingerprint"]
                if result["kind"] == "drop" and result["current"] is not None:
                    logic["lowest_alerted"] = result["current"]
    return rows, alerts, messages, logic


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        slug = require_slug(args.slug)
    except SystemExit:
        print("invalid slug", file=sys.stderr)
        return 2
    if args.backend != "fixtures":
        print("Live lookup is unavailable. Named limitation: fixtures backend only.")
        return 2
    if not args.fixtures:
        print("A fixtures file is required.", file=sys.stderr)
        return 2
    data = Path(args.data)
    state_path = trip_path(data, slug, f"{slug}-state.json")
    csv_path = trip_path(data, slug, f"{slug}-prices.csv")
    local_day = civil_date(args.now, args.tz).isoformat()
    preview = load_json(state_path)
    reason = inactive_line(preview, local_day)
    if reason:
        print(reason)
        return 0
    fixture = load_fixture(Path(args.fixtures))
    observations = observation_rows(fixture)
    outbox_path = data / "outbox.jsonl"
    messages: list[str] = []
    with FileLock(csv_path):
        state = load_json(state_path)
        state.setdefault("slug", slug)
        reason = inactive_line(state, local_day)
        if reason:
            print(reason)
            return 0
        checks = dict(state.get("checks_by_local_date") or {})
        count = int(checks.get(local_day) or 0)
        if count >= 4:
            print("stale")
            return 0
        existing = read_csv_rows(csv_path)
        new_rows, alerts, messages, logic = apply_observations(
            state,
            fixture,
            observations,
            args.now,
            args.tz,
            count,
            args.fail_delivery,
        )
        # Blank-price replays stay one row per seen_at. Priced replays still append.
        fresh_rows = [row for row in new_rows if _keep_row(row, existing)]
        for obs in observations:
            pause = obs.get("pause_ms")
            if pause:
                time.sleep(int(pause) / 1000.0)
        write_csv_rows(csv_path, existing + fresh_rows)
        if alerts and not args.fail_delivery:
            with FileLock(outbox_path):
                current = read_jsonl(outbox_path)
                current.extend(alerts)
                write_jsonl(outbox_path, current)
            state["last_alert_fingerprint"] = logic.get("last_alert_fingerprint")
            state["lowest_alerted"] = logic.get("lowest_alerted")
        state["outage_open"] = bool(logic.get("outage_open"))
        checks[local_day] = count + 1
        state["checks_by_local_date"] = checks
        atomic_write(state_path, json.dumps(state, ensure_ascii=False, indent=2) + "\n")
    if messages:
        print("\n".join(messages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
