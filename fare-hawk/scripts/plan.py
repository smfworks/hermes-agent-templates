#!/usr/bin/env python3
"""Build a working itinerary from a fixtures file. No network calls."""

from __future__ import annotations

import argparse
import html
import json
import sys
from datetime import date
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from store import (
    TWOPLACES,
    atomic_write,
    load_json,
    money,
    mutate_json,
    owner_stamp,
    require_slug,
    trip_path,
)
from travel_lookup import load_fixture

DEMO = "fixture/demo, not live fares"
FOOTER = "Try Hermes: Fare Hawk by SMF Works."
ROLES = ("Cheapest sensible", "Best value", "Most comfortable")


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Write a Fare Hawk working itinerary.")
    parser.add_argument("--data", required=True)
    parser.add_argument("--slug", required=True)
    parser.add_argument("--backend", default="fixtures")
    parser.add_argument("--fixtures")
    parser.add_argument("--now", default="2026-11-06T15:00:00Z")
    parser.add_argument("--tz", default="America/New_York")
    parser.add_argument("--dest")
    parser.add_argument("--start")
    parser.add_argument("--end")
    parser.add_argument("--adults", type=int)
    parser.add_argument("--children")
    parser.add_argument("--cabin")
    parser.add_argument("--bags", type=int)
    parser.add_argument("--home")
    parser.add_argument("--flex", action="store_true")
    parser.add_argument("--arrival-by", dest="arrival_by")
    parser.add_argument("--max-stops", dest="max_stops", type=int)
    parser.add_argument("--refundable", action="store_true")
    parser.add_argument("--assume-one-adult", dest="assume_one_adult", action="store_true")
    return parser.parse_args(argv)


def weekday_name(iso_date: str) -> str:
    return date.fromisoformat(iso_date).strftime("%A")


def quantize(value: Decimal) -> Decimal:
    return value.quantize(TWOPLACES, rounding=ROUND_HALF_EVEN)


def flight_total(flight: dict, adults: int, children: int, bags: int) -> Decimal:
    total = (
        Decimal(flight["fare_per_adult"]) * adults
        + Decimal(flight.get("fare_per_child") or "0") * children
        + Decimal(flight.get("bag_fee_each") or "0") * bags
        + Decimal(flight.get("taxes") or "0")
    )
    return quantize(total)


def traveler_fare(flight: dict, adults: int, children: int) -> Decimal:
    total = Decimal(flight["fare_per_adult"]) * adults + Decimal(flight.get("fare_per_child") or "0") * children
    return quantize(total)


def hotel_amounts(hotel: dict) -> tuple[Decimal | None, Decimal | None]:
    nights = Decimal(str(hotel["nights"]))
    rooms = Decimal(str(hotel["rooms"]))
    nightly = Decimal(hotel["nightly"])
    resort = hotel.get("resort_fee_per_night")
    if resort is None or not hotel.get("fees_complete", True):
        known = quantize(nightly * nights * rooms)
        return known, None
    stay = (nightly + Decimal(resort)) * nights * rooms
    total = quantize(stay + Decimal(hotel.get("taxes") or "0"))
    return quantize(stay), total


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


def classify_flights(flights, *, adults, children, bags, comparison, max_stops, arrival_by, refundable):
    eligible = []
    other = []
    for flight in flights:
        if not flight_kept(flight, max_stops=max_stops, arrival_by=arrival_by, refundable=refundable):
            continue
        currency = flight.get("currency") or comparison
        total = flight_total(flight, adults, children, bags)
        item = {**flight, "currency": currency, "total": total}
        if (not flight.get("fees_complete", True)) or currency != comparison:
            other.append(item)
        else:
            eligible.append(item)
    return assign_roles(eligible), other, eligible


def classify_hotels(hotels, comparison: str):
    eligible = []
    other = []
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


def party_line(adults: int, children: list[int], cabin: str, bags: int, rooms: int) -> str:
    adult_text = "1 adult" if adults == 1 else f"{adults} adults"
    if children:
        child_text = "children " + ", ".join(str(age) for age in children)
    else:
        child_text = "0 children"
    return (
        f"Party: {adult_text}, {child_text}. Cabin: {cabin}. "
        f"Bags: {bags}. Rooms: {rooms}."
    )


def day_lines(day: dict) -> list[str]:
    heading = f"### {weekday_name(day['date'])} {day['date']} - {day['neighborhood']}"
    if day.get("pace") == "light":
        heading += " - light"
    lines = [heading]
    for anchor in day.get("anchors") or []:
        lines.append(f"- {anchor}")
    meal = day.get("meal")
    if meal:
        prefix = "Signature meal" if day.get("signature") else "Meal"
        lines.append(f"{prefix}: {meal}")
    if day.get("rain"):
        lines.append(f"Rain backup: {day['rain']}")
    if "hours" in day and day.get("hours") is None:
        lines.append("Hours: confirm before you go.")
    elif day.get("hours"):
        lines.append(f"Hours: {day['hours']}")
    return lines


def stamp_for(item: dict, tz: str) -> str:
    return owner_stamp(item["seen_at"], tz)


def flight_lines(item: dict, role: str | None, adults: int, children: int, tz: str, incomplete: bool) -> list[str]:
    lines = []
    if role:
        lines.append(f"- {role}: {item['id']} - {money(item['total'])} {item['currency']}")
    elif incomplete:
        lines.append(f"Incomplete: {item['id']} - total unknown")
    else:
        lines.append(f"Different currency: {item['id']} - {money(item['total'])} {item['currency']}")
    lines.append(
        f"All travelers: {money(traveler_fare(item, adults, children))} {item['currency']}"
    )
    lines.append(
        f"Depart {item['depart_airport']} {item['depart_date']} "
        f"{item['depart_hhmm']} {item['depart_zone_label']}"
    )
    lines.append(
        f"Arrive {item['arrive_airport']} {item['arrive_date']} "
        f"{item['arrive_hhmm']} {item['arrive_zone_label']}"
    )
    lines.append(str(item["depart_zone"]))
    lines.append(str(item["arrive_zone"]))
    if item.get("restrictions"):
        lines.append(str(item["restrictions"]))
    lines.append(str(item["url"]))
    lines.append(f"Seen {stamp_for(item, tz)}")
    return lines


def hotel_lines(item: dict, role: str | None, tz: str) -> list[str]:
    lines = []
    if role:
        lines.append(f"- {role}: {item['id']} - {money(item['total'])} {item['currency']}")
        lines.append(f"Nightly stay: {money(item['known'])} {item['currency']}")
    elif item["total"] is None:
        lines.append(
            f"Incomplete: {item['id']} - nightly stay {money(item['known'])} - total unknown"
        )
    else:
        lines.append(f"Different currency: {item['id']} - {money(item['total'])} {item['currency']}")
        lines.append(f"Nightly stay: {money(item['known'])} {item['currency']}")
    lines.append(f"rooms: {item['rooms']}")
    if item.get("rating") is not None:
        lines.append(f"Rating: {item['rating']} ({item['rating_count']})")
    if item.get("restrictions"):
        lines.append(str(item["restrictions"]))
    lines.append(str(item["url"]))
    lines.append(f"Seen {stamp_for(item, tz)}")
    return lines


def to_html(markdown: str) -> str:
    body = html.escape(markdown, quote=True)
    return (
        "<!DOCTYPE html>\n<html><head><meta charset=\"utf-8\">"
        "<title>Fare Hawk itinerary</title></head><body><pre>"
        + body
        + "</pre></body></html>\n"
    )


def usable(value):
    if value in (None, "", "skipped", []):
        return None
    return value


def parse_children(raw: str) -> list[int]:
    if not raw.strip():
        return []
    return [int(part) for part in raw.split(",") if part.strip()]


def booking_status(path: Path) -> str:
    if not path.is_file():
        return "planning"
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip() == "Booking status: booked":
            return "booked"
    return "planning"


def build_report(fixture, request, tz: str) -> tuple[str, list[dict]]:
    adults = request["adults"]
    children = request["children"]
    child_count = len(children)
    bags = request["bags"]
    comparison = fixture.get("comparison_currency") or "USD"
    flight_roles, flight_other, flight_eligible = classify_flights(
        fixture.get("flights") or [],
        adults=adults,
        children=child_count,
        bags=bags,
        comparison=comparison,
        max_stops=request["max_stops"],
        arrival_by=request["arrival_by"],
        refundable=request["refundable"],
    )
    hotel_roles, hotel_other, hotel_eligible = classify_hotels(fixture.get("lodging") or [], comparison)
    area = None
    cheapest = hotel_roles.get("Cheapest sensible")
    if cheapest and cheapest.get("neighborhood"):
        area = str(cheapest["neighborhood"])
    elif fixture.get("days"):
        area = str(fixture["days"][0]["neighborhood"])

    lines = [
        DEMO,
        f"Destination: {request['destination']}",
        (
            f"Dates: {weekday_name(request['start'])} {request['start']} to "
            f"{weekday_name(request['end'])} {request['end']}"
        ),
        party_line(adults, children, request["cabin"], bags, request["rooms"]),
        f"Home: {request['origin']}",
        f"Route: {request['origin']}-{fixture.get('destination_code', '')}",
    ]
    if area:
        lines.append(f"Lodging area: {area}")
    lines.append("Watch: on" if request["watch_on"] else "Watch: off")
    lines.append(f"Booking status: {request['booking_status']}")
    if request["assumption"]:
        lines.append(request["assumption"])
    if fixture.get("limitation"):
        lines.append(str(fixture["limitation"]))
    for pair in fixture.get("checked_pairs") or []:
        lines.append(f"Checked: {pair['start']} to {pair['end']}")
    if fixture.get("unchecked_note"):
        lines.append(str(fixture["unchecked_note"]))

    lines.append("## Itinerary")
    for day in fixture.get("days") or []:
        lines.extend(day_lines(day))
        lines.append("")

    lines.append("## Flights")
    for role in ROLES:
        item = flight_roles.get(role)
        if item:
            lines.extend(flight_lines(item, role, adults, child_count, tz, False))
    for item in flight_other:
        incomplete = not item.get("fees_complete", True)
        lines.extend(flight_lines(item, None, adults, child_count, tz, incomplete))
    if len(flight_eligible) < 3:
        lines.append(f"Flight coverage: {len(flight_eligible)} verified options.")

    lines.append("## Lodging")
    for role in ROLES:
        item = hotel_roles.get(role)
        if item:
            lines.extend(hotel_lines(item, role, tz))
    for item in hotel_other:
        lines.extend(hotel_lines(item, None, tz))
    if len(hotel_eligible) < 3:
        lines.append(f"Lodging coverage: {len(hotel_eligible)} verified options.")
    lines.append(FOOTER)
    sources = []
    for item in list(flight_roles.values()) + flight_other:
        sources.append(
            {
                "id": item["id"],
                "kind": "flight",
                "url": item["url"],
                "seen_at": item["seen_at"],
                "seen_at_local": stamp_for(item, tz),
                "departure_local_date": item["depart_date"],
                "arrival_local_date": item["arrive_date"],
            }
        )
    for item in list(hotel_roles.values()) + hotel_other:
        sources.append(
            {
                "id": item["id"],
                "kind": "lodging",
                "url": item["url"],
                "seen_at": item["seen_at"],
                "seen_at_local": stamp_for(item, tz),
            }
        )
    return "\n".join(lines).rstrip() + "\n", sources


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
    data = Path(args.data)
    profile = load_json(data / "state.json")
    dates = profile.get("dates") if isinstance(profile.get("dates"), dict) else {}
    destination = args.dest or usable(profile.get("dest"))
    start = args.start or dates.get("start")
    end = args.end or dates.get("end")
    if not destination or not start or not end:
        print("Which destination and dates?")
        return 2
    party = profile.get("party") if isinstance(profile.get("party"), dict) else {}
    assumed = False
    if args.adults is not None:
        adults = args.adults
    elif party.get("adults") is not None:
        adults = int(party["adults"])
    elif args.assume_one_adult:
        adults = 1
        assumed = True
    else:
        print("How many travelers, adults, and children's ages?")
        return 2
    if args.children is not None:
        children = parse_children(args.children)
    else:
        children = [int(age) for age in (party.get("children") or [])]
    if args.cabin:
        cabin = args.cabin
    elif assumed:
        cabin = "economy"
    else:
        cabin = usable(profile.get("cabin")) or "economy"
    if args.bags is not None:
        bags = args.bags
    else:
        stored_bags = usable(profile.get("bags"))
        bags = int(stored_bags) if stored_bags is not None else 0
    if args.home:
        origin = args.home
    elif isinstance(profile.get("home"), list):
        origin = ",".join(str(code) for code in profile["home"])
    else:
        origin = usable(profile.get("home")) or ""
    if not args.fixtures:
        print("A fixtures file is required.", file=sys.stderr)
        return 2
    fixture = load_fixture(Path(args.fixtures))
    md_path = trip_path(data, slug, f"{slug}.md")
    html_path = trip_path(data, slug, f"{slug}.html")
    assumption = "one adult economy" if assumed else None
    report, sources = build_report(
        fixture,
        {
            "adults": adults,
            "children": children,
            "bags": bags,
            "cabin": cabin,
            "rooms": 1,
            "origin": origin,
            "destination": destination,
            "start": start,
            "end": end,
            "watch_on": profile.get("watch_yes") is True,
            "booking_status": booking_status(md_path),
            "assumption": assumption,
            "max_stops": args.max_stops,
            "arrival_by": args.arrival_by,
            "refundable": args.refundable,
        },
        args.tz,
    )
    atomic_write(md_path, report)
    atomic_write(html_path, to_html(report))
    atomic_write(
        trip_path(data, slug, f"{slug}-sources.json"),
        json.dumps({"sources": sources}, ensure_ascii=False, indent=2) + "\n",
    )

    def save_trip(state: dict) -> None:
        state.update(
            {
                "delivery_status": "recorded",
                "slug": slug,
                "adults": adults,
                "children": children,
                "start": start,
                "end": end,
                "destination": destination,
                "cabin": cabin,
                "bags": bags,
                "rooms": 1,
                "origin": origin,
            }
        )

    mutate_json(trip_path(data, slug, f"{slug}-state.json"), save_trip)

    def save_profile(state: dict) -> None:
        state["setup_complete"] = True

    mutate_json(data / "state.json", save_profile)
    if assumption:
        print(assumption)
    print(md_path.as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
