#!/usr/bin/env python3
"""S6 S7 S8 S5 — watch silence, drop math, and alert dedup. No model calls.

Missing scripts fail these checks. They are not skipped.
"""

from __future__ import annotations

import copy
import subprocess
import sys
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from helpers import (
    FIXTURES,
    NOW,
    PRODUCT_KEY,
    ROOT,
    TZ,
    WATCH_DETAILS,
    WATCH_LINK,
    WATCH_PARTY,
    WATCH_ROUTE,
    WATCH_SOURCE,
    assert_drop_block,
    assert_hermes_not_called,
    decimal_eq,
    fare_blocks,
    load_jobs,
    load_watch_logic,
    make_env,
    owner_stamp,
    read_csv_rows,
    read_outbox,
    read_state,
    read_trip_state,
    run_script,
    seed_data,
    seed_trip,
    watch_cmd,
    write_json,
)

KINDS = {
    "drop",
    "nonstop",
    "sellout",
    "rise",
    "none",
    "outage",
    "recovery",
    "stale",
    "inactive",
}
_UNSET = object()


def base_state(**overrides: object) -> dict:
    state = {
        "watch_yes": True,
        "checks_today": 0,
        "outage_open": False,
        "baseline": "1000.00",
        "lowest_alerted": None,
        "last_alert_fingerprint": None,
        "currency": "USD",
        "threshold_mode": "default_usd",
        "cabin": "economy",
        "room": "standard",
        "product_key": PRODUCT_KEY,
        "departure": "2026-12-10",
        "now": NOW,
        "tz": TZ,
    }
    state.update(overrides)
    return state


def base_obs(**overrides: object) -> dict:
    obs = {
        "status": "ok",
        "price": "960.00",
        "currency": "USD",
        "cabin": "economy",
        "room": "standard",
        "product_key": PRODUCT_KEY,
        "nonstop": False,
        "new_nonstop": False,
        "sellout": False,
        "sellout_verified": False,
        "fees_complete": True,
        "seen_at": NOW,
    }
    obs.update(overrides)
    return obs


def expect(evaluate, state: dict, obs: dict, *, kind: str, alert: bool, current=_UNSET, reference=_UNSET):
    snapshot = copy.deepcopy(state)
    result = evaluate(state, obs)
    assert state == snapshot, "evaluate_observation mutated state"
    assert {"alert", "kind", "fingerprint", "reference", "current"} <= set(result)
    assert result["kind"] in KINDS
    assert result["kind"] == kind, result
    assert result["alert"] is alert
    assert isinstance(result["reference"], str) and result["reference"]
    Decimal(result["reference"])
    if alert:
        assert isinstance(result["fingerprint"], str) and result["fingerprint"]
    else:
        assert result["fingerprint"] is None or isinstance(result["fingerprint"], str)
    if current is not _UNSET:
        if current is None:
            assert result["current"] is None
        else:
            assert result["current"] is not None
            assert decimal_eq(result["current"], current)
    if reference is not _UNSET:
        assert decimal_eq(result["reference"], reference)
    return result


def test_s7_drop_threshold_and_modes() -> None:
    drop_threshold, should_alert_drop, evaluate = load_watch_logic()
    assert drop_threshold(Decimal("1000"), "USD", "default_usd") == Decimal("50")
    assert drop_threshold(Decimal("949"), "USD", "default_usd") == Decimal("47.45")
    assert drop_threshold(Decimal("1000.10"), "USD", "default_usd") == Decimal("50.005")

    assert should_alert_drop(Decimal("1000"), Decimal("960"), "USD", "default_usd") is False
    assert should_alert_drop(Decimal("1000"), Decimal("950"), "USD", "default_usd") is False
    assert should_alert_drop(Decimal("1000"), Decimal("949"), "USD", "default_usd") is True
    assert should_alert_drop(Decimal("949"), Decimal("930"), "USD", "default_usd") is False
    assert should_alert_drop(Decimal("949"), Decimal("899"), "USD", "default_usd") is True
    exact_current = Decimal("1000.10") - Decimal("50.005")
    assert should_alert_drop(Decimal("1000.10"), exact_current, "USD", "default_usd") is False
    assert should_alert_drop(Decimal("1000.10"), exact_current - Decimal("0.001"), "USD", "default_usd") is True

    try:
        foreign = drop_threshold(Decimal("100"), "EUR", "default_usd")
    except Exception:
        foreign = None
    else:
        try:
            treated_as_25 = Decimal(foreign) == Decimal("25")
        except Exception:
            treated_as_25 = False
        assert treated_as_25 is False
    try:
        foreign_alert = should_alert_drop(Decimal("100"), Decimal("74"), "EUR", "default_usd")
    except Exception:
        foreign_alert = False
    assert foreign_alert is False

    assert drop_threshold(Decimal("1000"), "EUR", "fixed:40") == Decimal("40")
    assert should_alert_drop(Decimal("1000"), Decimal("960"), "USD", "fixed:40") is False
    assert should_alert_drop(Decimal("1000"), Decimal("959"), "USD", "fixed:40") is True
    assert drop_threshold(Decimal("1000"), "USD", "percent:10") == Decimal("100")
    assert should_alert_drop(Decimal("1000"), Decimal("900"), "USD", "percent:10") is False
    assert should_alert_drop(Decimal("1000"), Decimal("899.99"), "USD", "percent:10") is True
    assert drop_threshold(Decimal("1000"), "JPY", "any") == Decimal("0")
    assert should_alert_drop(Decimal("1000"), Decimal("999.99"), "USD", "any") is True
    assert should_alert_drop(Decimal("1000"), Decimal("1000"), "USD", "any") is False

    quiet = expect(evaluate, base_state(), base_obs(price="960.00"), kind="none", alert=False, reference="1000.00")
    assert quiet["alert"] is False
    first = expect(
        evaluate,
        base_state(),
        base_obs(price="949.00"),
        kind="drop",
        alert=True,
        current="949.00",
        reference="1000.00",
    )
    repeat_state = base_state(lowest_alerted="949.00", last_alert_fingerprint=first["fingerprint"])
    repeat_before = copy.deepcopy(repeat_state)
    repeat = evaluate(repeat_state, base_obs(price="949.00"))
    assert repeat_state == repeat_before
    assert repeat["alert"] is False
    assert repeat["kind"] in ("drop", "none")
    assert repeat["fingerprint"] == first["fingerprint"]
    expect(
        evaluate,
        base_state(lowest_alerted="949.00", last_alert_fingerprint=first["fingerprint"]),
        base_obs(price="930.00"),
        kind="none",
        alert=False,
        reference="949.00",
    )
    second = expect(
        evaluate,
        base_state(lowest_alerted="949.00", last_alert_fingerprint=first["fingerprint"]),
        base_obs(price="899.00"),
        kind="drop",
        alert=True,
        current="899.00",
        reference="949.00",
    )
    assert second["fingerprint"] != first["fingerprint"]
    expect(evaluate, base_state(), base_obs(price="950.00"), kind="none", alert=False, reference="1000.00")
    again = evaluate(base_state(), base_obs(price="949.00"))
    assert again["fingerprint"] == first["fingerprint"]


def test_s8_library_kinds() -> None:
    _drop_threshold, _should_alert_drop, evaluate = load_watch_logic()
    nonstop = expect(
        evaluate,
        base_state(),
        base_obs(price="990.00", nonstop=True, new_nonstop=True, product_key="BOS-LIS|nonstop"),
        kind="nonstop",
        alert=True,
        current="990.00",
    )
    expect(
        evaluate,
        base_state(last_alert_fingerprint=nonstop["fingerprint"]),
        base_obs(price="990.00", nonstop=True, new_nonstop=True, product_key="BOS-LIS|nonstop"),
        kind="nonstop",
        alert=False,
    )
    expect(
        evaluate,
        base_state(),
        base_obs(price="990.00", nonstop=True, new_nonstop=True, cabin="business", product_key="other"),
        kind="none",
        alert=False,
    )
    expect(
        evaluate,
        base_state(),
        base_obs(price="990.00", nonstop=True, new_nonstop=True, room="suite"),
        kind="none",
        alert=False,
    )
    expect(
        evaluate,
        base_state(),
        base_obs(price="900.00", currency="EUR"),
        kind="none",
        alert=False,
    )
    expect(evaluate, base_state(), base_obs(price="900.00", cabin="business"), kind="none", alert=False)
    expect(evaluate, base_state(), base_obs(price="900.00", room="suite"), kind="none", alert=False)
    expect(evaluate, base_state(), base_obs(price="900.00", fees_complete=False), kind="none", alert=False)

    sellout = expect(
        evaluate,
        base_state(),
        base_obs(price=None, sellout=True, sellout_verified=True),
        kind="sellout",
        alert=True,
        current=None,
    )
    expect(
        evaluate,
        base_state(),
        base_obs(status="empty", price=None, sellout=True, sellout_verified=True),
        kind="none",
        alert=False,
        current=None,
    )
    expect(
        evaluate,
        base_state(),
        base_obs(price=None, sellout=True, sellout_verified=True, product_key="other-flight"),
        kind="none",
        alert=False,
        current=None,
    )
    expect(
        evaluate,
        base_state(),
        base_obs(status="failed", price="0"),
        kind="none",
        alert=False,
        current=None,
    )

    inside = "2026-11-20T15:00:00Z"
    outside = "2026-10-01T15:00:00Z"
    rise = expect(
        evaluate,
        base_state(now=inside),
        base_obs(price="1100.00", seen_at=inside),
        kind="rise",
        alert=True,
        current="1100.00",
        reference="1000.00",
    )
    expect(
        evaluate,
        base_state(now=outside),
        base_obs(price="1100.00", seen_at=outside),
        kind="none",
        alert=False,
    )
    expect(
        evaluate,
        base_state(now="2026-11-19T15:00:00Z"),
        base_obs(price="1100.00"),
        kind="rise",
        alert=True,
        reference="1000.00",
    )
    expect(
        evaluate,
        base_state(now="2026-11-18T15:00:00Z"),
        base_obs(price="1100.00"),
        kind="none",
        alert=False,
    )
    expect(
        evaluate,
        base_state(now="2026-12-10T15:00:00Z"),
        base_obs(price="1100.00"),
        kind="rise",
        alert=True,
    )
    expect(
        evaluate,
        base_state(now="2026-12-11T15:00:00Z"),
        base_obs(price="1100.00"),
        kind="none",
        alert=False,
    )
    expect(
        evaluate,
        base_state(now=inside, lowest_alerted="800.00"),
        base_obs(price="1040.00"),
        kind="none",
        alert=False,
    )
    expect(
        evaluate,
        base_state(now=inside, lowest_alerted="800.00"),
        base_obs(price="1060.00"),
        kind="rise",
        alert=True,
        reference="1000.00",
        current="1060.00",
    )
    expect(
        evaluate,
        base_state(now=inside),
        base_obs(price="2000.00", currency="EUR"),
        kind="none",
        alert=False,
    )

    outage = expect(
        evaluate,
        base_state(outage_open=False),
        base_obs(status="outage", price=None),
        kind="outage",
        alert=True,
        current=None,
    )
    expect(
        evaluate,
        base_state(outage_open=True, last_alert_fingerprint=outage["fingerprint"]),
        base_obs(status="outage", price=None),
        kind="outage",
        alert=False,
        current=None,
    )
    recovery = expect(
        evaluate,
        base_state(outage_open=True),
        base_obs(status="ok", price="1000.00"),
        kind="recovery",
        alert=True,
        current="1000.00",
    )
    expect(evaluate, base_state(watch_yes=False), base_obs(price="100.00"), kind="inactive", alert=False, current=None)
    expect(evaluate, base_state(checks_today=4), base_obs(price="100.00"), kind="stale", alert=False, current=None)

    drop = evaluate(base_state(), base_obs(price="949.00"))
    fingerprints = {drop["fingerprint"], nonstop["fingerprint"], sellout["fingerprint"], rise["fingerprint"], recovery["fingerprint"]}
    assert None not in fingerprints
    assert len(fingerprints) == 5
    assert drop["fingerprint"] != nonstop["fingerprint"]


def test_s6_no_watch_yes() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        seed_trip(data, "lisbon", watch_yes=False)
        jobs = tmp / "jobs.json"
        write_json(jobs, {"jobs": [{"name": "unrelated-job", "schedule": "0 0 * * *", "timezone": "UTC"}]})
        install = run_script(
            "install_cron.py",
            ["--data", str(data), "--slug", "lisbon", "--jobs", str(jobs)],
            env,
        )
        assert install.returncode == 0, install.stderr
        loaded = load_jobs(jobs)
        assert [job["name"] for job in loaded] == ["unrelated-job"]
        result = run_script(
            "watch_prices.py",
            watch_cmd(data, "lisbon", FIXTURES / "watch_sequence.json"),
            env,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() in ("", "watch inactive")
        assert not (data / "trips" / "lisbon-prices.csv").exists()
        assert read_outbox(data) == []
        assert read_trip_state(data, "lisbon")["watch_yes"] is False
        assert read_state(data)["sentinel"] == "keep-me"
        assert_hermes_not_called(tmp)


def test_s6_travel_end() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        seed_trip(data, "lisbon", watch_yes=True, end="2026-11-01")
        result = run_script(
            "watch_prices.py",
            watch_cmd(data, "lisbon", FIXTURES / "watch_sequence.json"),
            env,
        )
        assert result.returncode == 0, result.stderr
        text = result.stdout.strip()
        assert "Fare Hawk:" not in result.stdout
        assert text in ("", "watch inactive") or "end" in text.casefold()
        assert not (data / "trips" / "lisbon-prices.csv").exists()
        assert read_outbox(data) == []


def test_s7_sequence_and_exact() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        seed_trip(data, "lisbon", watch_yes=True)
        first = run_script(
            "watch_prices.py",
            watch_cmd(data, "lisbon", FIXTURES / "watch_sequence.json"),
            env,
        )
        assert first.returncode == 0, first.stderr + first.stdout
        blocks = fare_blocks(first.stdout)
        assert len(blocks) == 2, first.stdout
        assert_drop_block(
            blocks[0],
            route=WATCH_ROUTE,
            amount="51.00",
            currency="USD",
            details=WATCH_DETAILS,
            party=WATCH_PARTY,
            reference="1000.00",
            current="949.00",
            stamp=owner_stamp("2026-11-06T15:01:00Z"),
            source=WATCH_SOURCE,
            link=WATCH_LINK,
        )
        assert_drop_block(
            blocks[1],
            route=WATCH_ROUTE,
            amount="50.00",
            currency="USD",
            details=WATCH_DETAILS,
            party=WATCH_PARTY,
            reference="949.00",
            current="899.00",
            stamp=owner_stamp("2026-11-06T15:04:00Z"),
            source=WATCH_SOURCE,
            link=WATCH_LINK,
        )
        outbox = read_outbox(data)
        assert len(outbox) == 2
        assert [row["kind"] for row in outbox] == ["drop", "drop"]
        assert decimal_eq(outbox[0]["reference"], "1000.00")
        assert decimal_eq(outbox[0]["current"], "949.00")
        assert decimal_eq(outbox[1]["reference"], "949.00")
        assert decimal_eq(outbox[1]["current"], "899.00")
        assert outbox[0]["slug"] == "lisbon"
        assert "51.00" in outbox[0]["body"]
        assert "50.00" in outbox[1]["body"]
        state = read_trip_state(data, "lisbon")
        assert decimal_eq(state["lowest_alerted"], "899.00")
        assert state["last_alert_fingerprint"] == outbox[1]["fingerprint"]
        assert state["checks_by_local_date"]["2026-11-06"] == 1
        assert state["owner_note"] == "keep-me"
        rows = read_csv_rows(data / "trips" / "lisbon-prices.csv")
        assert [row["price"] for row in rows] == ["960.00", "949.00", "949.00", "930.00", "899.00"]

        second = run_script(
            "watch_prices.py",
            watch_cmd(data, "lisbon", FIXTURES / "watch_sequence.json"),
            env,
        )
        assert second.returncode == 0, second.stderr
        assert second.stdout.strip() == ""
        assert len(read_outbox(data)) == 2
        assert len(read_csv_rows(data / "trips" / "lisbon-prices.csv")) == 10
        assert decimal_eq(read_trip_state(data, "lisbon")["lowest_alerted"], "899.00")
        assert read_state(data)["sentinel"] == "keep-me"
        assert_hermes_not_called(tmp)

    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        seed_trip(data, "exact", watch_yes=True)
        result = run_script(
            "watch_prices.py",
            watch_cmd(data, "exact", FIXTURES / "watch_exact_threshold.json"),
            env,
        )
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == ""
        assert read_outbox(data) == []
        rows = read_csv_rows(data / "trips" / "exact-prices.csv")
        assert [row["price"] for row in rows] == ["950.00"]
        assert read_trip_state(data, "exact")["lowest_alerted"] is None


def test_s8_dst_label() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        seed_trip(data, "july", watch_yes=True)
        seen = "2026-07-06T15:00:00Z"
        fixture = tmp / "july.json"
        write_json(fixture, one_watch(price="900.00", seen_at=seen))
        result = run_script("watch_prices.py", watch_cmd(data, "july", fixture, now=seen), env)
        assert result.returncode == 0, result.stderr + result.stdout
        assert "2026-07-06 11:00 ET" in result.stdout
        assert "EST" not in result.stdout
        assert_hermes_not_called(tmp)


def test_s8_fail_delivery_then_alert() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        seed_trip(data, "lisbon", watch_yes=True)
        fixture = tmp / "drop.json"
        write_json(fixture, one_watch(price="949.00", seen_at="2026-11-06T15:01:00Z"))
        failed = run_script(
            "watch_prices.py",
            watch_cmd(data, "lisbon", fixture, extra=["--fail-delivery"]),
            env,
        )
        assert failed.returncode == 0, failed.stderr
        assert "Fare Hawk:" not in failed.stdout
        assert read_outbox(data) == []
        state = read_trip_state(data, "lisbon")
        assert state["lowest_alerted"] is None
        assert state["last_alert_fingerprint"] is None
        caught = run_script("watch_prices.py", watch_cmd(data, "lisbon", fixture), env)
        assert caught.returncode == 0, caught.stderr + caught.stdout
        blocks = fare_blocks(caught.stdout)
        assert len(blocks) == 1
        assert_drop_block(
            blocks[0],
            route=WATCH_ROUTE,
            amount="51.00",
            currency="USD",
            details=WATCH_DETAILS,
            party=WATCH_PARTY,
            reference="1000.00",
            current="949.00",
            stamp=owner_stamp("2026-11-06T15:01:00Z"),
            source=WATCH_SOURCE,
            link=WATCH_LINK,
        )
        assert len(read_outbox(data)) == 1
        assert decimal_eq(read_trip_state(data, "lisbon")["lowest_alerted"], "949.00")
        quiet = run_script("watch_prices.py", watch_cmd(data, "lisbon", fixture), env)
        assert quiet.returncode == 0, quiet.stderr
        assert quiet.stdout.strip() == ""
        assert len(read_outbox(data)) == 1


def test_s8_nonstop_sellout_rise_outage() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)

        seed_trip(data, "nonstop", watch_yes=True)
        first = run_script("watch_prices.py", watch_cmd(data, "nonstop", FIXTURES / "watch_nonstop.json"), env)
        assert first.returncode == 0, first.stderr + first.stdout
        assert "nonstop" in first.stdout.casefold()
        nonstop_box = read_outbox(data)
        assert len(nonstop_box) == 1
        assert nonstop_box[0]["kind"] == "nonstop"
        assert nonstop_box[0]["slug"] == "nonstop"
        second = run_script("watch_prices.py", watch_cmd(data, "nonstop", FIXTURES / "watch_nonstop.json"), env)
        assert second.stdout.strip() == ""
        assert len(read_outbox(data)) == 1

        seed_trip(data, "sell", watch_yes=True)
        sold = run_script("watch_prices.py", watch_cmd(data, "sell", FIXTURES / "watch_sellout.json"), env)
        assert sold.returncode == 0, sold.stderr + sold.stdout
        folded = sold.stdout.casefold()
        assert "sellout" in folded or "sold out" in folded
        assert "availability not confirmed" in folded
        sell_box = [row for row in read_outbox(data) if row["slug"] == "sell"]
        assert len(sell_box) == 1
        assert sell_box[0]["kind"] == "sellout"
        assert sell_box[0]["current"] is None
        again = run_script("watch_prices.py", watch_cmd(data, "sell", FIXTURES / "watch_sellout.json"), env)
        assert "sellout" not in again.stdout.casefold()
        assert "sold out" not in again.stdout.casefold()
        assert len([row for row in read_outbox(data) if row["slug"] == "sell"]) == 1
        sell_rows = read_csv_rows(data / "trips" / "sell-prices.csv")
        assert [row["status"] for row in sell_rows] == ["ok", "empty"]
        assert all(row["price"] == "" for row in sell_rows)

        seed_trip(data, "rise", watch_yes=True)
        risen = run_script(
            "watch_prices.py",
            watch_cmd(data, "rise", FIXTURES / "watch_rise.json", now="2026-11-20T15:00:00Z"),
            env,
        )
        assert risen.returncode == 0, risen.stderr + risen.stdout
        assert "rise" in risen.stdout.casefold()
        rise_box = [row for row in read_outbox(data) if row["slug"] == "rise"]
        assert len(rise_box) == 1 and rise_box[0]["kind"] == "rise"
        repeat = run_script(
            "watch_prices.py",
            watch_cmd(data, "rise", FIXTURES / "watch_rise.json", now="2026-11-20T15:00:00Z"),
            env,
        )
        assert repeat.stdout.strip() == ""
        assert len([row for row in read_outbox(data) if row["slug"] == "rise"]) == 1

        early_root = tmp / "early"
        early_root.mkdir()
        early_data = seed_data(early_root)
        seed_trip(early_data, "rise", watch_yes=True)
        early = run_script(
            "watch_prices.py",
            watch_cmd(early_data, "rise", FIXTURES / "watch_rise.json", now="2026-10-01T15:00:00Z"),
            env,
        )
        assert early.returncode == 0, early.stderr
        assert early.stdout.strip() == ""
        assert read_outbox(early_data) == []
        assert read_csv_rows(early_data / "trips" / "rise-prices.csv")[0]["price"] == "1100.00"

        seed_trip(data, "out", watch_yes=True)
        outage = run_script("watch_prices.py", watch_cmd(data, "out", FIXTURES / "watch_outage.json"), env)
        assert outage.returncode == 0, outage.stderr + outage.stdout
        assert outage.stdout.count("degraded-watch") == 1
        assert outage.stdout.count("watch recovered") == 1
        out_rows = read_csv_rows(data / "trips" / "out-prices.csv")
        assert [row["price"] for row in out_rows] == ["", "", "1000.00", "1000.00"]
        assert [row["status"] for row in out_rows] == ["outage", "outage", "ok", "ok"]
        assert all(row["price"] != "0" for row in out_rows)
        out_box = [row for row in read_outbox(data) if row["slug"] == "out"]
        assert out_box == []
        assert_hermes_not_called(tmp)


def test_s5_concurrent_csv() -> None:
    script = ROOT / "scripts" / "watch_prices.py"
    assert script.is_file(), f"missing {script}"
    for _ in range(5):
        with TemporaryDirectory() as raw:
            tmp = Path(raw)
            data = seed_data(tmp)
            env = make_env(tmp)
            seed_trip(data, "shared", watch_yes=True)
            left = tmp / "left.json"
            right = tmp / "right.json"
            write_json(left, one_watch(price="960.10", seen_at=NOW, pause_ms=400, notes="left"))
            write_json(right, one_watch(price="970.20", seen_at="2026-11-06T15:05:00Z", pause_ms=400, notes="right"))
            commands = [
                watch_cmd(data, "shared", left),
                watch_cmd(data, "shared", right),
            ]
            procs = [
                subprocess.Popen(
                    [sys.executable, str(script), *args],
                    text=True,
                    encoding="utf-8",
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    stdin=subprocess.DEVNULL,
                    cwd=str(ROOT),
                    env=env,
                )
                for args in commands
            ]
            for proc in procs:
                stdout, stderr = proc.communicate(timeout=20)
                assert proc.returncode == 0, stderr + stdout
            rows = read_csv_rows(data / "trips" / "shared-prices.csv")
            assert sorted(row["price"] for row in rows) == ["960.10", "970.20"]
            assert_hermes_not_called(tmp)


def one_watch(*, price: str, seen_at: str, pause_ms: int | None = None, notes: str = "") -> dict:
    obs = {
        "status": "ok",
        "currency": "USD",
        "cabin": "economy",
        "room": "standard",
        "product_key": PRODUCT_KEY,
        "nonstop": False,
        "new_nonstop": False,
        "sellout": False,
        "sellout_verified": False,
        "fees_complete": True,
        "notes": notes,
        "price": price,
        "seen_at": seen_at,
    }
    if pause_ms is not None:
        obs["pause_ms"] = pause_ms
    return {
        "route": WATCH_ROUTE,
        "party": WATCH_PARTY,
        "details": WATCH_DETAILS,
        "source": WATCH_SOURCE,
        "link": WATCH_LINK,
        "currency": "USD",
        "baseline": "1000.00",
        "cabin": "economy",
        "room": "standard",
        "product_key": PRODUCT_KEY,
        "departure": "2026-12-10",
        "observations": [obs],
    }


def main() -> None:
    test_s7_drop_threshold_and_modes()
    test_s8_library_kinds()
    test_s6_no_watch_yes()
    test_s6_travel_end()
    test_s7_sequence_and_exact()
    test_s8_dst_label()
    test_s8_fail_delivery_then_alert()
    test_s8_nonstop_sellout_rise_outage()
    test_s5_concurrent_csv()
    print("test_watch.py PASS")


if __name__ == "__main__":
    main()
