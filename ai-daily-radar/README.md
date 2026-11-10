# AI Daily Radar

AI Daily Radar (Radar) sends one short morning brief of up to 7 AI changes that matter to your stack. Each item has exactly one evidence tag and a primary link. Radar reads and reports. It never posts, emails other people, or buys anything.

SMF Works publishes this template under the MIT license.

## Install

From a checkout of this repository:

```bash
hermes profile install ./ai-daily-radar --name radar-dev --alias
```

`radar-dev` is the development profile name. The distribution name is `ai-daily-radar`. Hermes Agent 0.22.0 or newer.

## After install

Copy `templates/USER.md` and `templates/MEMORY.md` into the profile `memories/` directory. Keep non-secret preferences only. Never put a password, a code, or an API key in memory or in chat.

Briefs live under the profile data directory `briefs/`. Friday wraps live under `wraps/`. There is no hosted link.

The profile tools are file, memory, skills, clarify, cronjob, todo, and web. Web search discovers URLs. The page-extract tool reads a page. A search snippet is a lead, not evidence. No browser. No delegation.

The first conversation is the intro, then one setup question at a time. A sample brief for the last 24 hours is offered once answers are in.

The shipped `config.yaml` starts a model with `grok-4.7` and `provider: xai-oauth`. After install, copy `.env.EXAMPLE` to the profile `.env` and replace the placeholder if you want a live research key. Fixture smoke does not need that key:

```bash
cp ai-daily-radar/.env.EXAMPLE ~/.hermes/profiles/radar-dev/.env
chmod 0600 ~/.hermes/profiles/radar-dev/.env
```

If `hermes auth status xai-oauth` is already logged in, the placeholder may stay empty and the first chat should start. To point at a different provider instead:

```bash
hermes --profile radar-dev config set model.default <model>
hermes --profile radar-dev config set model.provider <provider>
```

Do not copy a host-local endpoint into this folder.

Without a search backend, Radar says it cannot build a live brief and offers fixture/demo mode, labeled "fixture/demo, not live news". Documented Hermes tool names after checking this install: `web` toolset (search + page extract), `file`, `memory`, `skills`, `clarify`, `cronjob`, `todo`.

Daily Brief and Monthly Tune-Up stay off until an explicit yes. Tested commands:

```bash
hermes cron create "0 7 * * *" --name radar-daily-brief --timezone America/New_York --script scripts/brief.py --no-agent
hermes cron create "0 7 * * 1" --name radar-monthly-tuneup --timezone America/New_York --script scripts/monthly.py --no-agent
```

Pass the timezone stored in `profile.json`. Without a working scheduler or gateway, CLI and manual runs still work and the gap is explicit.

## Skills

- `radar-getting-started`
- `radar-evidence-tagging`
- `radar-ai-news-dedup`
- `radar-brief-formatting`

## Tests

From this directory:

```bash
bash tests/smoke.sh
```

That runs the file-level contract tests. It does not call a model. If `grok` is missing, smoke prints that you should install Grok Build or use Cursor, Claude Code, or Codex, then continues. It does not switch to another build CLI.

Liam owns the live smoke and the red-team in SPEC §8. The file-level tests are not the live red-team.

Public bot this template tracks: https://x.ai/bot/EZ8RChmm9gSGmK3SXv-3M
