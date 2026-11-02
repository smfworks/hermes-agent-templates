# Site Signal — Hermes profile distribution (SMF Works)

Website quality agent for sites you own. It scans **SEO, GEO, AEO, AI readiness,
and accessibility (axe-core)**, ranks issues by impact, ships fixes as GitHub PRs
that are merged only on your approval, confirms the deploy, re-scans live, and
reports before → after.

- Source of truth: [`SPEC.md`](./SPEC.md). Rules for agents building this repo:
  [`AGENTS.md`](./AGENTS.md).
- Brand: SMF Works.
- **Status:** build steps 1–8 of `SPEC.md` 7.1 are done (scaffold; `SOUL.md` +
  guardrails; skill bodies; scanners; ranking/report; fix-PR flow; cron routine;
  tests). Step 9 is the live smoke test, run by the orchestrator at acceptance
  (`bash tests/smoke.sh` — never run as part of a build step).

## Install

```bash
# Development install from this checkout (SPEC.md 6.3 / 7.2 gate)
hermes profile install . --name ss-dev --alias

# Production install from the private repo (create it first — see below)
hermes profile install github.com/smfworks/hermes-site-signal --alias

# Updates later (keeps memories, sessions, .env; keeps local config.yaml unless --force-config)
hermes profile update site-signal
```

The dev install gives you the `ss-dev` wrapper (= `hermes -p ss-dev`). Chat with
`ss-dev chat` or `hermes -p ss-dev chat`.

## Configure

1. **Credentials** — copy `.env.EXAMPLE` to `.env` inside the installed profile dir
   and fill in. Then `chmod 600 .env`.
   - `GH_TOKEN` — prefer `gh auth login` (keyring); set the token only if a file is
     unavoidable. Fine-grained: smfworks repos, contents + pull requests RW, checks R.
     Host note: `~/.local/bin/gh` is a broken mise wrapper here — use
     `~/.local/share/mise/installs/gh/2.103.3/gh_2.103.3_linux_amd64/bin/gh`
     (`PREREQ-RESULTS.md`).
   - `CHROME_PATH` — Chromium for the axe scanner. On this host:
     `~/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome` (or
     `/usr/bin/chromium`). The scanner reads `CHROME_PATH`; `/usr/bin/google-chrome`
     is never hardcoded (Google ships no linux-arm64 Chrome).
   - `XAI_API_KEY` — only if the operator picks an x.ai runtime model. The fix-writing
     backend is Grok Build (`~/.grok/bin/grok`) with GLM 5.3, which on this host is
     the `spark-glm` model entry (no paid API needed).
   - `VERCEL_TOKEN` — optional, off by default; deploy waits use GitHub check runs
     plus `curl`.
2. **Sites** — copy `sites.yaml.example` to `~/SiteSignal/sites.yaml` and edit there.
   The real registry lives outside the profile so updates never overwrite it.
   `smfworks.com` ships as **scan-only** until Michael assigns fix ownership
   (`SPEC.md` 6.3) — another Hermes agent does site work there.
3. **Model / Grok Build** — `config.yaml` sets `skills.config.site_signal.*`
   (data home, deny-terms path, page caps, rate limit, UA, Grok Build model).
   Verify with `hermes -p ss-dev config show`.

**User agent (decision from `PREREQ-NOTES.md`):** all scanners identify as
`SMFWorks-SiteSignal/1.0 (+https://smfworks.com)` — the unified UA allowed by
`SPEC.md` 5.2. Crawls honor robots.txt for that UA, ≤1 req/s per host, ≤25 pages
per run, 20 s timeout, GET only.

## Data & runtime layout

`~/SiteSignal/` is created at first run: `sites.yaml`, `history.jsonl`, `repos/`,
`wt/`, `reports/<domain>/<run>/`. No runtime data is stored in the profile dir.

## Weekly routine (SPEC.md 5.5)

`cron/jobs.json` ships one **paused** job, `site-signal-weekly-rescan`
(Mondays 08:00 America/New_York, `no_agent`, `scripts/weekly_rescan.sh`).
The script scans every `owner_verified` site in `~/SiteSignal/sites.yaml`
with all three scanners, ranks + renders a report, and compares against the
domain's last `history.jsonl` entry. It prints a short diff **only** when a
score dropped ≥ 3 points, a new critical/serious issue appeared (including
more nodes on a critical/serious axe rule), or a scan step failed — empty
stdout is a silent tick. The first scan of a site is silent (no baseline).
Cron runs never open or merge PRs. All output lands under
`~/SiteSignal/reports/<domain>/<run>-weekly/`.

Enable only after the owner says yes:

```bash
hermes -p site-signal cron resume site-signal-weekly-rescan   # or edit enabled/state
```

The authored record was validated against the installed Hermes v0.22.5 cron
loader and installer merge path; `hermes cron create --script weekly_rescan.sh
--no-agent --timezone America/New_York --paused` remains the fallback if the
record ever needs regeneration (keep the same job id so updates merge).

## Smoke test

After build steps 3–9, `bash tests/smoke.sh` runs the three scanners read-only
against smfworks.com and smfwisdomforge.com, then rank + render, and prints the
report paths (`SPEC.md` 7.1 step 9). Acceptance criteria are `SPEC.md` 7.3 (S1–S10)
and the checklist in `SPEC.md` 9. Per-scanner command lines live in the skill
bodies under `skills/site-signal/` once step 4 lands.

## Operator must verify

UNKNOWN items from `SPEC.md` 8.4, with current status. Do not guess; resolve each
before production use.

1. **Grok Bot skill texts** — OPEN. The six `site-signal-*` skill bodies from the
   Grok Bot box are UNKNOWN (not on disk). If Michael exports the template behind
   the share link, diff it against `SPEC.md` 6.2 and merge anything missing.
2. **`cron/jobs.json` schema** — RESOLVED: authored directly against the installed
   Hermes v0.22.5 loader and verified (`cron.jobs.load_jobs`, the installer's
   `import_job_definitions` merge, `is_job_runnable() == False`, and
   `compute_next_run` = Mondays 08:00 America/New_York). One job,
   `site-signal-weekly-rescan`, ships PAUSED (`enabled: false`,
   `state: "paused"`, `paused_reason: "enabled only after the owner says yes
   (SPEC 5.5)"`). On install Hermes re-stamps scheduler-owned fields
   (`paused_at`, `created_at`) and keeps the job paused.
3. **`toolsets:` vs `platform_toolsets:`** — RESOLVED: `platform_toolsets:` (per-
   platform map) is the current key; used in `config.yaml`.
4. **GLM 5.3 availability on mikesai1** — RESOLVED as `-m spark-glm`
   (GLM-5.3-Flash-EXL3 via spark-56bc, no Z.ai key needed). The `zai` provider
   401s on this box; `grok_model: spark-glm` is set in `config.yaml`.
5. **Which gateway Michael wants reports in** (Telegram/Slack/Discord/CLI) — OPEN.
6. **Does Site Signal open PRs itself, or hand off to Liam/Aiona?** — OPEN; the
   spec defaults to opening PRs itself (`SPEC.md` 6.3).
7. **Which agent owns smfworks.com fixes** — OPEN. A Hermes agent already does
   site work there, so `smfworks.com` is scan-only meanwhile.
8. **Google Search Console access** — OPEN; optional add-on, unused by default
   (the Grok Bot never used it).
9. **Distribution + sandbox repos** — `smfworks/hermes-site-signal` and
   `smfworks/site-signal-sandbox` do not exist yet; both need Michael's go
   (`PREREQ-RESULTS.md`).
10. **Hermes cron timezone on the host** — RESOLVED: the authored job carries
    `timezone: "America/New_York"`; the installed scheduler computes
    `next_run_at` in that zone (verified: `2026-11-02T08:00:00-05:00`).

## Safety summary

- Fix PRs only for domains in `sites.yaml` with `owner_verified: true` and no
  `scan_only: true`. Everything else is scan-only.
- Never push to a default branch, never force-push, never merge without an
  explicit approval naming that PR (or a saved `merge: after_green_ci` policy).
  Squash only. PRs open as drafts (owner's standing preference).
- Deny-terms scan (`~/.config/grok-fleet/deny-terms.txt`, never printed) runs
  fail-closed before every commit and PR text.
- No invented statistics, quotes, citations, authors, dates, or `sameAs` profiles.
- No WCAG-conformance or ranking-guarantee claims; axe misses keyboard and
  screen-reader issues, so a manual pass is still needed.
- Cron jobs never open or merge PRs.

## Build status (`SPEC.md` 7.1)

| Step | Deliverable | State |
|---|---|---|
| 1 | Scaffold (tree, manifest, config, README, AGENTS, sites.yaml.example) | done |
| 2 | `SOUL.md` + `site-signal-guardrails` skill | done |
| 3 | Eight skill bodies | done (1887364) |
| 4 | Three scanners + `lib/common/http.py` | done (5156834) |
| 5 | `rank.py` + `render_report.py` + templates | done (a9d7ab0) |
| 6 | Fix-PR flow (`ship_fix.sh`, deny-terms, deploy wait) | done (15183b9) |
| 7 | `weekly_rescan.sh` + paused cron job | done (this commit) |
| 8 | Tests + fixtures | done (next commit) |
| 9 | `tests/smoke.sh` | done (next commit; live run at acceptance) |
