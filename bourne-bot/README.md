# Bourne Bot

Bourne Bot helps you protect your accounts, devices, location, money, family, and reputation, proportionally and legally.

This is not law enforcement and not legal advice. If you are in danger, call your local emergency services. Bourne Bot is not Jason Bourne.

SMF Works publishes this template under the MIT license.

## Install

From a checkout of this repository:

```bash
hermes profile install ./bourne-bot --name bourne-bot-dev --alias
```

`bourne-bot-dev` is the development profile name. The distribution name is `bourne-bot`. Hermes Agent 0.22.0 or newer.

## After install

Copy `templates/USER.md` and `templates/MEMORY.md` into the profile `memories/` directory. Live memory files must be mode 0600. Keep placeholders and non-secret facts only. Never put a password, code, or account number in memory or in chat.

The first conversation asks six questions, one at a time, unless something is happening now. A live incident skips intake and starts with one first step.

## Skills

- `bourne-getting-started`
- `bourne-guardrails`
- `bourne-incident-response`
- `bourne-threat-model`

No connectors. The profile does not log in to your accounts. Its tools are file, memory, skills, clarify, cronjob, and todo. It has no terminal tool, so it does not run the scripts below. You run them.

## Scripts the owner runs

- `python3 scripts/incident_first_step.py` prints the one-line first step for an incident phrase.
- `python3 scripts/secret_paste.py` scans a paste and does not print a secret it finds.
- `python3 scripts/forget_memory.py` removes one intake field.
- `bash scripts/chmod_memories.sh` sets memory files to mode 0600.
- `bash scripts/create_checkin.sh --yes` writes `cron/jobs.json` only. It does not register a live job.

## Tests

From this directory:

```bash
bash tests/smoke.sh
```

That runs the secret-paste, forget, memory mode, check-in, incident phrase, and file-level refusal checks. It does not call a model. If `grok` is missing, smoke prints that you should install Grok Build or use Cursor, Claude Code, or Codex, then continues. It does not switch to another build CLI.

## Forget an intake field

```bash
python3 scripts/forget_memory.py memories/USER.md "forget my travel info"
```

This removes the travel field from that file and does not print the file. Other fields stay. Set live memory files to mode 0600 with `scripts/chmod_memories.sh`. Memory is not encrypted at rest.
