# Receipts — environment notes (mikesai1 / omarchy-2)

Recorded 2026-11-04 before the first build step.

- Branch point: origin/main 008b563 (Bourne Bot template already on main).
- Hermes Agent v0.22.6 (2026.9.24), git install, Python 3.14.9. `hermes_requires: ">=0.22.0"`.
- Grok Build: `~/.grok/bin/grok` 1.0.70. Default model grok-4.7. Do not swap CLIs if missing at smoke time; name Cursor, Claude Code, Codex.
- gh 2.103.3 at `~/.local/share/mise/installs/gh/2.103.3/gh_2.103.3_linux_amd64/bin/gh`. `~/.local/bin/gh` is a mise wrapper; do not use it.
- Grok Bot source: https://x.ai/bot/JXXlchVIC_I2v76hbclRP. Skills in this template are written from SPEC.md §§1–8 (Charlie's parity spec).
- Skill loadable layout (v0.22.x): `skills/<category>/<skill-name>/SKILL.md` (two levels), matching bourne-bot. Frontmatter `name:` is the Grok Bot skill name (`money-back-getting-started`, `money-back-scan`, `money-back-page`, `money-back-guardrails`).
- Cron: `hermes cron create` supports `--timezone`, `--script`, `--no-agent`, `--skill`. Store tz in `money-back/state.json` and pass `--timezone` on create. Default tz America/New_York. Jobs install only on an explicit yes.
- Mail: fixtures backend for tests and no-connector use. Gmail API uses `gmail.readonly` only. IMAP opens the mailbox read-only. Token/app password live in the Hermes secrets store or a 0600 file outside the repo. Never commit them.
- Profile git identity: Paula Rossi <paula@smfworks.com>.
- LICENSE copyright line: SMF Works only. Do not write any other employer name.
- Liam owns SPEC §10 live smoke + red-team. Ship CI-runnable contract tests anyway.
- Draft PR only. Merge gate = Michael's yes comment naming the live head SHA; checks green; any new push voids the yes. Do not merge.
