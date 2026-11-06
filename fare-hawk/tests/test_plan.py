#!/usr/bin/env python3
"""S2 S3 S4 S5 — itinerary, constraints, fees, and private confirmations."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from helpers import (
    ASSUMPTION,
    FIXTURES,
    NOW,
    TZ,
    assert_hermes_not_called,
    assert_plan_report,
    dates_fact,
    make_env,
    owner_stamp,
    plan_cmd,
    read_json,
    read_state,
    resolve_relative_dates,
    run_script,
    seed_data,
    weekday_name,
)


def plan(data, env, slug, fixture, extra=None):
    result = run_script("plan.py", plan_cmd(data, slug, fixture, extra), env)
    assert result.returncode == 0, result.stderr + result.stdout
    assert f"trips/{slug}.md" in result.stdout.replace("\\", "/")
    return result


def lisbon_flags(bags: str = "1", extra: list[str] | None = None) -> list[str]:
    flags = [
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
    if extra:
        flags.extend(extra)
    return flags


def test_s2_s3_lisbon() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        fixture = read_json(FIXTURES / "trip_lisbon.json")
        plan(data, env, "lisbon", FIXTURES / "trip_lisbon.json", lisbon_flags())
        assert_plan_report(
            data,
            "lisbon",
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
        report = (data / "trips" / "lisbon.md").read_text(encoding="utf-8")
        assert weekday_name("2026-12-10") == "Thursday"
        assert weekday_name("2026-12-17") == "Thursday"
        assert dates_fact("2026-12-10", "2026-12-17") in report
        assert "2026" in report
        assert owner_stamp(NOW) in report
        blocks = report.split("### ")
        opening = next(block for block in blocks if block.startswith("Thursday 2026-12-10 - Alfama"))
        closing = next(block for block in blocks if block.startswith("Thursday 2026-12-17"))
        middle = next(block for block in blocks if block.startswith("Friday 2026-12-11"))
        assert "light" in opening.splitlines()[0]
        assert "light" in closing.splitlines()[0]
        assert "light" not in middle.splitlines()[0]
        assert "Castelo de Sao Jorge" not in opening
        assert_hermes_not_called(tmp)


def test_s3_party_bags_children_relative() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        fixture = read_json(FIXTURES / "trip_lisbon.json")
        plan(
            data,
            env,
            "bags",
            FIXTURES / "trip_lisbon.json",
            lisbon_flags("2"),
        )
        assert_plan_report(
            data,
            "bags",
            fixture,
            adults=2,
            children=[],
            bags=2,
            cabin="economy",
            rooms=1,
            origin="BOS",
            destination="Lisbon",
            start="2026-12-10",
            end="2026-12-17",
            watch_on=False,
        )
        assert "815.00" in (data / "trips" / "bags.md").read_text(encoding="utf-8")

        plan(
            data,
            env,
            "kids",
            FIXTURES / "trip_lisbon.json",
            lisbon_flags("1", ["--children", "8,11"]),
        )
        report = (data / "trips" / "kids.md").read_text(encoding="utf-8")
        assert "children 8, 11" in report
        assert_hermes_not_called(tmp)

    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        phrase = "in 34 days for 7 nights"
        start, end = resolve_relative_dates(phrase, NOW, TZ)
        assert (start, end) == ("2026-12-10", "2026-12-17")
        saved = run_script(
            "onboard.py",
            ["--data", str(data), "--step", "dates", "--value", phrase, "--now", NOW, "--tz", TZ],
            env,
        )
        assert saved.returncode == 0, saved.stderr
        assert read_state(data)["dates"] == {"start": start, "end": end}
        assert run_script(
            "onboard.py",
            ["--data", str(data), "--step", "dest", "--value", "Lisbon", "--now", NOW, "--tz", TZ],
            env,
        ).returncode == 0
        assert run_script(
            "onboard.py",
            ["--data", str(data), "--step", "party", "--value", "2", "--now", NOW, "--tz", TZ],
            env,
        ).returncode == 0
        plan(
            data,
            env,
            "relative",
            FIXTURES / "trip_lisbon.json",
            ["--home", "BOS", "--cabin", "economy", "--bags", "1"],
        )
        report = (data / "trips" / "relative.md").read_text(encoding="utf-8")
        assert dates_fact(start, end) in report
        assert "Thursday" in report
        assert "2026" in report


def test_s3_overnight_flex_and_constraints() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        overnight = read_json(FIXTURES / "trip_overnight.json")
        plan(data, env, "overnight", FIXTURES / "trip_overnight.json", lisbon_flags())
        assert_plan_report(
            data,
            "overnight",
            overnight,
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
        report = (data / "trips" / "overnight.md").read_text(encoding="utf-8")
        assert "Arrive LIS 2026-12-11 10:15 WET" in report
        assert "Depart BOS 2026-12-10 22:30 ET" in report
        assert weekday_name("2026-12-11") == "Friday"
        sources = read_json(data / "trips" / "overnight-sources.json")
        ov = next(row for row in sources["sources"] if row["id"] == "OV-1")
        assert ov["arrival_local_date"] == "2026-12-11"
        assert ov["departure_local_date"] == "2026-12-10"
        assert "Arrive LIS 2026-12-10 10:15 WET" not in report

        flex = read_json(FIXTURES / "trip_flex.json")
        plan(data, env, "flex", FIXTURES / "trip_flex.json", lisbon_flags("0", ["--flex"]))
        assert_plan_report(
            data,
            "flex",
            flex,
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

        lisbon = read_json(FIXTURES / "trip_lisbon.json")
        plan(
            data,
            env,
            "stops",
            FIXTURES / "trip_lisbon.json",
            lisbon_flags("1", ["--max-stops", "0"]),
        )
        assert_plan_report(
            data,
            "stops",
            lisbon,
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
            max_stops=0,
        )
        assert "TP-CHEAP" not in (data / "trips" / "stops.md").read_text(encoding="utf-8")

        plan(
            data,
            env,
            "arrive",
            FIXTURES / "trip_lisbon.json",
            lisbon_flags("1", ["--arrival-by", "09:00"]),
        )
        assert_plan_report(
            data,
            "arrive",
            lisbon,
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
            arrival_by="09:00",
        )
        arrive_report = (data / "trips" / "arrive.md").read_text(encoding="utf-8")
        assert "TP-CHEAP" not in arrive_report
        assert "TP-VALUE" not in arrive_report
        assert "TP-COMFY" in arrive_report

        plan(
            data,
            env,
            "refund",
            FIXTURES / "trip_lisbon.json",
            lisbon_flags("1", ["--refundable"]),
        )
        assert_plan_report(
            data,
            "refund",
            lisbon,
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
            refundable=True,
        )
        refund_report = (data / "trips" / "refund.md").read_text(encoding="utf-8")
        assert "TP-COMFY" in refund_report
        assert "TP-CHEAP" not in refund_report
        assert_hermes_not_called(tmp)


def test_s4_fees_currency_empty_hours() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        incomplete = read_json(FIXTURES / "trip_incomplete_fees.json")
        plan(data, env, "fees", FIXTURES / "trip_incomplete_fees.json", lisbon_flags())
        assert_plan_report(
            data,
            "fees",
            incomplete,
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
        assert "Cheapest sensible: H-UNKNOWN" not in report
        assert "Best value: H-UNKNOWN" not in report
        assert "Most comfortable: H-UNKNOWN" not in report
        assert "basic economy, bag fee 35.00, no seat selection" in report
        assert "resort fee 15.00 per night" in report
        assert "cancellation deadline 2026-12-01" in report
        assert "2520.00" in report

        eur = read_json(FIXTURES / "trip_eur.json")
        plan(data, env, "eur", FIXTURES / "trip_eur.json", lisbon_flags("0"))
        assert_plan_report(
            data,
            "eur",
            eur,
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
        eur_report = (data / "trips" / "eur.md").read_text(encoding="utf-8")
        assert "Cheapest sensible: EUR-1" not in eur_report
        assert "Cheapest sensible: USD-CHEAP" in eur_report
        assert "different currency" in eur_report.casefold()

        empty = read_json(FIXTURES / "trip_empty.json")
        result = plan(data, env, "empty", FIXTURES / "trip_empty.json", [
            "--dest",
            "Emptyville",
            "--start",
            "2026-12-10",
            "--end",
            "2026-12-17",
            "--adults",
            "2",
            "--home",
            "BOS",
        ])
        assert result.returncode == 0
        assert_plan_report(
            data,
            "empty",
            empty,
            adults=2,
            children=[],
            bags=0,
            cabin="economy",
            rooms=1,
            origin="BOS",
            destination="Emptyville",
            start="2026-12-10",
            end="2026-12-17",
            watch_on=False,
        )
        empty_report = (data / "trips" / "empty.md").read_text(encoding="utf-8")
        assert "Cheapest sensible" not in empty_report
        assert "Best value" not in empty_report
        assert "Most comfortable" not in empty_report
        from helpers import PRICE_RE

        assert PRICE_RE.search(empty_report) is None

        venues = read_json(FIXTURES / "venues_unknown_hours.json")
        plan(data, env, "hours", FIXTURES / "venues_unknown_hours.json", lisbon_flags("0"))
        assert_plan_report(
            data,
            "hours",
            venues,
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
        hours_report = (data / "trips" / "hours.md").read_text(encoding="utf-8")
        assert "confirm before you go." in hours_report
        assert "Miradouro de Santa Catarina" in hours_report
        assert "09:00" not in hours_report
        assert "open daily" not in hours_report.casefold()
        assert PRICE_RE.search(hours_report) is None
        assert_hermes_not_called(tmp)


def test_s5_overwrite_and_private_confirm() -> None:
    with TemporaryDirectory() as raw:
        tmp = Path(raw)
        data = seed_data(tmp)
        env = make_env(tmp)
        fixture = read_json(FIXTURES / "trip_lisbon.json")
        plan(data, env, "lisbon", FIXTURES / "trip_lisbon.json", lisbon_flags())
        md_path = data / "trips" / "lisbon.md"
        html_path = data / "trips" / "lisbon.html"
        first_md = md_path.resolve()
        first_html = html_path.resolve()
        md_path.write_text(md_path.read_text(encoding="utf-8") + "\nMARKER-OLD-ITINERARY\n", encoding="utf-8")
        html_path.write_text(html_path.read_text(encoding="utf-8") + "\nMARKER-OLD-ITINERARY\n", encoding="utf-8")
        plan(data, env, "lisbon", FIXTURES / "trip_lisbon.json", lisbon_flags())
        assert md_path.resolve() == first_md
        assert html_path.resolve() == first_html
        assert not (data / "trips" / "lisbon-2.md").exists()
        assert "MARKER-OLD-ITINERARY" not in md_path.read_text(encoding="utf-8")
        assert "MARKER-OLD-ITINERARY" not in html_path.read_text(encoding="utf-8")
        assert_plan_report(
            data,
            "lisbon",
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

        note = run_script(
            "confirm.py",
            ["--data", str(data), "--slug", "lisbon", "--text", "just a note"],
            env,
        )
        assert note.returncode == 0, note.stderr
        private = data / "trips" / "lisbon-private.md"
        assert private.read_text(encoding="utf-8").count("just a note") == 1
        assert "Booking status: planning" in md_path.read_text(encoding="utf-8")

        booked = run_script(
            "confirm.py",
            [
                "--data",
                str(data),
                "--slug",
                "lisbon",
                "--text",
                "Booked for Alex Traveler confirmation ABC123",
            ],
            env,
        )
        assert booked.returncode == 0, booked.stderr
        private_text = private.read_text(encoding="utf-8")
        assert private_text.index("just a note") < private_text.index("Alex Traveler")
        assert "ABC123" in private_text
        for path in (md_path, html_path):
            text = path.read_text(encoding="utf-8")
            assert "Booking status: booked" in text
            assert "ABC123" not in text
            assert "Alex Traveler" not in text

        plan(data, env, "lisbon", FIXTURES / "trip_lisbon.json", lisbon_flags())
        assert_plan_report(
            data,
            "lisbon",
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
            booking_status="booked",
        )
        rewritten = md_path.read_text(encoding="utf-8")
        assert "ABC123" not in rewritten
        assert "Alex Traveler" not in rewritten
        assert "just a note" in private.read_text(encoding="utf-8")

        card = run_script("card.py", ["--data", str(data), "--slug", "lisbon"], env)
        assert card.returncode == 0, card.stderr
        for name in ("lisbon-card.md", "lisbon-card.html"):
            share = (data / "trips" / name).read_text(encoding="utf-8")
            assert "ABC123" not in share
            assert "Alex Traveler" not in share
        assert_hermes_not_called(tmp)


def main() -> None:
    test_s2_s3_lisbon()
    test_s3_party_bags_children_relative()
    test_s3_overnight_flex_and_constraints()
    test_s4_fees_currency_empty_hours()
    test_s5_overwrite_and_private_confirm()
    print("test_plan.py PASS")


if __name__ == "__main__":
    main()
