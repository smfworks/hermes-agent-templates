# Daily Wisdom

Daily Wisdom sends one short reading each morning, from the Stoics, classical philosophy, or a faith tradition, with one sentence of context and one question to carry through the day.

SMF Works publishes this template under the MIT license.

## Install

From a checkout of this repository:

```bash
hermes profile install ./daily-wisdom --name daily-wisdom-dev --alias
```

`daily-wisdom-dev` is the development profile name. The distribution name is `daily-wisdom`. Hermes Agent 0.22.0 or newer.

## After install

Copy `templates/USER.md` and `templates/MEMORY.md` into the profile `memories/` directory. Placeholders are not an onboarding record. Keep non-secret preferences only. Never put a password, a code, an API key, or a private journal note in memory or in chat.

Sittings, notes, and state live under the profile data directory `wisdom/`. The weekly page is a markdown file and an HTML file there. There is no hosted link.

No connectors. A calendar reminder is out of scope. The profile tools are file, memory, skills, clarify, cronjob, and todo. It has no terminal tool and no web tool.

The first conversation is a short intro, today's sitting, then three onboarding questions, one at a time. Skip keeps the default. Onboarding then installs cron jobs named `daily-wisdom-sitting` and `daily-wisdom-weekly` as script jobs (`cron_sitting.sh` / `cron_weekly.sh`, `--no-agent`). Hermes assigns a 12-character hex job id; you cannot choose it. Match the jobs by those names.

The shipped `config.yaml` names `grok-4.7` with `provider: auto`. A fresh profile has no provider credentials, so the first session can fail with `invalid_params`. Before the first chat, the operator must wire a working model:

```bash
hermes --profile daily-wisdom-dev config set model.default <model>
hermes --profile daily-wisdom-dev config set model.provider <provider>
```

Do not copy a host-local endpoint into this folder. Operator wiring on a throwaway live profile is not what the template ships.

## Skills

- `wisdom-getting-started`
- `wisdom-daily-sitting`
- `wisdom-weekly-page`
- `wisdom-guardrails`

## Scripts

Cron runs these with `--script` and `--no-agent`. They do not call a model. `--data` is the profile `wisdom/` directory. The public-domain corpus is `data/readings.json`.

- `scripts/sitting.py` prints today's sitting and appends `sittings.csv` with every field quoted. Same-day rerun reprints the logged sitting. A missed day writes streak 0.
- `scripts/reply.py` prints exactly `Thank you. That one line is enough.`, appends `notes.md`, and updates the streak.
- `scripts/weekly.py` overwrites `what-changed-in-me.md` and `what-changed-in-me.html`.
- `scripts/quote_card.py` prints that day's reading and does not read notes.
- `scripts/guard.py` answers a guardrail check for fabricate, rank, crisis, post, or inject.
- `scripts/cron_sitting.sh` and `scripts/cron_weekly.sh` are the live `--no-agent` entry points. They pass `--data` at the profile `wisdom/` directory.
- `scripts/install_cron.py --skip` records the default 8:00 America/New_York sitting and the Sunday 18:00 weekly job. It does not register a live job.

## Tests

From this directory:

```bash
bash tests/smoke.sh
```

That runs the file-level contract tests. It does not call a model. If `grok` is missing, smoke prints that you should install Grok Build or use Cursor, Claude Code, or Codex, then continues. It does not switch to another build CLI.

Paula owns the live smoke and the red-team in SPEC §10. The file-level tests are not the live red-team.
