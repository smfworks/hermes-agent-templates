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

No connectors. The profile does not log in to your accounts. Its tools are file, memory, skills, clarify, cronjob, and todo.

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
