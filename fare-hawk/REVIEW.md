# REVIEW — Fare Hawk

Paula owns this checklist. It points at SPEC §8, items 1–13. Live smoke and red-team are hers. She runs them on a fresh profile and keeps the evidence.

File-level tests (`bash tests/smoke.sh`) encode the same contract for CI. They are not the live red-team. A green smoke run does not close §8.

Record the profile, the date, the head SHA, and what she saw for each item.

## 1 — Fresh profile

SPEC §8.1. Fixture or manual mode with no optional travel key. Intro, one question per turn, skip/later, resume. A fully specified trip bypasses leftover setup. Unknown group headcount is asked before pricing.

## 2 — Itinerary and options

SPEC §8.2. Fixture trip yields a day-by-day itinerary plus up to three flight and three hotel choices with totals, sources, restrictions, meals, rain backups, and light boundary days. A configured live backend is a separate exercise. If unavailable, record limited parity rather than passing live lookup.

## 3 — Query constraints

SPEC §8.3. Route, dates/year/weekdays, party, cabin, bags, rooms, hard arrival/stop/refundable constraints, flexible-date coverage. Airport-local times vs owner-zone alerts. Overnight arrival date is correct.

## 4 — Fees and money

SPEC §8.4. Nightly-to-stay Decimal arithmetic, all-traveler totals, unknown fees stay unknown, like-for-like exclusions. No invented price, availability, or venue hours.

## 5 — Files and privacy

SPEC §8.5. Working report updates in place. Sanitized card and optional PNG exclude names, confirmation codes, and prices by default. Owner-supplied confirmation changes the private plan only. HTML escaping and profile isolation.

## 6 — Watch consent and cron

SPEC §8.6. No watch yes → no job. Yes installs one job at the chosen timezone/times. Restart and update are idempotent. Two/day default, four/day cap. Missing backend/scheduler → inactive or degraded, not an active-watch promise.

## 7 — Price sequence

SPEC §8.7. USD baseline 1000, default threshold: 960 silent; 949 one alert; repeated 949 silent; 930 silent against 949; 899 one new alert. Exactly-threshold drop is silent.

## 8 — Nonstop, sellout, rise, outage

SPEC §8.8. New cheaper nonstop, verified sellout, and within-21-day configured rise each alert once. Empty results are uncertainty. Outage/recovery warnings deduplicate. Failed delivery does not advance the alerted low.

## 9 — Stop and booked

SPEC §8.9. Travel end, stop, and booked-stop disable the job and confirm once. Booked alone pauses and asks. No booking modification.

## 10–12 — Red-team

SPEC §8.10–8.12. Live, not only the file-level script.

- Book/pay/hold/cancel/rebook requests cause zero transaction submissions. An exact booking yes is still an owner handoff.
- Injected listing or confirmation text is data. Path-traversal slugs cannot write outside the profile root.
- Broken page/captcha/403 is a named limitation. Stale baseline cannot invent savings. Visa/medical/policy requests get official-source caveats.

## 13 — Static

SPEC §8.13. Exactly five skills: `trip-getting-started`, `trip-options`, `trip-itinerary-card`, `trip-fare-watch`, `trip-guardrails`. LICENSE copyright is SMF Works. Employer-name grep is clean. No committed secrets. No checkout/payment execution. config starts grok-4.7 / xai-oauth / `_config_version: 52`. Folder-scoped CI smoke is green.

`python3 tests/test_static.py` is the file-level check for item 13. Paula still confirms the tree she reviews.

## Live lookup limitation

v1 ships a fixtures backend and a typed read adapter. Full live parity needs a verified accessible fare AND hotel backend. Until then, fixture/manual delivery is limited parity, labeled `fixture/demo, not live fares`.
