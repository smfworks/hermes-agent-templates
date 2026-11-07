#!/usr/bin/env python3
"""S4 — Decimal totals, all-traveler arithmetic, and CSV quoting."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from helpers import (
    FIXTURES,
    PRODUCT_KEY,
    WATCH_DETAILS,
    WATCH_LINK,
    WATCH_PARTY,
    WATCH_ROUTE,
    WATCH_SOURCE,
    assert_hermes_not_called,
    assert_plan_report,
    make_env,
    read_csv_rows,
    read_json,
    read_outbox,
    read_trip_state,
    run_script,
    seed_data,
    seed_trip,
    watch_cmd,
    write_json,
)


def lisbon_flags(bags: str = "1") -> list[str]:
    return [
        "--dest",
        "Lisbon",
        "--start",
        "2026-12-10",
        "--end",
        "2026-12-17",
        "--adults",
        "2",
        "--cabin",
        "economy",
        "--bags",
        bags,
        "--home",
        "BOS",
    ]


def test_s4_decimal_totals() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        fixture = read_json(FIXTURES / "trip_incomplete_fees.json")
        result = run_script(
            "plan.py",
            [
                "--data",
                str(data),
                "--slug",
                "fees",
                "--backend",
                "fixtures",
                "--fixtures",
                str(FIXTURES / "trip_incomplete_fees.json"),
                "--now",
                "2026-11-06T15:00:00Z",
                "--tz",
                "America/New_York",
                *lisbon_flags(),
            ],
            env,
        )
        assert result.returncode == 0, result.stderr + result.stdout
        assert_plan_report(
            data,
            "fees",
            fixture,
            adults=2,
            children=[],
            bags=1,
            cabin="economy",
            rooms=1,
            origin="BOS",
            destination="Lisbon",
            start="2026-12-10",
            end="2026-12-17",
            watch_on=False,
        )
        report = (data / "trips" / "fees.md").read_text(encoding="utf-8")
        html = (data / "trips" / "fees.html").read_text(encoding="utf-8")
        for text in (report, html):
            assert "703.38" in text
            assert "700.70" in text
            assert "703.37" not in text
            assert "700.699999" not in text
            assert "555.80" in text
            assert "500.80" in text
            assert "500.799999" not in text
            assert "2520.00" in text
            assert "basic economy" in text
            assert "bag fee 35.00" in text
            assert "resort fee 15.00 per night" in text
            assert "cancellation deadline 2026-12-01" in text
            assert "unknown" in text.casefold()
            assert "Incomplete: H-UNKNOWN - nightly stay 70.00 - total unknown" in text
            for role in ("Cheapest sensible", "Best value", "Most comfortable"):
                assert f"{role}: H-UNKNOWN" not in text
        assert_hermes_not_called(tmp)


def test_s4_csv_quote_and_unknown_price() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        seed_trip(data, "quote", watch_yes=True)
        notes = 'He said "hi", there\nnext'
        fixture = tmp / "quote.json"
        write_json(
            fixture,
            {
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
                "observations": [
                    {
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
                        "price": "960.10",
                        "seen_at": "2026-11-06T15:00:00Z",
                    },
                    {
                        "status": "failed",
                        "currency": "USD",
                        "cabin": "economy",
                        "room": "standard",
                        "product_key": PRODUCT_KEY,
                        "nonstop": False,
                        "new_nonstop": False,
                        "sellout": False,
                        "sellout_verified": False,
                        "fees_complete": True,
                        "notes": "lookup failed",
                        "price": "0",
                        "seen_at": "2026-11-06T15:01:00Z",
                    },
                ],
            },
        )
        result = run_script("watch_prices.py", watch_cmd(data, "quote", fixture), env)
        assert result.returncode == 0, result.stderr + result.stdout
        assert "Fare Hawk:" not in result.stdout
        assert read_outbox(data) == []
        rows = read_csv_rows(data / "trips" / "quote-prices.csv")
        assert len(rows) == 2
        assert rows[0]["status"] == "ok"
        assert rows[0]["price"] == "960.10"
        assert rows[0]["notes"] == notes
        assert rows[0]["currency"] == "USD"
        assert rows[1]["status"] == "failed"
        assert rows[1]["price"] == ""
        assert rows[1]["price"] != "0"
        assert rows[1]["notes"] == "lookup failed"
        raw = (data / "trips" / "quote-prices.csv").read_text(encoding="utf-8")
        assert "960.10" in raw
        assert_hermes_not_called(tmp)
        state = read_trip_state(data, "quote")
        assert state["owner_note"] == "keep-me"
        assert state["lowest_alerted"] is None


def main() -> None:
    test_s4_decimal_totals()
    test_s4_csv_quote_and_unknown_price()
    print("test_money.py PASS")


if __name__ == "__main__":
    main()
