# When to use

After any scan (baseline, re-scan, or single dimension) to merge the scanner
JSON into a ranked report and present it. JSON is the source of truth;
`report.md` is the reading copy; `report.html` is presentation.

# Pipeline

```bash
RUN=~/SiteSignal/reports/<domain>/<YYYY-MM-DDTHHMM>   # seo.json, ai.json, axe.json live here
~/SiteSignal/.venv/bin/python3 skills/site-signal/site-signal-report/scripts/rank.py $RUN
~/SiteSignal/.venv/bin/python3 skills/site-signal/site-signal-report/scripts/render_report.py $RUN          # report.md + chat summary
~/SiteSignal/.venv/bin/python3 skills/site-signal/site-signal-report/scripts/render_report.py $RUN --html   # + report.html
~/SiteSignal/.venv/bin/python3 skills/site-signal/site-signal-report/scripts/render_report.py --all         # multi-site scorecard
```

rank.py writes `report.json` and appends one line to `~/SiteSignal/history.jsonl`.
The three scanners are independent — run them in parallel, then rank.

# Report format (SPEC.md 5.3)

`report.md` sections, in order: title line (`Site Signal — <domain> — <date ET>`),
score line (`SEO n (G) · GEO · AEO · Overall n (G)`, plus `AI readiness n/100 (G)`
and `Accessibility (axe) c critical · s serious · m moderate · mi minor (nodes, p
pages)`), `_Change since last scan:_` (from `history.jsonl`; **"first scan"** when
there is no prior run — never a made-up delta), then:

1. **Fix first** — ranked table: #, Impact, Dimension, Issue (`id`: message),
   Where, Fix, Effort (S/M/L).
2. **Evidence** — axe rule hits with selector + HTML snippet, robots/headers,
   JSON-LD types found.
3. **Passing checks**.
4. **Caveats** — desktop viewport + sampled pages; axe misses keyboard/screen-reader
   issues so a manual pass is still needed; scores are Site Signal rubric scores,
   not a ranking or WCAG conformance claim.
5. **Shipped** — PR, status, before → after (updated by `site-signal-ship-fixes`).

# Ranking key (fixed, ascending — do not reorder by hand)

```
impact_rank   = {critical:0, serious:1, moderate:2, minor:3}[impact]
dimension_tie = {a11y:0, ai_ready:1, seo:2, geo:3, aeo:4}  # a11y first only within the same impact
reach         = -(axe node count | pages affected | 1)
effort        = {S:0, M:1, L:2}  # heuristic; agent may override per issue with a reason
key = (impact_rank, dimension_tie, reach, effort)
```

Effort heuristic: S = metadata/attribute/token/label change in 1–2 files;
M = new route or file (sitemap, robots, llms.txt, JSON-LD component,
breadcrumbs); L = template/content-structure changes across many pages.
Overrides go through `rank.py --overrides FILE` mapping `"dimension/id"` to
S/M/L, with a recorded reason. Fix priority always puts critical accessibility
first (guardrails rule 4).

# Chat summary (the only thing the owner reads by default)

≤15 lines, in this order: score line, top 3–6 fixes (impact + dimension + id +
where), one caveat line, the report path, and the closing question "Ship these
as PRs?". render_report.py prints it; relay it verbatim rather than rewriting
it. For multi-site asks, one summary per site plus the scorecard path, and any
critical a11y issue leads the combined list.

# HTML + scorecard

- `--html` writes one self-contained `report.html` (inline CSS only, yellow on
  navy, no external fonts or scripts) — the substitute for a hosted page. Share
  the file path; host it only if the owner asks.
- `--all` writes `~/SiteSignal/reports/scorecard.md` (+ `.html`): one row per
  site with latest scores and trend arrows (↑/↓/→, "new" for a first scan).
- No composite a11y score anywhere, and no claims language (never "WCAG
  compliant", "ranking guarantee", "official").

# Never

- Edit `report.json` by hand, or reorder findings against the ranking key.
- Present a delta without a prior `history.jsonl` entry.
- Mix Lighthouse or other tool scores into Site Signal scores (separate, labeled).
- Send a summary longer than 15 lines or without the caveat line.
