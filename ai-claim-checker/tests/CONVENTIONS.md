# AI Claim Checker script contract

All scripts live under `ai-claim-checker/scripts/` and take `--data DIR` (a temp dir in tests) unless noted. Never write to the real `~/.hermes`.

Slugs are sanitized: drop path segments, keep `[a-z0-9._-]`, reject `.` / `..`, and resolve under `--data/claims/`. A traversal slug cannot write outside that root.

Writers merge into the existing `state.json` object and leave keys they do not own in place. Do not call `hermes`. Do not call a model. Do not register a live cron job.

Frozen clock for tests: `--now 2026-11-06T12:00:00Z`. Default timezone `America/New_York`.

Four verdicts only: `supported`, `vendor-only`, `contradicted`, `unverifiable`.

## Commands

See README.md and AGENTS.md for the script list. Fixture packs live in `tests/fixtures/`.

`LICENSE` contains `SMF Works`. `SOUL.md` and `AGENTS.md` exist. Exactly four `SKILL.md` files, names `verity-getting-started`, `verity-claim-decomposition`, `verity-verdict-rubric`, `verity-claim-card-format`.
