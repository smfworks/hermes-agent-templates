#!/usr/bin/env python3
"""S5 — sanitized share card, PNG bytes, and slug checks. No model calls.

Missing scripts fail these checks. They are not skipped.
"""

from __future__ import annotations

import html
from pathlib import Path
from tempfile import TemporaryDirectory

from helpers import (
    FIXTURES,
    assert_hermes_not_called,
    assert_plan_report,
    make_env,
    plan_cmd,
    read_json,
    run_script,
    seed_data,
)

VENUE = """A & B <script>alert(1)</script> "q" 'z'"""
PLANTED = """Destination: Lisbon
Dates: Thursday 2026-12-10 to Thursday 2026-12-17
Party: 2 adults, 0 children. Cabin: economy. Bags: 1. Rooms: 1.
Lodging area: Alfama
Watch: off
Booking status: planning
Traveler: Alex Traveler
Confirmation: ABC123
Total: $480

## Itinerary
### Thursday 2026-12-10 - Alfama - light
- Fish & chips
Meal: soup
Hours: 10:00-18:00

## Flights
- Cheapest sensible: TP-CHEAP - 780.00 USD
Hotel secret rate 900.00 USD
"""


def snapshot(root: Path) -> set[str]:
    return {str(path.relative_to(root)) for path in root.rglob("*") if path.is_file()}


def test_s5_sanitized_card_and_png() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        trips = data / "trips"
        trips.mkdir()
        working = trips / "lisbon.md"
        working.write_text(PLANTED, encoding="utf-8")
        (trips / "lisbon.html").write_text("<p>Total: $480</p><p>Alex Traveler</p>", encoding="utf-8")
        result = run_script("card.py", ["--data", str(data), "--slug", "lisbon", "--png"], env)
        assert result.returncode == 0, result.stderr
        card_md = (trips / "lisbon-card.md").read_text(encoding="utf-8")
        card_html = (trips / "lisbon-card.html").read_text(encoding="utf-8")
        for text in (card_md, card_html):
            assert "Destination: Lisbon" in text or "Destination: Lisbon" in html.unescape(text)
            assert "Alfama" in text
            assert "2 adults" in text
            assert "Watch: off" in text or "Watch: off" in html.unescape(text)
            assert "Fish" in text
            assert "Alex Traveler" not in text
            assert "ABC123" not in text
            assert "$" not in text
            assert "480" not in text
            assert "780.00" not in text
            assert "900.00" not in text
            assert "Cheapest sensible" not in text
            assert "Booking status" not in text
            assert "Traveler:" not in text
            assert "Confirmation:" not in text
        assert "Fish &amp; chips" in card_html
        folded = card_html.casefold()
        assert "<script" not in folded
        assert "iframe" not in folded
        assert "onerror" not in folded
        still = working.read_text(encoding="utf-8")
        assert "$480" in still
        assert "Alex Traveler" in still
        assert "780.00" in still
        png = (trips / "lisbon-card.png").read_bytes()
        assert png.startswith(b"\x89PNG")
        assert b"Alex Traveler" not in png
        assert b"ABC123" not in png
        assert b"$480" not in png
        assert_hermes_not_called(tmp)


def test_s5_html_escapes_injected_venue() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        fixture = read_json(FIXTURES / "inject_listing.json")
        planned = run_script(
            "plan.py",
            plan_cmd(
                data,
                "inject",
                FIXTURES / "inject_listing.json",
                [
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
                    "0",
                    "--home",
                    "BOS",
                ],
            ),
            env,
        )
        assert planned.returncode == 0, planned.stderr + planned.stdout
        assert_plan_report(
            data,
            "inject",
            fixture,
            adults=2,
            children=[],
            bags=0,
            cabin="economy",
            rooms=1,
            origin="BOS",
            destination="Lisbon",
            start="2026-12-10",
            end="2026-12-17",
            watch_on=False,
        )
        card = run_script("card.py", ["--data", str(data), "--slug", "inject"], env)
        assert card.returncode == 0, card.stderr
        card_html = (data / "trips" / "inject-card.html").read_text(encoding="utf-8")
        card_md = (data / "trips" / "inject-card.md").read_text(encoding="utf-8")
        assert html.escape(VENUE) in card_html
        assert "<script" not in card_html.casefold()
        assert "iframe" not in card_html.casefold()
        assert "onerror" not in card_html.casefold()
        assert VENUE in card_md
        assert "Alex Traveler" not in card_html
        assert "$" not in card_md
        assert_hermes_not_called(tmp)


def test_s5_slug_rejected() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        outside = tmp / "outside-canary.txt"
        outside.write_text("safe", encoding="utf-8")
        fixture = FIXTURES / "trip_empty.json"
        flags = [
            "--dest",
            "Lisbon",
            "--start",
            "2026-12-10",
            "--end",
            "2026-12-17",
            "--adults",
            "2",
        ]
        rejected = ["../outside", "foo/bar", "Lisbon", "", "a" * 65, ".."]
        for slug in rejected:
            before = snapshot(tmp)
            plan = run_script("plan.py", plan_cmd(data, slug, fixture, flags), env)
            card = run_script("card.py", ["--data", str(data), "--slug", slug], env)
            confirm = run_script(
                "confirm.py",
                ["--data", str(data), "--slug", slug, "--text", "note"],
                env,
            )
            for result in (plan, card, confirm):
                assert result.returncode == 2, (slug, result.returncode, result.stderr)
            assert snapshot(tmp) == before
            assert outside.read_text(encoding="utf-8") == "safe"
            assert not (tmp / "outside").exists()

        try:
            run_script("card.py", ["--data", str(data), "--slug", "bad\x00slug"], env)
        except ValueError as exc:
            assert "null" in str(exc).casefold()
        else:
            raise AssertionError("null slug was accepted by the process spawn")
        assert outside.read_text(encoding="utf-8") == "safe"

        slug = "a" * 64
        trips = data / "trips"
        trips.mkdir()
        (trips / f"{slug}.md").write_text(
            "Destination: Lisbon\nDates: Thursday 2026-12-10 to Thursday 2026-12-17\n"
            "Party: 1 adult, 0 children. Cabin: economy. Bags: 0. Rooms: 1.\n"
            "Lodging area: Alfama\nWatch: off\n\n## Itinerary\n- walk\n## Flights\nTotal: $9\n",
            encoding="utf-8",
        )
        accepted = run_script("card.py", ["--data", str(data), "--slug", slug], env)
        assert accepted.returncode == 0, accepted.stderr
        card_md = (trips / f"{slug}-card.md").read_text(encoding="utf-8")
        assert card_md.startswith("Destination: Lisbon") or "Destination: Lisbon" in card_md
        assert "$" not in card_md
        assert (trips / f"{slug}-card.md").resolve().is_relative_to(data.resolve())
        assert_hermes_not_called(tmp)


def main() -> None:
    test_s5_sanitized_card_and_png()
    test_s5_html_escapes_injected_venue()
    test_s5_slug_rejected()
    print("test_card.py PASS")


if __name__ == "__main__":
    main()
