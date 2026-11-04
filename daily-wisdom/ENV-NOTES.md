# Daily Wisdom — environment notes (mikesai1 / omarchy-2)

Recorded 2026-11-04 before the first Grok Build step.

- Branch point: origin/main 008b563 (Bourne Bot template already on main).
- Hermes Agent v0.22.6 (2026.9.24), git install, Python 3.14.9, local f0d94882e89a. `hermes_requires: ">=0.22.0"`.
- Grok Build: `~/.grok/bin/grok` 1.0.70, auth present (grok.com). Default model grok-4.7. Do not swap CLIs if missing at smoke time; name Cursor, Claude Code, Codex.
- gh 2.103.3 at `~/.local/share/mise/installs/gh/2.103.3/gh_2.103.3_linux_amd64/bin/gh`. `~/.local/bin/gh` is a mise wrapper; do not use it.
- Grok Bot live check: https://x.ai/bot/u5Du_MOfZGUSSYJIyceLY HTTP 200. Public page title "Daily Wisdom (by SMF Works) by Michael". The page does not expose skill bodies. Skills in this template are written from SPEC.md §§1–8 (Charlie's parity spec). No Appendix A dump existed on disk.
- Skill loadable layout (v0.22.x): `skills/<category>/<skill-name>/SKILL.md` (two levels), matching bourne-bot. Frontmatter `name:` is the Grok Bot skill name (`wisdom-getting-started`, `wisdom-daily-sitting`, `wisdom-weekly-page`, `wisdom-guardrails`).
- Cron: `hermes cron create` supports `--timezone`, `--script`, `--no-agent`, `--skill`, `--name`. It does not take a caller-chosen job id; Hermes mints `uuid4().hex[:12]`. Identify Daily Wisdom jobs by name `daily-wisdom-sitting` and `daily-wisdom-weekly`. Live jobs.json on this host has a `timezone` key when `--timezone` is passed. Store tz in `wisdom/state.json` as well. Default tz America/New_York.
- Shipped `config.yaml` is `grok-4.7` / `provider: auto` plus `_config_version: 52`. A fresh install has no credentials and can fail `invalid_params` until the operator wires a provider. Do not ship spark-glm or any host-local endpoint in the template.
- `SOUL.md` must not contain the injection scanner's hit phrase. Distribution-owned SOUL is blocked on a hit (`test_distribution_owned_soul_md_still_blocks_on_a_hit`).
- Profile git identity: Liam (SMF Works) <liam@smfworks.com>.
- LICENSE copyright line: SMF Works only. Do not write any other employer name.
- Paula owns SPEC §10 live smoke + red-team. Ship CI-runnable contract tests anyway. Do not overwrite untracked files she leaves.
- Draft PR only. Merge gate = Michael's yes comment naming the live head SHA; checks green; any new push voids the yes. Do not merge.
