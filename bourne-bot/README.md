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
