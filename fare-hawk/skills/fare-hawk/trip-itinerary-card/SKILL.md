---
name: trip-itinerary-card
description: >-
  Use to write the day-by-day itinerary and the local share card: neighborhood
  anchors, meals, rain backups, and hours, with private fields kept off the card.
---
# Fare Hawk itinerary and card

Build the days by neighborhood. Balanced pace is two or three anchors a day, plus a rain backup and a meal. A signature meal replaces the ordinary meal line when the day calls for one. Keep the arrival day and the departure day light.

Verify opening days and hours on the official venue page. When hours are unknown, the line is `Hours: confirm before you go.` Copy a sourced hours string. Invent no venue that is absent from the source. Label travel time as an estimate unless a source gives it.

The working itinerary names destination, dates with weekdays, and party. It includes lodging neighborhood and night allocation, booking status, watch status, and the last successful check time. Footer, on its own line: `Try Hermes: Fare Hawk by SMF Works.`

Overwrite `trips/<slug>.md` and `trips/<slug>.html` in place. These are owner-private working files. They are not a hosted page.

After the owner supplies a booking change, update that same local itinerary. Confirmation text goes in `trips/<slug>-private.md` only, from text the owner supplied. Mail import is deferred. The working files may show `Booking status: booked` after that paste. They do not gain the raw confirmation, traveler names, or confirmation codes.

## Share card

Write `trips/<slug>-card.md` and `trips/<slug>-card.html` in place from the day plan, destination, dates, party count, lodging area, and watch status. Traveler names, confirmation codes, and prices stay off the card unless the owner asks for a chosen field.

HTML inserts source text escaped. The card page has no active embed. An optional `trips/<slug>-card.png` renders the sanitized card only. Uploading that image is a separate owner decision, and v1 does not upload it.

Chat returns a short finding and the local paths.

## Hermes (this template)

Tool names only. The rules above do not change.

- `skill_view` loads `trip-itinerary-card` and `trip-guardrails`.
- `web` reads official venue and government pages. `file` overwrites the working itinerary and the card under `--data`.
- `scripts/plan.py` writes `trips/<slug>.md` and `trips/<slug>.html`.
- `scripts/card.py` writes `trips/<slug>-card.md` and `trips/<slug>-card.html`.
- `scripts/confirm.py` appends `trips/<slug>-private.md`.
- Seeds: `templates/itinerary.html` and `templates/card.html`.
- Profile tools: `file`, `memory`, `skills`, `clarify`, `cronjob`, `todo`, `web`.
- No browser. No delegation. No terminal tool.
