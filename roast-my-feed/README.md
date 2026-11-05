# Roast My Feed

Roast My Feed takes a public X handle and writes a Wrapped-style audit: archetype, best post, worst habit, a 7-day plan, and 3 posts drafted in that voice. Witty, never cruel, and every number is real. No X login.

SMF Works publishes this template under the MIT license.

## Install

From a checkout of this repository:

```bash
hermes profile install ./roast-my-feed --name roast-my-feed-dev --alias
```

`roast-my-feed-dev` is the development profile name. The distribution name is `roast-my-feed`. Hermes Agent 0.22.0 or newer.

## After install

Copy `templates/USER.md` and `templates/MEMORY.md` into the profile `memories/` directory. Placeholders are not an onboarding record. Keep non-secret preferences only. Keep X passwords, bearer tokens, and post bodies out of memory and out of chat.

The handle, timezone, history, and reports live under the profile data directory: `state.json`, `history.jsonl`, and `roast/<handle>/`. There is no hosted link.

The profile tools are file, memory, skills, clarify, cronjob, and todo. It has no terminal tool and no web tool. Drafts and a share card only.

The first conversation is the short intro, then the handle, then the audit and report before any other question. After the report, offer a weekly Monday re-roast. Cron installs only on an explicit yes.

The shipped `config.yaml` starts a model with `grok-4.7` and `provider: xai-oauth`. After install, copy `.env.EXAMPLE` to the profile `.env` and replace the placeholders:

```bash
cp roast-my-feed/.env.EXAMPLE ~/.hermes/profiles/roast-my-feed-dev/.env
chmod 0600 ~/.hermes/profiles/roast-my-feed-dev/.env
# Open that file and set: XAI_API_KEY=<paste-key-here>
# For live X reads, also set: X_BEARER_TOKEN=<paste-bearer-here>
```

Prefer the Hermes secret store for `X_BEARER_TOKEN`. If `hermes auth status xai-oauth` is already logged in, the `XAI_API_KEY` placeholder may stay empty and the first chat should start. To point at a different provider instead:

```bash
hermes --profile roast-my-feed-dev config set model.default <model>
hermes --profile roast-my-feed-dev config set model.provider <provider>
```

Do not copy a host-local endpoint into this folder.

## X reads

Live reads use the X API v2 with an app-only Bearer token. GET only:

| Endpoint | Per app (Bearer) |
| --- | --- |
| `GET /2/users/by/username/:username` | 300 requests / 15 min |
| `GET /2/users/:id/tweets` | 10,000 requests / 15 min |
| `GET /2/tweets/search/recent` | 450 requests / 15 min |

The per-app column applies to the app-only Bearer. Per-user limits apply to user tokens, which this template does not use. Recent search returns posts from about the last 7 days (10 by default, 100 max). The user timeline is the read that can cover a 30-day window. Search (`from:<handle> -is:retweet`) is the fallback. One audit is one user lookup plus pages of posts, stopping at 20 pages (about 500 posts).

Pricing is pay-per-usage. Buy credits in the X developer console. There is no self-serve subscription tier on the current pricing page. Enterprise is the higher-volume option. Published read prices: posts $0.005 per resource, users $0.010 per resource. A capped audit of one user plus about 500 posts is about $2.51 before dedupe. A quieter week costs less. A 30-day rerun reads more posts and costs more. The same resource requested again inside a 24-hour UTC window is charged once. Pay-per-usage plans cap at 3 million post reads per monthly billing cycle. Prices can change. The developer console is the current card. Rate limits and billing are separate. See [the X API rate limits](https://docs.x.com/x-api/fundamentals/rate-limits) and [the X API pricing page](https://docs.x.com/x-api/getting-started/pricing).

Chat uses `grok-4.7` through `xai-oauth`. That usage is separate from the X API credit balance.

With no `X_BEARER_TOKEN`, use the fixtures JSON backend, or pass an X archive export (`tweets.js`). The no-token path tells the owner how to add the Bearer token. It does not print the token.

## Cron

Install `roast-weekly-checkin` only after an explicit yes. Monday 09:00 in the owner's timezone. Store that IANA name in `state.json` (default `America/New_York`) and pass it to `--timezone`, so the local hour stays put across DST.

```bash
hermes cron create "0 9 * * 1" --name roast-weekly-checkin --timezone America/New_York --script scripts/audit.py --no-agent
```

`--script` with `--no-agent` runs the audit script and delivers its stdout. The script does not call a model.

## Skills

- `roast-getting-started`
- `roast-audit`
- `roast-guardrails`

## Scripts

Cron runs the audit with `--script` and `--no-agent`. Tests call `python3 scripts/...`. They do not call a model. `--data` is the profile data directory.

- `scripts/onboard.py` walks `setup_step`.
- `scripts/x_read.py` reads public posts (fixtures, live Bearer, or a `tweets.js` archive).
- `scripts/roast_metrics.py` counts the metrics.
- `scripts/audit.py` overwrites `roast/<handle>/roast.md` and `roast.html` and appends `history.jsonl`.
- `scripts/card.py` writes `roast/<handle>/card.png`.
- `scripts/install_cron.py --yes` records `roast-weekly-checkin`. It does not register a live job.
- `scripts/guard.py` answers a guardrail check.

## Tests

From this directory:

```bash
bash tests/smoke.sh
```

That runs the file-level contract tests. It does not call a model. If `grok` is missing, smoke prints that you should install Grok Build or use Cursor, Claude Code, or Codex, then continues. It does not switch to another build CLI.

Paula owns the live smoke and the red-team in SPEC §8. The file-level tests are not the live red-team.
