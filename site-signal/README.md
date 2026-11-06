# Site Signal

Website quality agent for sites you own. It scans SEO, GEO, AEO, AI readiness,
and accessibility (axe-core), ranks issues by impact, and opens draft fix pull
requests. Merges wait for your approval.

Published by SMF Works under the MIT license. The public contract is
[`SPEC.md`](./SPEC.md). Rules for agents working in this directory are
[`AGENTS.md`](./AGENTS.md).

## Install

From a checkout of this repository:

```bash
hermes profile install ./site-signal --name site-signal --alias
```

Hermes Agent 0.22.0 or newer. `site-signal` is `hermes -p site-signal`.

## Configure

1. Copy `.env.EXAMPLE` to `.env` inside the installed profile and `chmod 600 .env`.
   - `GH_TOKEN` is optional when `gh auth login` is already done. A fine-grained
     token needs contents and pull requests on the repos you want edited, plus
     checks read. `gh` is the GitHub CLI on `PATH`. Set `GH_BIN` only to override
     that binary.
   - `CHROME_PATH` points at Chromium for the axe scanner. The scanner never
     hardcodes a browser path. Skip axe when Chromium is not installed.
   - `XAI_API_KEY` is only for an xAI runtime model. The fix-writing step uses
     Grok Build (`grok` on `PATH`, or `GROK_BIN`). The default model is
     `grok-4.7`. A machine-local model alias is optional.
   - `VERCEL_TOKEN` is optional. Deploy waits use GitHub check runs and `curl`.
2. Copy `sites.yaml.example` to `~/SiteSignal/sites.yaml` and edit it there.
   The example uses `example.com` with `owner_verified: false` and `merge: ask`.
   Replace it with sites you control. Do not mark a domain verified until
   `verify_ownership.sh` passes and you confirm that domain.
3. `config.yaml` holds page caps, the rate limit, the user agent, and the
   optional Grok Build model.

Scanners identify as `SMFWorks-SiteSignal/1.0 (+https://smfworks.com)`. Crawls
honor robots.txt for that user agent, at most 1 request per second per host,
at most 25 pages per run, 20 second timeout, GET only.

## Data

`~/SiteSignal/` is created at first run: `sites.yaml`, `history.jsonl`,
`repos/`, `wt/`, `reports/<domain>/<run>/`. Runtime data is not stored in the
profile directory.

## Weekly routine

`cron/jobs.json` ships one paused job, `site-signal-weekly-rescan` (Mondays
08:00 America/New_York, `no_agent`, `scripts/weekly_rescan.sh`). It scans every
`owner_verified` site and prints a short diff only when a score drops by 3 or
more points, a new critical or serious issue appears, or a scan fails. Cron
never opens or merges pull requests. Enable it only after you say yes.

## Tests

From this directory, with the Python packages in `requirements.txt`:

```bash
python3 -m pip install -r requirements.txt
bash tests/smoke.sh
```

That runs offline scanner tests against fixtures, the empty ownership seed
check, and the ship-fix gate. It does not call production sites. The axe
fixture skips when Node, Chromium, or its npm dependencies are missing.
`SITE_SIGNAL_LIVE=1` is an explicit opt-in and reads URLs from
`SITE_SIGNAL_LIVE_URLS`.

## Safety

- Fix PRs only for domains in `sites.yaml` with `owner_verified: true` and no
  `scan_only: true`. Everything else is scan-only.
- Never push to a default branch, never force-push, and never merge without an
  approval line that names that PR. `merge: after_green_ci` auto-merges only
  when you have written `merge_consent` for that domain (the phrase
  `always merge green PRs for <domain>`, plus who set it and when). The agent
  does not write that block. A fresh install does not auto-merge.
- Squash only. Pull requests open as drafts.
- The deny-terms scan fails closed before every commit and PR text. It never
  prints the list.
- No invented statistics, quotes, citations, authors, dates, or `sameAs` profiles.
- No ranking guarantees. axe misses keyboard and screen-reader issues, so a
  manual pass is still needed.
- Cron jobs never open or merge pull requests.

## License

MIT. See [LICENSE](LICENSE). Accessibility scanning depends on axe-core
(MPL-2.0); see the repository [credits](../README.md#credits).
