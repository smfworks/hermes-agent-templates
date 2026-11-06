# Site Signal — public spec

Website quality agent for sites the operator owns. It scans SEO, GEO, AEO, AI
readiness, and accessibility, ranks issues by impact, and opens draft fix pull
requests. This file is the public contract. It does not list anyone's sites,
machines, or tokens.

The skill files under `skills/site-signal/` are the operating rules. If a skill
and this file disagree, `site-signal-guardrails` wins.

## 3. Persona and rules

### 3.1 Greeting

Paste a production URL you own and Site Signal returns SEO, GEO, AEO,
AI-readiness, and accessibility scores ranked by impact, then opens fix PRs
when you ask.

### 3.3 Standing rules

1. Open fix PRs only for domains in `sites.yaml` with `owner_verified: true`
   and without `scan_only: true`. Everything else is scan-only.
2. No direct pushes, no force-push, and no history rewrite on a default or
   protected branch. Fix work uses a fresh worktree on
   `site-signal/<topic>-<shortid>`.
3. Default merge policy is `merge: ask`. A merge needs CI green on the current
   head SHA, a mergeable PR, and an approval line that names the repo and PR.
   `merge: after_green_ci` auto-merges only when `merge_consent` names that
   domain, the phrase is `always merge green PRs for <domain>`, and `set_by`
   and `set_at` record who set it and when. The agent does not write that
   block. A fresh install does not auto-merge. Squash only. PRs open as drafts.
4. Fix priority is critical accessibility, then critical AI-readiness or SEO,
   then serious, moderate, and minor. `rank.py` implements this.
5. Deny-terms scan fails closed before every commit and PR text. Never print
   the private list or quote its terms.
6. Do not invent statistics, quotes, citations, authors, dates, or social
   profiles.
7. Crawl as `SMFWorks-SiteSignal/1.0 (+https://smfworks.com)`, honor robots.txt
   for that user agent, at most 1 request per second per host, at most 25
   pages per run, 20 second timeout, GET only.

## 5. Workflow

### 5.1 Ownership

Copy `sites.yaml.example` to `~/SiteSignal/sites.yaml` and edit it there.

`scripts/verify_ownership.sh` checks one method:

- `seed+owner` — the public seed list is empty. This method never verifies a
  domain.
- `repo` — `gh` can read `OWNER/REPO` and its homepage points at the domain.
- `wellknown` — `https://<domain>/.well-known/site-signal.txt` contains the token.
- `dns` — TXT `site-signal-verification.<domain>` contains the token.

Exit 0 is the mechanical check only. The owner still confirms that domain
before `owner_verified` becomes true. Unlisted domains stay scan-only.

### 5.2 Scans

Three scanners, run against a site the operator asked to scan:

- SEO / GEO / AEO — `site-signal-seo-geo-aeo`
- AI readiness — `site-signal-ai-readiness`
- Accessibility — `site-signal-axe-scan` (axe-core, MPL-2.0, via puppeteer-core)

Weights and check lists live in each skill's `references/rubric.md` (Appendix
A). Do not change weights without a version bump.

### 5.3 Report

`rank.py` merges scanner JSON into a ranked report. `render_report.py` writes
`report.md` and `report.html`. JSON is the source of truth.

### 5.4 Ship a fix

`ship_fix.sh` clones into a worktree, renders a fix brief, runs the coding
tool, runs repo tests, runs the deny-terms check, pushes the feature branch,
and opens a draft PR. It squash-merges with `--match-head-commit` only when
the approval line names the repo and PR, or when `merge_consent` for that
domain is complete. Then it can wait for deploy and re-scan.

### 5.5 Weekly re-scan

`scripts/weekly_rescan.sh` scans every `owner_verified` site and prints a short
diff only when a score drops by 3 or more points, a new critical or serious
issue appears, or a scan fails. The cron job ships paused. Cron never opens or
merges a pull request.

## 6. Registry and installs

### 6.1 Registry

The live registry is `~/SiteSignal/sites.yaml`, outside the profile, so an
update does not overwrite it. `sites.yaml.example` is a placeholder:
`example.com`, `owner_verified: false`, `merge: ask`.

### 6.2 Skills

Eight skills under `skills/site-signal/`. Each `SKILL.md` has YAML frontmatter
with `name` and `description`.

### 6.3 Pull requests

Site Signal opens draft PRs itself for verified sites that are not
`scan_only`. It does not assume any particular domain is scan-only. The
operator sets `scan_only: true` when another workflow already ships fixes.

Install from a checkout:

```bash
hermes profile install ./site-signal --name site-signal --alias
```

Hermes 0.22.0 or newer. `platform_toolsets` is the config key.

## 7. Build and tests

### 7.1 What ships

Scaffold, persona, guardrails, skills, scanners, rank and render, the fix-PR
flow, the paused weekly job, and offline tests.

### 7.2 Install gate

`gh` is the GitHub CLI on `PATH` (`GH_BIN` overrides it). Do not point it at a
machine-specific install. `CHROME_PATH` is optional and required only for the
axe scanner.

### 7.3 Acceptance

`bash tests/smoke.sh` runs the offline pytest suite, the ownership seed check,
and the ship-fix gate against local fixtures. It does not call production
sites. Set `SITE_SIGNAL_LIVE=1` only when you intentionally scan URLs in
`SITE_SIGNAL_LIVE_URLS`. The axe fixture skips when Node, Chromium, or
puppeteer-core is missing.

## 8. Operator choices

### 8.4 Things this template does not decide

1. Which chat gateway receives reports.
2. Whether a given domain should be `scan_only`.
3. Optional search-console access. Unused by default.
4. The runtime model. The shipped default is `grok-4.7`. A local alias is
   optional.

## 9. Checklist

- Example registry does not mark a real domain `owner_verified`.
- `verify_ownership.sh` seed list is empty.
- `merge: after_green_ci` without `merge_consent` does not merge.
- Deny-terms check fails closed and does not print the list.
- Cron does not open or merge pull requests.
- No build-machine hostname, local username, or home-directory path in the
  files this template installs.
