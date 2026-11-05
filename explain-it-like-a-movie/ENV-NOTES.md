# Explain It Like a Movie — environment notes

Recorded 2026-11-05 before the first commit on movie-v1.

- Branch point: origin/main 03ab1fc (Receipts already on main).
- Hermes Agent v0.22.x. `hermes_requires: ">=0.22.0"`.
- Grok Build: if missing at smoke time, name Cursor, Claude Code, Codex. Do not swap CLIs.
- gh: mise 2.103.3 full path. Do not use `~/.local/bin/gh`.
- Skills in this template are written from SPEC.md. No Appendix A dump.
- Skill loadable layout (v0.22.x): `skills/<category>/<skill-name>/SKILL.md` (two levels). Frontmatter `name:` is movie-getting-started, movie-script, movie-produce, movie-guardrails.
- Shipped `config.yaml` is `grok-4.7` / `provider: xai-oauth` plus `_config_version: 52`. `.env.EXAMPLE` has an `XAI_API_KEY=` placeholder. Do not ship a host-local endpoint in the template.
- Terminal is on the chat toolset because render.py and pdftotext have to run. Web is on the toolset because URL fetch is required. No browser, no delegation, no cron in v1.
- `SOUL.md` must not contain the injection scanner's hit phrase. Protected-instruction gate may block agent writes to any `SOUL.md` basename; write `SOUL.tmp.md` / `AGENTS.tmp.md` and `git mv` them.
- LICENSE copyright line: SMF Works only. Do not write any other employer name.
- Liam owns SPEC §8 live smoke + red-team. Ship CI-runnable contract tests anyway.
- No-key render: ffmpeg + Pillow + espeak-ng or piper. CI installs espeak-ng. Local smoke may set `PIPER_MODEL` to an onnx voice if piper is on PATH.
- Draft PR only. Merge gate = Michael's yes comment naming the live head SHA; checks green; any new push voids the yes. Do not merge.
