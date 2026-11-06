#!/usr/bin/env python3
"""Shared helpers for Fare Hawk contract tests. No model calls."""

from __future__ import annotations

import csv
import html as html_lib
import io
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = Path(__file__).resolve().parent / "fixtures"
NOW = "2026-11-06T15:00:00Z"
TZ = "America/New_York"
INTRO = (
    "Tell me where and when. In 10 minutes you'll have a day-by-day itinerary card, "
    "3 flight and hotel options, and a price watch that pings you when fares drop. "
    "You book; I watch and report."
)
FOOTER = "Try Hermes: Fare Hawk by SMF Works."
DEMO = "fixture/demo, not live fares"
ROLES = ("Cheapest sensible", "Best value", "Most comfortable")
CRON_EXPR = "7 6,18 * * *"
PRODUCT_KEY = "BOS-LIS|2026-12-10|2026-12-17|economy|standard"
WATCH_ROUTE = "BOS-LIS"
WATCH_PARTY = "2 adults"
WATCH_DETAILS = "TP 216, 2026-12-10 to 2026-12-17"
WATCH_SOURCE = "Fixture Air"
WATCH_LINK = "https://fixtures.example/bos-lis"
INVENTED_VENUE = "NOT-A-REAL-VENUE-99"
INTEGRATIONS_SENTENCE = (
    "v1 does not write mail, calendar, or Drive, and it does not execute a booking."
)
ASSUMPTION = "one adult economy"
TWOPLACES = Decimal("0.01")
SLUG_RE = re.compile(r"^[a-z0-9-]{1,64}$")
PRICE_RE = re.compile(r"(?<![\d.])\d+\.\d{2}(?!\d)")
ZONE_SHORT = {"America/New_York": "ET"}
CSV_HEADER = "seen_at,status,price,currency,source,link,notes,product_key"
ONBOARD_FIELDS = (
    "home",
    "dest",
    "dates",
    "party",
    "cabin",
    "bags",
    "pace",
    "budget",
    "interests",
    "loyalty",
    "integrations",
    "threshold",
    "watch",
)


def money(value: Decimal | str | int) -> str:
    decimal = value if isinstance(value, Decimal) else Decimal(str(value))
    return format(decimal.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN), "f")


def make_env(tmp: Path) -> dict[str, str]:
    env = os.environ.copy()
    home = tmp / "home"
    home.mkdir(exist_ok=True)
    bindir = tmp / "bin"
    bindir.mkdir(exist_ok=True)
    marker = tmp / "hermes-invoked"
    hermes = bindir / "hermes"
    hermes.write_text(
        f"#!/bin/sh\necho invoked > {shlex.quote(str(marker))}\nexit 99\n",
        encoding="utf-8",
    )
    hermes.chmod(0o755)
    env["HOME"] = str(home)
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def assert_hermes_not_called(tmp: Path) -> None:
    assert not (tmp / "hermes-invoked").exists(), "hermes was invoked"
    assert not (tmp / "home" / ".hermes").exists(), "script wrote ~/.hermes"


def run_script(
    script: str,
    args: list[str],
    env: dict[str, str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    path = ROOT / "scripts" / script
    assert path.is_file(), f"missing {path}"
    return subprocess.run(
        [sys.executable, str(path), *args],
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
        cwd=str(cwd or ROOT),
        env=env,
        stdin=subprocess.DEVNULL,
        timeout=30,
    )


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def read_state(data: Path) -> dict:
    return json.loads((data / "state.json").read_text(encoding="utf-8"))


def trip_state_path(data: Path, slug: str) -> Path:
    return data / "trips" / f"{slug}-state.json"


def read_trip_state(data: Path, slug: str) -> dict:
    return json.loads(trip_state_path(data, slug).read_text(encoding="utf-8"))


def seed_data(tmp: Path, state: dict | None = None) -> Path:
    data = tmp / "data"
    data.mkdir()
    payload = {"sentinel": "keep-me"}
    if state:
        payload.update(state)
    write_json(data / "state.json", payload)
    return data


def seed_trip(data: Path, slug: str, **overrides: object) -> Path:
    payload: dict[str, object] = {
        "slug": slug,
        "watch_yes": False,
        "paused": False,
        "baseline": "1000.00",
        "lowest_alerted": None,
        "last_alert_fingerprint": None,
        "currency": "USD",
        "threshold_mode": "default_usd",
        "cabin": "economy",
        "room": "standard",
        "product_key": PRODUCT_KEY,
        "departure": "2026-12-10",
        "end": "2026-12-17",
        "route": WATCH_ROUTE,
        "party": WATCH_PARTY,
        "details": WATCH_DETAILS,
        "source": WATCH_SOURCE,
        "link": WATCH_LINK,
        "outage_open": False,
        "checks_by_local_date": {},
        "owner_note": "keep-me",
    }
    payload.update(overrides)
    path = trip_state_path(data, slug)
    write_json(path, payload)
    return path


def civil_date(iso: str, tz: str) -> date:
    instant = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return instant.astimezone(ZoneInfo(tz)).date()


def owner_stamp(iso: str, tz: str = TZ) -> str:
    instant = datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo(tz))
    label = ZONE_SHORT.get(tz, tz)
    return instant.strftime("%Y-%m-%d %H:%M") + f" {label}"


def weekday_name(iso_date: str) -> str:
    return date.fromisoformat(iso_date).strftime("%A")


def resolve_relative_dates(phrase: str, now: str, tz: str) -> tuple[str, str]:
    match = re.fullmatch(r"in (\d+) days for (\d+) nights", phrase.strip())
    assert match, phrase
    start = civil_date(now, tz) + timedelta(days=int(match.group(1)))
    end = start + timedelta(days=int(match.group(2)))
    return start.isoformat(), end.isoformat()


def party_fact(adults: int, children: list[int], cabin: str, bags: int, rooms: int) -> str:
    adult_text = "1 adult" if adults == 1 else f"{adults} adults"
    if children:
        child_text = "children " + ", ".join(str(age) for age in children)
    else:
        child_text = "0 children"
    return (
        f"Party: {adult_text}, {child_text}. Cabin: {cabin}. "
        f"Bags: {bags}. Rooms: {rooms}."
    )


def dates_fact(start: str, end: str) -> str:
    return f"Dates: {weekday_name(start)} {start} to {weekday_name(end)} {end}"


def day_heading(day: dict) -> str:
    heading = f"### {weekday_name(day['date'])} {day['date']} - {day['neighborhood']}"
    if day.get("pace") == "light":
        return heading + " - light"
    return heading


def flight_total(flight: dict, adults: int, children: int, bags: int) -> Decimal:
    total = (
        Decimal(flight["fare_per_adult"]) * adults
        + Decimal(flight.get("fare_per_child") or "0") * children
        + Decimal(flight.get("bag_fee_each") or "0") * bags
        + Decimal(flight.get("taxes") or "0")
    )
    return total.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


def traveler_fare(flight: dict, adults: int, children: int) -> Decimal:
    total = Decimal(flight["fare_per_adult"]) * adults + Decimal(flight.get("fare_per_child") or "0") * children
    return total.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


def hotel_amounts(hotel: dict) -> tuple[Decimal | None, Decimal | None]:
    """Return (known nightly stay, all-in total or None when fees are incomplete)."""
    nights = Decimal(str(hotel["nights"]))
    rooms = Decimal(str(hotel["rooms"]))
    nightly = Decimal(hotel["nightly"])
    resort = hotel.get("resort_fee_per_night")
    if resort is None or not hotel.get("fees_complete", True):
        known = (nightly * nights * rooms).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)
        return known, None
    stay = (nightly + Decimal(resort)) * nights * rooms
    total = (stay + Decimal(hotel.get("taxes") or "0")).quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)
    return stay.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN), total


def assign_roles(options: list[dict]) -> dict[str, dict]:
    ordered = sorted(options, key=lambda item: (item["total"], item["id"]))
    roles: dict[str, dict] = {}
    if not ordered:
        return roles
    roles["Cheapest sensible"] = ordered[0]
    if len(ordered) >= 2:
        rest = ordered[1:]
        roles["Most comfortable"] = sorted(rest, key=lambda item: (-item["comfort"], item["id"]))[0]
    if len(ordered) >= 3:
        used = {item["id"] for item in roles.values()}
        leftover = [item for item in ordered if item["id"] not in used]
        roles["Best value"] = sorted(leftover, key=lambda item: item["id"])[0]
    return roles


def flight_kept(flight: dict, *, max_stops: int | None, arrival_by: str | None, refundable: bool) -> bool:
    if not flight.get("verified", True):
        return False
    if max_stops is not None and int(flight["stops"]) > max_stops:
        return False
    if arrival_by is not None and str(flight["arrive_hhmm"]) > arrival_by:
        return False
    if refundable and not flight.get("refundable"):
        return False
    return True


def classify_flights(
    flights: list[dict],
    *,
    adults: int,
    children: int,
    bags: int,
    comparison: str,
    max_stops: int | None = None,
    arrival_by: str | None = None,
    refundable: bool = False,
) -> tuple[dict[str, dict], list[dict], list[dict]]:
    eligible: list[dict] = []
    other: list[dict] = []
    for flight in flights:
        if not flight_kept(flight, max_stops=max_stops, arrival_by=arrival_by, refundable=refundable):
            continue
        currency = flight.get("currency") or comparison
        total = flight_total(flight, adults, children, bags)
        item = {**flight, "currency": currency, "total": total}
        incomplete = not flight.get("fees_complete", True)
        if incomplete or currency != comparison:
            other.append(item)
        else:
            eligible.append(item)
    return assign_roles(eligible), other, eligible


def classify_hotels(hotels: list[dict], comparison: str) -> tuple[dict[str, dict], list[dict], list[dict]]:
    eligible: list[dict] = []
    other: list[dict] = []
    for hotel in hotels:
        if not hotel.get("verified", True):
            continue
        currency = hotel.get("currency") or comparison
        known, total = hotel_amounts(hotel)
        item = {**hotel, "currency": currency, "known": known, "total": total}
        if total is None or currency != comparison:
            other.append(item)
        else:
            eligible.append(item)
    return assign_roles(eligible), other, eligible


def depart_line(flight: dict) -> str:
    return (
        f"Depart {flight['depart_airport']} {flight['depart_date']} "
        f"{flight['depart_hhmm']} {flight['depart_zone_label']}"
    )


def arrive_line(flight: dict) -> str:
    return (
        f"Arrive {flight['arrive_airport']} {flight['arrive_date']} "
        f"{flight['arrive_hhmm']} {flight['arrive_zone_label']}"
    )


def assert_contains(text: str, needle: str, label: str) -> None:
    assert needle in text, f"{label} missing {needle!r}"


def special_snippets(fixture: dict) -> list[str]:
    found: list[str] = []
    blobs: list[str] = []
    for day in fixture.get("days") or []:
        blobs.extend(day.get("anchors") or [])
        for key in ("meal", "rain", "neighborhood"):
            if day.get(key):
                blobs.append(str(day[key]))
    for venue in fixture.get("venues") or []:
        if venue.get("name"):
            blobs.append(str(venue["name"]))
    for value in blobs:
        if any(char in value for char in "<>&") and value not in found:
            found.append(value)
    return found


def assert_line(text: str, needle: str) -> None:
    escaped = html_lib.escape(needle)
    lines = [line.strip() for line in text.splitlines()]
    if any(needle in line or escaped in line for line in lines):
        return
    assert needle in text or escaped in text, needle


def assert_choice_cap(stdout: str) -> None:
    for line in stdout.splitlines():
        if " / " in line:
            parts = [part.strip() for part in line.split("/") if part.strip()]
            assert len(parts) <= 5, line
    block = 0
    counts: list[int] = []
    for line in stdout.splitlines():
        if re.match(r"^\s*(\d+[\.\)]|[-*])\s+\S", line):
            block += 1
        else:
            if block:
                counts.append(block)
            block = 0
    if block:
        counts.append(block)
    for count in counts:
        assert count <= 5, stdout


def assert_one_question(stdout: str) -> None:
    assert stdout.count("?") <= 1, stdout


def plan_cmd(data: Path, slug: str, fixture: Path, extra: list[str] | None = None) -> list[str]:
    args = [
        "--data",
        str(data),
        "--slug",
        slug,
        "--backend",
        "fixtures",
        "--fixtures",
        str(fixture),
        "--now",
        NOW,
        "--tz",
        TZ,
    ]
    if extra:
        args.extend(extra)
    return args


def watch_cmd(
    data: Path,
    slug: str,
    fixture: Path,
    extra: list[str] | None = None,
    *,
    now: str = NOW,
    tz: str = TZ,
) -> list[str]:
    args = [
        "--data",
        str(data),
        "--slug",
        slug,
        "--backend",
        "fixtures",
        "--fixtures",
        str(fixture),
        "--now",
        now,
        "--tz",
        tz,
    ]
    if extra:
        args.extend(extra)
    return args


def load_watch_logic():
    scripts = str(ROOT / "scripts")
    if scripts not in sys.path:
        sys.path.insert(0, scripts)
    from watch_logic import drop_threshold, evaluate_observation, should_alert_drop

    return drop_threshold, should_alert_drop, evaluate_observation


def read_csv_rows(path: Path) -> list[dict[str, str]]:
    """Read prices.csv. QUOTE_MINIMAL and QUOTE_ALL both round-trip."""
    assert path.is_file(), f"missing {path}"
    text = path.read_text(encoding="utf-8")
    parsed = list(csv.reader(io.StringIO(text, newline="")))
    assert parsed, "empty csv"
    assert parsed[0] == CSV_HEADER.split(","), parsed[0]
    return list(csv.DictReader(io.StringIO(text, newline="")))


def read_outbox(data: Path) -> list[dict]:
    path = data / "outbox.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def load_jobs(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(loaded, list):
        return loaded
    assert isinstance(loaded, dict), "jobs file must be a list or an object"
    jobs = loaded.get("jobs", [])
    assert isinstance(jobs, list)
    return jobs


def schedule_expr(job: dict) -> str:
    schedule = job.get("schedule")
    if isinstance(schedule, str):
        expr = schedule
    elif isinstance(schedule, dict):
        expr = str(schedule.get("expr", ""))
    else:
        expr = ""
    return " ".join(expr.split())


def decimal_eq(left: object, right: object) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return Decimal(str(left)) == Decimal(str(right))


def assert_drop_block(
    block: str,
    *,
    route: str,
    amount: str,
    currency: str,
    details: str,
    party: str,
    reference: str,
    current: str,
    stamp: str,
    source: str,
    link: str,
) -> None:
    assert f"Fare Hawk: {route} dropped {amount} {currency}" in block, block
    assert f"{details}, {party}: {reference} → {current}" in block, block
    assert f"Seen {stamp} on {source} · lowest alerted since watch began" in block, block
    assert f"{link} · You book; total may change at checkout." in block, block


def fare_blocks(stdout: str) -> list[str]:
    parts = stdout.split("Fare Hawk:")
    return ["Fare Hawk:" + part.strip() for part in parts[1:]]


def lodging_area(fixture: dict, roles: dict[str, dict]) -> str | None:
    cheapest = roles.get("Cheapest sensible")
    if cheapest and cheapest.get("neighborhood"):
        return str(cheapest["neighborhood"])
    days = fixture.get("days") or []
    if days:
        return str(days[0]["neighborhood"])
    return None


def assert_plan_report(
    data: Path,
    slug: str,
    fixture: dict,
    *,
    adults: int,
    children: list[int],
    bags: int,
    cabin: str,
    rooms: int,
    origin: str,
    destination: str,
    start: str,
    end: str,
    watch_on: bool,
    max_stops: int | None = None,
    arrival_by: str | None = None,
    refundable: bool = False,
    assumption: str | None = None,
    booking_status: str = "planning",
) -> None:
    md_path = data / "trips" / f"{slug}.md"
    html_path = data / "trips" / f"{slug}.html"
    sources_path = data / "trips" / f"{slug}-sources.json"
    state_path = trip_state_path(data, slug)
    assert md_path.is_file(), md_path
    assert html_path.is_file(), html_path
    assert sources_path.is_file(), sources_path
    assert state_path.is_file(), state_path
    md = md_path.read_text(encoding="utf-8")
    html = html_path.read_text(encoding="utf-8")
    sources = read_json(sources_path)
    comparison = fixture.get("comparison_currency") or "USD"
    flight_roles, flight_other, flight_eligible = classify_flights(
        fixture.get("flights") or [],
        adults=adults,
        children=len(children),
        bags=bags,
        comparison=comparison,
        max_stops=max_stops,
        arrival_by=arrival_by,
        refundable=refundable,
    )
    hotel_roles, hotel_other, hotel_eligible = classify_hotels(fixture.get("lodging") or [], comparison)
    shown_ids = set()

    for text, label in ((md, "md"), (html, "html")):
        assert_contains(text, DEMO, label)
        assert_contains(text, FOOTER, label)
        assert_line(text, f"Destination: {destination}")
        assert_line(text, dates_fact(start, end))
        assert_line(text, party_fact(adults, children, cabin, bags, rooms))
        assert_line(text, f"Home: {origin}")
        assert_line(text, f"Route: {origin}-{fixture.get('destination_code', '')}")
        assert_line(text, "Watch: on" if watch_on else "Watch: off")
        assert_line(text, f"Booking status: {booking_status}")
        assert "## Itinerary" in text
        assert "## Flights" in text
        assert "## Lodging" in text
        if assumption:
            assert_contains(text, assumption, label)
        area = lodging_area(fixture, hotel_roles)
        if area:
            assert_line(text, f"Lodging area: {area}")
        for day in fixture.get("days") or []:
            assert_line(text, day_heading(day))
            for anchor in day.get("anchors") or []:
                assert_line(text, f"- {anchor}")
            meal = day.get("meal")
            if meal:
                prefix = "Signature meal" if day.get("signature") else "Meal"
                assert_line(text, f"{prefix}: {meal}")
            if day.get("rain"):
                assert_line(text, f"Rain backup: {day['rain']}")
            if day.get("hours") is None and "hours" in day:
                assert_line(text, "Hours: confirm before you go.")
            elif day.get("hours"):
                assert_line(text, f"Hours: {day['hours']}")
        if fixture.get("limitation"):
            assert_contains(text, fixture["limitation"], label)
        if fixture.get("unchecked_note"):
            assert_contains(text, fixture["unchecked_note"], label)
        for pair in fixture.get("checked_pairs") or []:
            assert_line(text, f"Checked: {pair['start']} to {pair['end']}")
        for role, item in flight_roles.items():
            assert_line(text, f"{role}: {item['id']} - {money(item['total'])} {item['currency']}")
            assert_line(text, f"All travelers: {money(traveler_fare(item, adults, len(children)))} {item['currency']}")
            shown_ids.add(item["id"])
        for item in flight_other:
            if not item.get("fees_complete", True):
                assert_line(text, f"Incomplete: {item['id']}")
                assert "unknown" in text.casefold()
            else:
                assert_line(
                    text,
                    f"Different currency: {item['id']} - {money(item['total'])} {item['currency']}",
                )
            assert_line(text, f"All travelers: {money(traveler_fare(item, adults, len(children)))} {item['currency']}")
            shown_ids.add(item["id"])
        for role, item in hotel_roles.items():
            assert_line(text, f"{role}: {item['id']} - {money(item['total'])} {item['currency']}")
            assert_line(text, f"Nightly stay: {money(item['known'])} {item['currency']}")
            assert_line(text, f"rooms: {item['rooms']}")
            if item.get("rating") is not None:
                assert_line(text, f"Rating: {item['rating']} ({item['rating_count']})")
            shown_ids.add(item["id"])
        for item in hotel_other:
            if item["total"] is None:
                assert_line(
                    text,
                    f"Incomplete: {item['id']} - nightly stay {money(item['known'])} - total unknown",
                )
            else:
                assert_line(
                    text,
                    f"Different currency: {item['id']} - {money(item['total'])} {item['currency']}",
                )
                assert_line(text, f"Nightly stay: {money(item['known'])} {item['currency']}")
            assert_line(text, f"rooms: {item['rooms']}")
            shown_ids.add(item["id"])
        for pool in (flight_roles, hotel_roles):
            for role, item in pool.items():
                if item.get("restrictions"):
                    assert_contains(text, item["restrictions"], label)
                assert_contains(text, item["url"], label)
                assert_contains(text, owner_stamp(item["seen_at"]), label)
        for item in flight_other + hotel_other:
            if item.get("restrictions"):
                assert_contains(text, item["restrictions"], label)
            assert_contains(text, item["url"], label)
            assert_contains(text, owner_stamp(item["seen_at"]), label)
        for item in list(flight_roles.values()) + [row for row in flight_other]:
            assert_contains(text, depart_line(item), label)
            assert_contains(text, arrive_line(item), label)
            assert_contains(text, item["depart_zone"], label)
            assert_contains(text, item["arrive_zone"], label)
        if len(flight_eligible) < 3 or len(hotel_eligible) < 3:
            assert "coverage" in text.casefold(), label
        assert INVENTED_VENUE not in text
        if label == "html":
            folded = text.casefold()
            assert "<script" not in folded
            assert "iframe" not in folded
            assert "onerror" not in folded
            for raw in special_snippets(fixture):
                assert html_lib.escape(raw) in text
                assert raw not in text

    dropped = []
    for flight in fixture.get("flights") or []:
        if flight["id"] not in shown_ids:
            dropped.append(flight["id"])
            assert flight["id"] not in md
            assert flight["id"] not in html
    for hotel in fixture.get("lodging") or []:
        if hotel["id"] not in shown_ids:
            assert hotel["id"] not in md or "Incomplete:" in md or "Different currency:" in md

    catalog = {entry["id"]: entry for entry in sources.get("sources", [])}
    for ident in shown_ids:
        assert ident in catalog, ident
        entry = catalog[ident]
        assert entry["url"]
        assert entry["seen_at"]
        assert entry["seen_at_local"] == owner_stamp(entry["seen_at"])
    for flight in list(flight_roles.values()) + flight_other:
        entry = catalog[flight["id"]]
        assert entry["departure_local_date"] == flight["depart_date"]
        assert entry["arrival_local_date"] == flight["arrive_date"]
        assert entry["kind"] == "flight"

    trip_state = read_trip_state(data, slug)
    assert trip_state["delivery_status"] == "recorded"
    assert trip_state["slug"] == slug
    assert trip_state["adults"] == adults
    assert list(trip_state["children"]) == list(children)
    assert trip_state["start"] == start
    assert trip_state["end"] == end
    assert trip_state["destination"] == destination
    profile = read_state(data)
    assert profile.get("sentinel") == "keep-me"
    assert profile.get("setup_complete") is True
    return None
