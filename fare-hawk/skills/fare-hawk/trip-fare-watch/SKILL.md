---
name: trip-fare-watch
description: >-
  Use for the opt-in price watch: same-source rechecks, qualifying alerts,
  and a stop when travel ends or the owner says stop.
---
# Fare Hawk price watch

The watch is opt-in per trip. Ask permission for a twice-daily check and the timezone. Suggest 06:07 and 18:07 owner-local time. A threshold is not schedule consent. Record the cron job id only after installation succeeds. The job name is `fare-hawk-watch-<slug>`. The schedule is `7 6,18 * * *`. The default is two checks a day. The ceiling is four checks per trip per day, including a manual or retry check. After the quota, label the last-seen data stale and wait for the next allowed check.

Re-check the exact watched set, or a comparable set, on the same source. Append every actual observation. Notify only on a qualifying change. An unchanged check sends no chat message.

## What to store

For each watch, keep the source and query, the comparable-set key, currency, total basis, exact dates, travelers, rooms, bags, cabin, rate terms, baseline total, lowest successfully alerted price, last observation, last alert fingerprint, status, and stop date. A comparable-key change resets the baseline only after you explain the change. Savings stay inside one product, one currency, and one fee coverage.

Append observations to `trips/<slug>-prices.csv`. A failed lookup is its own status row with a blank price. A blank price is not zero, and it is not the previous price. Use decimal arithmetic. Infer no fare movement from a failed request.

## When to alert

Reference price is the lowest successfully alerted price. Before the first alert, the reference is the baseline.

USD default: the drop is strictly greater than the larger of 25 USD and 5 percent of the reference total. The owner may choose a fixed amount in their currency, a percent, or any decrease. For a non-USD default, ask for a threshold in that currency, or use a disclosed sourced FX conversion. 25 is not every currency.

Also alert, each with its own fingerprint:

- A new cheaper verified nonstop that meets the constraints. The drop threshold does not apply to that kind.
- A verified sellout of the chosen option. A missing search result is "availability not confirmed," not a sellout.
- A significant rise within 21 days of departure. v1 rise policy: the increase is strictly above the owner's rise threshold (default the same amount or percent rule) versus the baseline, inside that window. Say that this rise rule is the configured policy. Predict no future price.

Like-for-like means the same currency, the same cabin, the same room when both sides have a room, and complete fees. A different currency, cabin, room, or incomplete fees produces no savings alert.

Update the last-alert state only when private delivery succeeds. A failed delivery retries the same qualifying price once on the next success. An outage produces one degraded-watch warning for that episode, then quiet retries at the normal cadence. Recovery is reported once.

## Alert text

```
Fare Hawk: <route/property> dropped <amount currency>
<flight/room and dates>, <party>: <reference> → <current total>
Seen <owner-local time + zone> on <source> · lowest alerted since watch began
<exact search/listing link> · You book; total may change at checkout.
```

Label airport-local times by airport and zone. Alert and check timestamps use the owner timezone. A failed check shows current status and the last successful check separately.

## Stop

Stop before another lookup after the travel end date, when the owner says stop, or on "booked, stop." Remove the job and confirm once. "Booked" alone asks whether to stop. Until the owner answers, the planning watch pauses.

A post-booking reprice check is a new opt-in. Read the airline or property policy and report a possible credit with the source. The owner decides and performs any change. The watch never changes a reservation.

## Hermes (this template)

Tool names only. The rules above do not change.

- `skill_view` loads `trip-fare-watch` and `trip-guardrails`.
- `cronjob` installs, updates, and removes `fare-hawk-watch-<slug>` with `--script`, `--no-agent`, schedule `7 6,18 * * *`, and the owner timezone.
- `scripts/watch_prices.py --data DIR --slug SLUG` performs one check.
- `scripts/watch_logic.py` compares a price to the threshold.
- `scripts/install_cron.py` writes the jobs file and does not call hermes.
- `web` reads the configured source page when a live read adapter is in use. `file` appends `trips/<slug>-prices.csv` and updates `trips/<slug>-state.json`.
- Profile tools: `file`, `memory`, `skills`, `clarify`, `cronjob`, `todo`, `web`.
- No browser. No delegation. No terminal tool.
