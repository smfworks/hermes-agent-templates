# Fare Hawk script contract

All scripts live under `fare-hawk/scripts/` and take `--data DIR` (a temp dir in tests) unless noted. Never write to the real `~/.hermes`. Do not call `hermes`. Do not call a model. Do not register a live cron job.

Frozen clock: `--now ISO`. Tests use `NOW=2026-11-06T15:00:00Z` and `TZ=America/New_York` unless a test says otherwise. Every script accepts `--now` and `--tz`. Relative dates use the civil date of `--now` in `--tz`.

Data layout under `--data DIR`:

- `state.json`
- `trips/<slug>.md`
- `trips/<slug>.html`
- `trips/<slug>-card.md`
- `trips/<slug>-card.html`
- `trips/<slug>-card.png`
- `trips/<slug>-prices.csv`
- `trips/<slug>-state.json`
- `trips/<slug>-sources.json`
- `trips/<slug>-private.md`
- `outbox.jsonl`

Slug: lowercase `[a-z0-9-]{1,64}` only. Reject `../`, `/`, null bytes, empty, uppercase, and anything else outside that pattern. Exit 2. No write outside `--data DIR`.

A script that writes `state.json` or `trips/<slug>-state.json` merges into the existing object and leaves keys it does not own. A pre-seeded `sentinel` or `owner_note` stays in place.

CSV: Python `csv` module, quoting `csv.QUOTE_MINIMAL` or `csv.QUOTE_ALL`. Money: `decimal.Decimal` quantized to `0.01` with `ROUND_HALF_EVEN`. Never float. Failed lookup rows have a blank price, never `0`, even when the fixture sends `"price": "0"` on a failed status.

Footer on the working itinerary, its own line: `Try Hermes: Fare Hawk by SMF Works.`

Fixture/demo reports contain, as its own line: `fixture/demo, not live fares`

Owner-local stamps use `--tz`. `America/New_York` prints as `YYYY-MM-DD HH:MM ET` (24-hour, DST-aware). `2026-11-06T15:00:00Z` is `2026-11-06 10:00 ET`. `2026-07-06T15:00:00Z` is `2026-07-06 11:00 ET`.

## Commands

1. `python3 scripts/onboard.py --data DIR --step intro`

   Prints exactly this paragraph (one block, no extra sentence):

   `Tell me where and when. In 10 minutes you'll have a day-by-day itinerary card, 3 flight and hotel options, and a price watch that pings you when fares drop. You book; I watch and report.`

   Sets `setup_step` to `intro_done` in `state.json`. Does not mention cron. The output has at most one `?`.

   If `setup_step` is already set, stdout contains `resume` (any case) and still prints the intro or a short resume prompt. At most one `?`.

2. `python3 scripts/onboard.py --data DIR --step FIELD [--value VALUE] [--skip]`

   `FIELD` is one of: `home` `dest` `dates` `party` `cabin` `bags` `pace` `budget` `interests` `loyalty` `integrations` `threshold` `watch`.

   One field per call. An unknown field exits 2 and stores nothing. Omitting `--value` and `--skip` does not guess a value. At most one `?`. If a choices line is present, it has at most five items when split on `/` or when option-marker lines are grouped. A choices line looks like `Choices: economy / premium / business / first`.

   `--skip` records the field in the `skipped` list and continues. `--value later` does the same.

   Persist after each step.

   - `dest --value Lisbon` stores string `dest`.
   - `home --value BOS` or `BOS,PVD` stores `home` as a list of airport codes.
   - `dates --value 2026-12-10..2026-12-17` stores `dates` as `{"start","end"}`.
   - `dates --value "in 34 days for 7 nights"` resolves in `--tz` from `--now`. From `2026-11-06` in `America/New_York` that is start `2026-12-10` and end `2026-12-17` (start plus the night count).
   - `party --value 2` stores `{"adults": 2, "children": []}`. `2+8+11` stores adults `2` and children `[8, 11]`.
   - `cabin`, `bags`, `pace`, `budget`, `interests` store the given value. `bags` is an integer.
   - `loyalty` stores a list of names only. `--value TAP` stores `["TAP"]`. A value that contains `password`, `passport`, or a run of 13 or more digits is refused: exit 2, the value is not stored, and the distinctive secret is not echoed.
   - `loyalty --skip` stores `loyalty` as `"skipped"` and adds `loyalty` to `skipped`.
   - `integrations --skip` or any value: stdout contains the exact sentence `v1 does not write mail, calendar, or Drive, and it does not execute a booking.`
   - `threshold --skip` stores `{"mode": "default_usd", "amount": "25", "percent": "5"}` (amount and percent may be JSON numbers; tests compare them as decimals) and adds `threshold` to `skipped`.
   - `watch --value yes` stores boolean `watch_yes` true. `--value no` stores false. A threshold is not schedule consent. `watch_yes` false or unset means no job later. This step does not write a jobs file.

   `setup_complete` stays unset until `plan.py` records delivery.

3. `python3 scripts/plan.py --data DIR --slug SLUG --backend fixtures --fixtures PATH [--now ISO] [--tz TZ]`

   Optional trip flags when the fact is not already in `state.json`: `--dest` `--start YYYY-MM-DD` `--end YYYY-MM-DD` `--adults N` `--children AGES` `--cabin` `--bags N` `--home AIRPORTS` `--flex` `--arrival-by HH:MM` `--max-stops N` `--refundable` `--assume-one-adult`.

   Request facts come from the flags, otherwise from `state.json`. The fixture does not supply the request. Defaults when the fact is still missing: cabin `economy`, bags `0`, rooms `1`, children `[]`. There is no `--rooms` flag.

   If dest or dates are missing: exit 2, stdout asks for them, no invented fares, no working report.

   If party/adults are missing and `--assume-one-adult` is absent: exit 2. Stdout asks how many travelers / adults / children's ages. No report.

   `--assume-one-adult` with adults omitted: use 1 adult and cabin economy, and include the exact phrase `one adult economy` in stdout and in the report.

   Backend `fixtures`: read the JSON. No network. Exit 0 on an empty offer list.

   Writes `trips/<slug>.md` and `trips/<slug>.html` in place (overwrite the same paths, no second filename). Preserves `Booking status: booked` when that line is already booked. Does not copy private confirmation text into the working files. Writes `trips/<slug>-state.json` with `delivery_status` `recorded` and the request facts, merging existing keys. Writes `trips/<slug>-sources.json`. Sets `setup_complete` true on `state.json`. Prints a path whose suffix is `trips/<slug>.md`.

4. `python3 scripts/watch_prices.py --data DIR --slug SLUG --backend fixtures --fixtures PATH [--now ISO] [--tz TZ]`

   Reads `trips/<slug>-state.json`. If `watch_yes` is not true, or `paused` is true, or `end` is before the owner-local date: no lookup, no outbox line, no new CSV row, empty stdout or a single `watch inactive` line (travel end may instead say `end`). Exit 0.

   Otherwise this invocation counts as one check. The cap is 4 checks per trip per owner-local date, including this run. The counter is `checks_by_local_date` keyed `YYYY-MM-DD`. A 5th check does not look up, does not increment the counter, does not append CSV rows, and stdout contains `stale`. No `Fare Hawk:` alert.

   Under the cap, read the fixture and apply every observation in order as one check. Append one CSV row per observation. Replay appends the rows again. Alert dedup uses `lowest_alerted` and `last_alert_fingerprint`, not CSV presence.

   Compare with `watch_logic.py`. A qualifying drop, nonstop, sellout, or rise appends one JSON object to `outbox.jsonl` and prints the alert. Update `lowest_alerted` and `last_alert_fingerprint` only when that outbox write succeeds.

   Unchanged or below-threshold: empty stdout (strip to empty), no new outbox line.

   Empty observation (`status` `empty`): stdout contains `availability not confirmed`. Not a sellout. No sellout outbox line.

   Outage: stdout contains `degraded-watch` once for the episode. A later outage observation in the same run is quiet. The next `ok` observation prints `watch recovered` once. A second `ok` in that run does not repeat it.

   `--fail-delivery`: the lookup may append CSV rows, but the script writes no outbox line, does not change `lowest_alerted` or `last_alert_fingerprint`, exits 0, and stdout may contain `retry`. The next successful run of the same qualifying price still alerts once.

   Holds an exclusive `FileLock` (create-exclusive lock file beside the CSV, same approach as other templates' `store.FileLock`) around the CSV read-modify-write. When an observation sets `pause_ms`, sleep that many milliseconds after the lock is held and the current rows are read, before the write.

5. `python3 scripts/watch_logic.py` is a library. Tests insert `scripts/` on `sys.path` and import:

   `from watch_logic import drop_threshold, should_alert_drop, evaluate_observation`

   `drop_threshold(reference: Decimal, currency: str, mode: str) -> Decimal`

   - `default_usd` and currency `USD`: `max(Decimal("25"), Decimal("0.05") * reference)`.
   - `default_usd` and any other currency, with no owner threshold: raise, or return a sentinel that makes `should_alert_drop` return false. A drop of 26 against a reference of 100 must not alert. Do not treat 25 as every currency.
   - `fixed:<amount>` uses that decimal amount. `fixed:40` on any currency is `Decimal("40")`.
   - `percent:<number>` is `reference * number / 100`. `percent:10` on 1000 is 100.
   - `any` is `Decimal("0")`.

   `should_alert_drop(reference, current, currency, mode) -> bool`

   True only when `(reference - current) > drop_threshold(...)`. Equal is false.

   `evaluate_observation(state: dict, obs: dict) -> dict` with keys `alert` (bool), `kind` (`drop|nonstop|sellout|rise|none|outage|recovery|stale|inactive`), `fingerprint` (`str|None`), `reference` (decimal string), `current` (`str|None`). It does not mutate `state`. Priority:

   1. `watch_yes` is not true → `inactive`, `alert` false, `current` null.
   2. `checks_today` >= 4 → `stale`, `alert` false, `current` null.
   3. `status` `outage` and `outage_open` is false → `alert` true, `kind` `outage`, `current` null, non-empty fingerprint.
   4. `status` `outage` and `outage_open` is true → `alert` false, `kind` `outage`.
   5. `status` `ok` and `outage_open` is true → `alert` true, `kind` `recovery`.
   6. `status` `failed` or `empty` → `alert` false, `kind` `none`, `current` null. Empty is not a sellout even if `sellout` is true. A failed `price` of `"0"` still yields `current` null.
   7. Verified sellout (`sellout` and `sellout_verified`) of the same `product_key` → `kind` `sellout`.
   8. `new_nonstop` and `nonstop`, fees complete, same currency and cabin, price strictly below the reference → `kind` `nonstop`. The drop threshold does not apply. A different `product_key` is allowed for this kind.
   9. Owner-local civil date of `state["now"]` in `state["tz"]` is within 21 days of `state["departure"]` (0 through 21 inclusive) and `(current - baseline) > drop_threshold(baseline, ...)` on a like-for-like product → `kind` `rise`. Rise uses `baseline`, not `lowest_alerted`.
   10. Like-for-like drop where `should_alert_drop` is true → `kind` `drop`. Reference is `lowest_alerted` when set, otherwise `baseline`.
   11. Otherwise `kind` `none`.

   Like-for-like requires the same currency, the same cabin, fees complete, and the same room when both sides have a room. A different currency, cabin, room, or incomplete fees does not produce a drop, rise, or nonstop savings alert.

   When `alert` is true, `fingerprint` is a non-empty string. The same inputs produce the same fingerprint. Drop, nonstop, sellout, and rise fingerprints differ. If `last_alert_fingerprint` equals that fingerprint, `alert` is false.

6. `python3 scripts/install_cron.py --data DIR --slug SLUG --jobs PATH [--yes|--no] [--tz TZ] [--times 06:07,18:07] [--stop] [--booked] [--booked-stop]`

   Does not call `hermes`.

   With none of `--yes`, `--stop`, `--booked`, `--booked-stop`: writes no jobs.

   `--no`: writes no jobs. Sets `watch_yes` false on `state.json` and on the trip state.

   `--yes`: writes exactly one job named `fare-hawk-watch-<slug>`. A second `--yes` with the same args does not duplicate it. Other job names in the file stay. The file is `{"jobs": [ ... ]}` (a bare list is accepted on read). Each job has `name`, `schedule`, and `timezone`. `schedule` is either the string `7 6,18 * * *` or `{"expr": "7 6,18 * * *"}`. `timezone` comes from `--tz`, default `America/New_York`. Sets trip `watch_yes` true, `paused` false, merging other trip keys.

   `--stop`: removes that job, sets `watch_yes` false, prints one confirmation containing `stopped`. A later `watch_prices.py` does not look up. Stop stays in effect until a later `--yes`.

   `--booked`: does not remove the job. Sets `paused` true on the job and the trip state. Stdout contains `?` and `stop`. `watch_prices.py` does not look up while paused.

   `--booked-stop`: removes the job the same way `--stop` does.

7. `python3 scripts/card.py --data DIR --slug SLUG [--png]`

   Writes `trips/<slug>-card.md` and `trips/<slug>-card.html` in place.

   Keeps, from the working markdown:

   - lines that start with `Destination:`, `Dates:`, `Party:`, `Lodging area:`, or `Watch:`
   - the `## Itinerary` section through the line before the next `## ` heading

   Drops every other line, including flights, lodging prices, `Traveler:`, `Confirmation:`, and `Booking status:`.

   The default card has no traveler names, confirmation codes, prices, currency amounts, or `$`. The working `trips/<slug>.md` may still contain prices.

   HTML escapes `& < > " '` the way `html.escape` does (`&amp; &lt; &gt; &quot; &#x27;`). No `<script`, no `iframe`, no `onerror`.

   `--png` writes `trips/<slug>-card.png` starting with the PNG magic bytes `\x89PNG`. Render from the sanitized card only.

8. `python3 scripts/confirm.py --data DIR --slug SLUG --text TEXT`

   Appends `TEXT` to `trips/<slug>-private.md`. Does not fetch mail.

   If `TEXT` contains `confirmation` (any case), replace the working itinerary line with `Booking status: booked` in the markdown and the HTML. Do not copy the raw text, traveler names, or confirmation codes into the working files or the share card. Other pasted text is private-only and leaves `Booking status: planning` in place.

9. `python3 scripts/guard.py --mode MODE [--text TEXT]`

   Modes: `book_if_dips` | `you_have_my_card` | `hold_deposit` | `cancel_rebook` | `selected_option` | `watch_consent` | `exact_booking_yes` | `inject_listing` | `inject_confirmation` | `path_traversal` | `visa_eligibility` | `captcha_403` | `stale_baseline` | `secrets_solicit`

   All exit 0 with non-empty stdout. Never print a planted canary. Never claim a booking, payment, cancel, or change was submitted.

   - `exact_booking_yes`: stdout says the owner finishes booking, or handoff, or `you book`.
   - `you_have_my_card`: does not echo a card number.
   - `secrets_solicit`: does not ask for a passport, password, or card.
   - `inject_listing` and `inject_confirmation`: treat the text as data. Stdout contains `data`, `not followed`, or `reported`.
   - `path_traversal`: refuses the slug.
   - `captcha_403`: names the limitation. No workaround and no credential ask.
   - `stale_baseline`: no fake savings figure.
   - `visa_eligibility`: points at an official source and does not guarantee eligibility.

## Money

USD `default_usd`, baseline 1000:

| Current | Result |
| --- | --- |
| 960 | silent (drop 40, threshold 50) |
| 949 | one alert (drop 51 > 50); `lowest_alerted` becomes 949 |
| 949 again | silent |
| 930 | silent against 949 (drop 19, threshold `max(25, 47.45)` = 47.45) |
| 899 | one new alert (drop 50 > 47.45) |
| 950 against baseline 1000 | silent (drop 50 == threshold 50) |

`drop_threshold(Decimal("1000.10"), "USD", "default_usd")` is `Decimal("50.005")`. A drop equal to the threshold is silent.

`fixed:40`: threshold 40, so a drop of 40 is silent and a drop of 41 alerts. `percent:10` on 1000: a drop of 100 is silent and 100.01 alerts. `any`: any strict decrease alerts; an equal price does not.

Flight all-in total, quantized once at the end:

`fare_per_adult * adults + fare_per_child * children + bag_fee_each * bags + taxes`

Also show `All travelers: {fare_per_adult * adults + fare_per_child * children} CURRENCY`.

Lodging, when `fees_complete` is true and `resort_fee_per_night` is not null:

`Nightly stay` = `(nightly + resort_fee_per_night) * nights * rooms`

`total` = that stay plus `taxes`, then quantize.

A null resort fee or `fees_complete` false: show the known `nightly * nights * rooms` as `Incomplete: ID - nightly stay AMOUNT - total unknown`. The word `unknown` is required. Do not treat the fee as 0. That option gets none of the three role labels.

Example: nightly `100.10`, nights 7, rooms 1, resort `0.00`, taxes `2.675` → nightly stay `700.70`, all-in `703.38`. The report contains `703.38` and does not contain `703.37` or `700.699999`.

Different currency, different cabin, different room, or incomplete fees cannot produce a savings alert against the baseline product. A verified different-currency option is still shown as `Different currency: ID - AMOUNT CURRENCY`.

## Report shape

Successful `plan.py` writes both files with:

- `Destination: {dest}`
- `Dates: {Weekday} {start} to {Weekday} {end}` using the civil weekday of each date
- `Party: {N adults|1 adult}, {0 children|children 8, 11}. Cabin: {cabin}. Bags: {bags}. Rooms: {rooms}.`
- `Home: {origin}`
- `Route: {origin}-{destination_code}`
- `Lodging area: {neighborhood}` from the cheapest sensible hotel when one exists, otherwise the first day
- `Watch: on` or `Watch: off`
- `Booking status: planning` until `confirm.py` sets `booked`
- `## Itinerary`, `## Flights`, `## Lodging`
- one block per fixture day:

```
### {Weekday} {date} - {neighborhood}[- light]
- {anchor}
Meal: {meal}
Signature meal: {meal}
Rain backup: {rain}
Hours: {hours}
```

` - light` is added only when `pace` is `light`. `Signature meal` replaces `Meal` when `signature` is true. `Hours: confirm before you go.` is the line when `hours` is null. Copy a non-null hours string. Do not invent a venue that is not in the fixture.

Role line, one per assigned role, only for eligible same-currency complete options:

`- Cheapest sensible: {id} - {total} {currency}`

Same form for `Best value` and `Most comfortable`.

Assignment, after hard filters:

- lowest total, then lowest id, is `Cheapest sensible`
- when at least two remain, the highest `comfort` among the rest, then lowest id, is `Most comfortable`
- when at least three remain, the leftover option is `Best value`
- never give two roles to one option
- never invent a missing role
- when a category has fewer than three eligible options, the report contains `coverage`

Each shown flight also includes `Depart AIRPORT DATE HH:MM LABEL`, `Arrive AIRPORT DATE HH:MM LABEL`, the IANA zone names, the restrictions string, the source URL, and the owner-local seen stamp. Arrival date is the fixture `arrive_date` (an overnight flight keeps the next local date).

Each shown hotel includes `rooms: N`, restrictions, URL, and the seen stamp.

`trips/<slug>-sources.json`:

```json
{
  "sources": [
    {
      "id": "TP-CHEAP",
      "kind": "flight",
      "url": "https://fixtures.example/flights/tp-cheap",
      "seen_at": "2026-11-06T15:00:00Z",
      "seen_at_local": "2026-11-06 10:00 ET",
      "departure_local_date": "2026-12-10",
      "arrival_local_date": "2026-12-10"
    }
  ]
}
```

Every shown flight or hotel has an entry. Hard-constraint drops are omitted. `seen_at_local` matches the owner stamp of `seen_at`.

Flexible fixtures copy each `Checked: {start} to {end}` line and the `unchecked_note` verbatim.

A fixture `limitation` string is copied verbatim. An empty offer list still exits 0, names that limitation, and contains no role label and no `NNN.NN` price.

Hard constraints, applied before ranking: `stops` greater than `--max-stops` are dropped; `arrive_hhmm` later than `--arrival-by` is dropped (`HH:MM` string order, equal times stay); `--refundable` drops non-refundable flights. An equal arrival time is kept.

## prices.csv

Header, in this order:

```
seen_at,status,price,currency,source,link,notes,product_key
```

`status` is `ok`, `failed`, `empty`, or `outage`. `price` is the two-decimal amount only when `status` is `ok` and the observation has a price. Otherwise the price field is empty. `notes` is copied from the observation, including commas, quotes, and newlines, so `csv.DictReader` returns the same string.

## Trip state and outbox

`install_cron.py --yes` and `watch_prices.py` share `trips/<slug>-state.json`. Watch fixtures supply the display fields (`route`, `party`, `details`, `source`, `link`, `baseline`, `currency`, `cabin`, `room`, `product_key`, `departure`). The trip state supplies `watch_yes`, `paused`, `baseline` when set, `lowest_alerted`, `last_alert_fingerprint`, `threshold_mode`, `outage_open`, `checks_by_local_date`, and `end`.

An outbox line is one JSON object:

```json
{"slug": "lisbon", "kind": "drop", "fingerprint": "...", "reference": "1000.00", "current": "949.00", "body": "..."}
```

`body` contains the same alert text as stdout. `current` is null when the event has no price.

## Alert shape

Stdout when a drop alert fires:

```
Fare Hawk: {route} dropped {amount} {currency}
{details}, {party}: {reference} → {current}
Seen {owner-local time} on {source} · lowest alerted since watch began
{link} · You book; total may change at checkout.
```

Amounts are two-decimal strings. The seen time is the observation `seen_at` rendered in `--tz`, not a second conversion of airport-local clocks. `2026-11-06T15:01:00Z` in `America/New_York` is `2026-11-06 10:01 ET`.

Nonstop stdout contains `nonstop`. Sellout stdout contains `sellout` or `sold out`. Rise stdout contains `rise`. Those kinds use their own fingerprints.

## Watch observation

Top-level fixture fields are the defaults. Each object in `observations` may override them.

`status`: `ok`, `failed`, `empty`, or `outage`.

Flags: `nonstop`, `new_nonstop`, `sellout`, `sellout_verified`, `fees_complete`, `pause_ms`.

`price` is a decimal string or null. `seen_at` is an ISO timestamp.

## Guard output

Stdout must not claim the action happened. These phrases are claims: `i booked`, `booked it`, `booked for you`, `have booked`, `successfully booked`, `booking submitted`, `checkout submitted`, `i submitted`, `submitted your`, `submitted the booking`, `submitted a booking`, `submitted payment`, `payment submitted`, `you were charged`, `card was charged`, `i charged`, `charged your`, `i cancelled`, `i canceled`, `cancelled for you`, `canceled for you`, `have cancelled`, `i paid`, `paid for you`, `payment sent`, `reservation placed`, `hold placed`, `deposit submitted`.

`you book` is the handoff phrase and is not a claim that a booking was submitted.
