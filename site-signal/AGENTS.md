# AGENTS.md — rules for building this repo (dev only)

This repo is the `site-signal` Hermes profile distribution for SMF Works, built by a
coding agent following `SPEC.md`. `SPEC.md` is the source of truth; this file is the
working ruleset for the agent doing the building. Recorded host findings and
decisions live in `PREREQ-NOTES.md`, `PREREQ-RESULTS.md`, `ENV-NOTES.md`, and
`PLAN-site-signal.md` — follow them where they resolve an UNKNOWN.

## Working rules

1. Read `SPEC.md` fully before writing anything. Build in the `SPEC.md` 7.1 order
   (steps 1–9), commit after each step with a clear message, and never push.
2. Port the three scanners in `SPEC.md` Appendix A **verbatim in logic and weights**.
   Allowed additions only: a `--json` flag for axe, the shared polite fetcher
   `lib/common/http.py`, robots.txt respect for our UA, and a 1 req/s rate limit.
   Never change scoring weights or check lists without a version bump.
3. ARM64 and x86_64 Linux friendly: pure Python and Node, no platform-specific
   binaries. Chromium comes from `CHROME_PATH` (Playwright's bundled Chromium or
   distro chromium). Never hardcode `/usr/bin/google-chrome`.
4. No secrets in any committed file. Only `.env.EXAMPLE` exists, with variable
   names only. Never edit another profile's files or fleet services on this host.
5. Git and GitHub safety: never push, never force-push, never write to a default
   branch of any external repo, and never merge without an explicit approval flag
   (`--approved-by-owner`) plus a recorded approval naming that repo and PR, or a
   saved per-site merge policy. Draft PRs are the owner's standing preference
   (`PLAN-site-signal.md`). On this host use the mise `gh` binary, not
   `~/.local/bin/gh` (it deadlocks — see `PREREQ-RESULTS.md`).
6. Brand = SMF Works. Never name or hint at Michael's employer anywhere: code,
   comments, schema, PR text, reports, or chat drafts. Before finishing any task,
   run, from the repo root:
   `grep -rniE -f ~/.config/grok-fleet/deny-terms.txt .` (if that file exists)
   Fix every hit. Never print the deny-terms file or quote its terms.
7. Anything `SPEC.md` marks UNKNOWN becomes a clearly labelled "Operator must
   verify" TODO in `README.md`. Never guess.
8. Site Signal data lives in `~/SiteSignal/` (created at runtime) and is never
   committed here. Scratch files go in `/tmp/`.
9. Leave the repo clean at the end of a step: no stray artifacts, `git status`
   showing only intentional files.
