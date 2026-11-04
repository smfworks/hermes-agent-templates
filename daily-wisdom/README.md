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

The first conversation is a short intro, today's sitting, then three onboarding questions, one at a time. Skip keeps the default. Onboarding then installs cron jobs `daily-wisdom-sitting` and `daily-wisdom-weekly` as script jobs (`--script --no-agent`).

## Skills

- `wisdom-getting-started`
- `wisdom-daily-sitting`
- `wisdom-weekly-page`
- `wisdom-guardrails`

## Tests

From this directory:

```bash
bash tests/smoke.sh
```

That runs the file-level contract tests. It does not call a model. If `grok` is missing, smoke prints that you should install Grok Build or use Cursor, Claude Code, or Codex, then continues. It does not switch to another build CLI.

Paula owns the live smoke and the red-team in SPEC §10. The file-level tests are not the live red-team.
