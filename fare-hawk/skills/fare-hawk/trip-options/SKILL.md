---
name: trip-options
description: >-
  Use to show up to three flights and three lodging options with all-in totals,
  fees, restrictions, source links, and a seen-at time.
---
# Fare Hawk options

Show three real flight choices and three real lodging choices when the sources have them. Roles, one each, and only for eligible same-currency options with complete fees:

- Cheapest sensible
- Best value
- Most comfortable

Assign from the owner's constraints and the actual totals. One option gets one role. When a category has fewer than three eligible options, show the ones you have and say what the coverage is. Leave an empty role off the report. Invent no slot, no fare, and no venue.

## What a shown option carries

Flights: carrier and flight numbers, airports, airport-local departure and arrival dates and times with zone labels, duration, stops, layovers, cabin and fare, baggage and change terms, total, and currency. Be candid about layovers, red-eyes, and fees.

Lodging: property, room, and rate, location, rooms, guests, nights, rating and review count when the source has them, cancellation deadline, check-in and check-out, all-in total, and currency.

Each shown option includes the source link and the seen-at time. A price is "seen at [time] on [source]; may change." Search snippets and calendar "from" prices are leads, not current bookable totals.

Totals cover all travelers, all rooms, and all nights, including taxes and known fees. Basic economy, bags, resort fees, cleaning fees, and cancellation terms stay visible. A missing fee is missing, not free and not zero. An incomplete total stays out of the all-in ranking and out of watch comparisons.

Compare like for like: same currency, same cabin, same room when both sides name a room, and complete fees. Show a verified different-currency option as a different currency. Do not convert currency unless you have a dated sourced rate. Prefer the same currency.

There is no promise of a price lock or of seat inventory. Verify the airline or property direct rate when that page is available, and say what the rate includes.

An empty or blocked source is a named limitation. Offer one documented alternative read or a manual paste. One empty result is not a claim that the route or the property is unavailable. Stay inside the source's rate and access limits.

Apply hard constraints before ranking: stop limit, arrival deadline, accessibility, and refundable when the owner required them.

## Hermes (this template)

Tool names only. The rules above do not change.

- `skill_view` loads `trip-options` and `trip-guardrails`.
- `web` reads public flight, lodging, and official pages. `file` writes `trips/<slug>.md`, `trips/<slug>.html`, and `trips/<slug>-sources.json` under `--data`.
- `scripts/plan.py --data DIR --slug SLUG` writes those working files in place.
- Profile tools: `file`, `memory`, `skills`, `clarify`, `cronjob`, `todo`, `web`.
- No browser. No delegation. No terminal tool.
