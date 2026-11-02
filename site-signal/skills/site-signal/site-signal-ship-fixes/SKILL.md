# When to use

When the owner asks to ship fixes for a verified site ("Make fixes", "ship the
top serious on wisdomforge") or to merge an open Site Signal PR ("merge
wisdomforge#22"). One PR per repo per pass, from a fresh worktree, merged only
on the owner's recorded approval. Everything here runs through
`scripts/ship_fix.sh` — the guardrails (ownership gate, draft PRs, squash-only,
approval naming) live in the script, not in improvisation.

# Before you ship

- `report.json` exists for the domain (`site-signal-report` ran on this run).
- The domain is in `~/SiteSignal/sites.yaml` with `owner_verified: true` and no
  `scan_only: true`. `ship_fix.sh` refuses everything else (smfworks.com is
  scan-only until Michael assigns fix ownership).
- The owner named the target: "ship the top serious on wisdomforge" qualifies;
  a bare "go" does not. Relay it verbatim as `--approved-by-owner`.
- Dry-run first when the plan is new: `--dry-run` creates a throwaway worktree,
  renders the fix brief, prints every command it WOULD run, stops before the
  push, and opens nothing.

# Ship phase (5.4 steps 1–7)

```bash
skills/site-signal/site-signal-ship-fixes/scripts/ship_fix.sh \
  --repo smfworks/wisdomforge --domain smfwisdomforge.com \
  --run-dir ~/SiteSignal/reports/smfwisdomforge.com/<run> \
  --approved-by-owner "ship the top serious on wisdomforge"
```

Selection defaults to all critical + serious issues in the ranked report;
`--top N` takes the first N, `--with-moderate` adds moderate (only when the
owner says "all"), `--issues "a11y/color-contrast,seo/open-graph"` picks
explicitly, and `--brief FILE` uses a fix brief you wrote instead of the
rendered one. The script then:

1. Creates `$SS_HOME/repos/<repo>` (clones once) and a worktree
   `$SS_HOME/wt/<repo>-<shortid>` on branch `site-signal/<topic>-<shortid>`
   from `origin/<default_branch>`.
2. Renders the fix brief (`$RUN/fix-brief-<repo>.md`) — ranked issues with
   evidence (rule id, URL, selector/snippet, current value), the desired
   outcome, constraints (SMF Works branding and publisher; no new stats,
   quotes, citations, authors, dates, or sameAs; no prose rewrites beyond a
   1–2-sentence lead or a 40–60-word answer restating existing content; keep
   the layout), and acceptance (repo tests + build pass).
3. Runs Grok Build headless with the brief, writing `$RUN/grok-<repo>.json` —
   on this host that is `-m spark-glm` (GLM 5.3); the run is pinned to
   "commit locally only; never push; never gh; never touch .env". Hermes (this
   script) does the push and PR. For 1–2 line fixes you may skip Grok Build
   (`--skip-grok`) and edit via your own patch tooling before the script runs.
4. Runs the repo's tests and build (`npm test --if-present`, `npm run build`
   by default; override with `--test-cmd`/`--build-cmd`). Failure stops the
   ship with nothing pushed.
5. Greps the diff for new numerals and new external URLs and lists the hits in
   the PR body ("New facts flagged for review") — the owner confirms or
   removes; nothing is invented to satisfy a check.
6. Runs `deny_terms_check.sh` over the diff, PR title, PR body, and brief —
   fail closed; a block means fix the text, never bypass.
7. Pushes the branch once and opens a **draft** PR (owner's standing
   preference) with the issues, evidence, before scores, and verification log,
   then waits for checks (`gh pr checks --watch --fail-fast`, ≤20 min).

On green checks: if `merge: after_green_ci` is saved for the site, or the
approval line names the PR, it merges immediately; otherwise it prints the
merge command and waits for the owner. A failed check leaves the PR open for
inspection (exit 8) — report it, do not force anything.

# Merge phase (5.4 step 7) — only after the owner names the PR

```bash
skills/site-signal/site-signal-ship-fixes/scripts/ship_fix.sh \
  --merge 22 --repo smfworks/wisdomforge --domain smfwisdomforge.com \
  --run-dir ~/SiteSignal/reports/smfwisdomforge.com/<run> \
  --approved-by-owner "merge wisdomforge#22"
```

The approval must contain the repo (full or short) and `#22` — "merge wisdomforge
22" or "merge the wisdomforge PR" do not match; a bare "go" is refused. The
policy `merge: after_green_ci` replaces the per-PR approval only when the owner
said "always merge green PRs for <domain>" and that is recorded in sites.yaml.
The script verifies the PR is OPEN and MERGEABLE, marks it ready if draft,
squash-merges with `--match-head-commit <head sha>` (subject `<PR title>
(#<n>)`), and deletes the branch. Squash only — never merge commits, never
force-push, never touch the default branch.

# Deploy wait + re-scan (5.4 steps 8–9)

`wait_deploy.sh <repo> <merge_sha> <domain>` (run by ship_fix.sh when
`deploy: vercel`) polls GitHub check runs and deployment statuses on the merge
SHA for ≤15 min, then curl-verifies the artifact on production — pass
`--verify-path /sitemap.xml` and optionally `--expect-contains …` for the
specific fix. A timeout means "not confirmed", not "failed": check the Vercel
dashboard, verify manually, then continue.

The re-scan runs the same scanners on the same page set into
`$SS_HOME/reports/<domain>/<run>-after/`, ranks and renders it, and appends the
before → after row to the original report's **Shipped** table. Report the
delta from the re-scan numbers only.

# False positives (5.4 step 9)

If a check still fails but the deployed HTML proves the fix landed, suspect the
**scanner**: verify the live HTML by hand (curl + read the markup), confirm the
rule is misfiring, and propose the scanner change as a version bump — with the
evidence — never a quiet loosening. The Grok Bot precedent: Book and
LearningResource were added to the article-schema type list, and the scanner
was fixed instead of forcing site changes.

# Cleanup (5.4 step 10)

The script removes the worktree and local branch. Confirm the remote branch is
gone (`--delete-branch` does it), and leave `~/SiteSignal/` with the before and
after runs plus the approval records (`$RUN/approval-<repo>.md`).

# Never

- Push a default branch, force-push, or rewrite history; the coding model never
  pushes and never runs `gh`.
- Merge without an approval line naming the PR (or a saved `after_green_ci`
  policy), on non-green CI, on a non-mergeable PR, or with a moved head SHA.
- Open PRs for unlisted, unverified, or `scan_only` domains — the script refuses;
  do not work around it.
- Let the deny-terms check pass with a missing list (fail closed) or print the
  list when reporting a block.
- Add dependencies in a fix PR without listing them for the owner.
- Touch other agents' repos: smfworks.com fixes stay with whoever Michael
  assigns; Site Signal keeps it scan-only until then.
