# Fare Hawk

Fare Hawk by SMF Works. Name a place and dates. You get a day-by-day itinerary, three flight options and three hotel options, then an opt-in price watch. You book. It watches and reports.

SMF Works publishes this template under the MIT license.

## Install

From a checkout of this repository, install this folder:

```bash
hermes profile install ./fare-hawk --name fare-hawk-dev --alias
```

`fare-hawk-dev` is the development profile name. The distribution name is `fare-hawk`. Hermes Agent 0.22.0 or newer.

## After install

Copy `templates/USER.md` and `templates/MEMORY.md` into the profile `memories/` directory. Placeholders are not an onboarding record. Keep non-secret preferences only. Loyalty entries are program names only. Keep card numbers, passport numbers, passwords, and confirmation codes out of memory and out of chat.

Trip files live under `trips/` inside the profile data directory. Scripts take `--data` pointed at that directory. The working itinerary is `trips/<slug>.md` and `trips/<slug>.html`, overwritten in place. The share card is `trips/<slug>-card.md` and `trips/<slug>-card.html`. There is no hosted page.

The first conversation asks where and when, then one question at a time (at most five choices). Skip and later are supported. Itinerary and options run as soon as destination, dates, and party are known.

The shipped `config.yaml` starts a model with `grok-4.7` and `provider: xai-oauth`. After install, copy `.env.EXAMPLE` to the profile `.env` and replace the placeholder:

```bash
cp fare-hawk/.env.EXAMPLE ~/.hermes/profiles/fare-hawk-dev/.env
chmod 0600 ~/.hermes/profiles/fare-hawk-dev/.env
# Open that file and set: XAI_API_KEY=<paste-key-here>
```

If `hermes auth status xai-oauth` is already logged in, the placeholder may stay empty and the first chat should start. To point at a different provider instead:

```bash
hermes --profile fare-hawk-dev config set model.default <model>
hermes --profile fare-hawk-dev config set model.provider <provider>
```

Do not copy a host-local endpoint into this folder.

## Fixture mode

Optional travel-provider keys are not required. With no travel key, planning and watch checks use fixtures or a manual paste. Those reports say `fixture/demo, not live fares`. A configured read adapter, when present, supplies live flight and hotel reads. Absent travel keys are a stated limitation.

## v1 booking

The owner books. v1 stays read-only even after an explicit booking yes: Fare Hawk provides the exact source link, and the owner finishes booking. There is no checkout.

## Capability matrix

| Capability | v1 |
| --- | --- |
| Flights | Fixtures, manual paste, or a configured read adapter |
| Hotels | Fixtures, manual paste, or a configured read adapter |
| Price watch | Opt-in cron job `fare-hawk-watch-<slug>`, schedule `7 6,18 * * *`, owner-local timezone, `--script` and `--no-agent` |
| Mail | Not in v1 |
| Calendar | Not in v1 |
| Drive | Not in v1 |
| Hosted pages | None. Local working files and a local share card only |
| Checkout | None. The owner books |

The profile tools are file, memory, skills, clarify, cronjob, todo, and web. No browser. No delegation.

## Skills

- `trip-getting-started`
- `trip-options`
- `trip-itinerary-card`
- `trip-fare-watch`
- `trip-guardrails`

## Tests

From this directory:

```bash
bash tests/smoke.sh
```

That runs the file-level contract tests. It does not call a model.

## Provenance

Public bot, plus the Charlie spec of 2026-11-06. Source skill files were not on the build host. The five skills here state that spec. They are not a verbatim copy of those source files.

Attribution: SMF Works. License: MIT.
