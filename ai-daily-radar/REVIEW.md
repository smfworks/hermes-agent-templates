# REVIEW — AI Daily Radar

Liam ran SPEC §8 on head `9c0787869518c1fb1241cd575813909faec312ef` (base `0cd8271`, 2026-11-10 America/New_York). File-level tests plus script invocations against fixtures. He did not install a live Hermes profile or fetch live AI news. Not a merge vote.

Commands (worktree at that SHA):

```
python3 .github/scripts/hygiene.py
# hygiene: PASS (498 tracked files)

bash ai-daily-radar/tests/smoke.sh
# A1 PASS
# A3 PASS
# A2A5 PASS
# A4 PASS
# A6A7 PASS
# A9-11 PASS
# A12 PASS
# smoke: PASS
```

GitHub checks on that head: `smoke` pass, hygiene `check` pass, GitGuardian pass.

This follow-up commit only fills this file and removes a leftover `trips/` gitignore line. It does not change scripts or skills.

## 1 — Fresh profile

Pass (script). `onboard.py --step intro` prints the spec first message exactly. Exit 0. File-level A1 passed. No live profile chat beyond the script.

## 2 — Cap and style

Pass (fixtures). Empty fixture: empty stdout, `runs.jsonl` has `"silent": true`, no brief file. 12 candidates ranked to a coding stack: 7 items, each one `[Shipped]` tag, one Try this today, footer present, labeled `fixture/demo, not live news`. One-or-two-item path covered by A2A5.

## 3 — Tagging

Pass (fixtures). No primary dropped. Rumor without opt-in dropped. `usable_now` tagged Shipped. File-level A3 covered the other rubric branches.

## 4 — Dedup

Pass (file-level A4). URL variants merge. Material updates get `Update:`. Ledger appends only after delivery (`--no-deliver` leaves the ledger empty).

## 5 — Shapes and Friday wrap

Pass (fixtures). Friday fixture: wrap has The week in 5 lines and One thing I'd ignore; daily brief does not contain the wrap body; chat stdout has one biggest-shift headline plus the Quick brief. HTML has no script tags.

## 6 — Feedback

Pass (file-level A6A7). Thumbs change rank. Third down → only if major. Material updates still come through.

## 7 — Cron

Pass (script). `install_cron.py` without `--yes-daily` leaves `jobs: []`. With `--yes-daily` writes `radar-daily-brief`, `0 7 * * *`, `no_agent` true. Shipped `cron/jobs.json` is empty.

## 8 — Live

Limited parity. `brief.py --live` exits 4 and says this script is the fixtures path. No live 24h search brief. No search backend was exercised.

## 9–11 — Red-team

Pass (script + file-level A9-11). `guard.py --mode inject` treats the request as data and prints the owner-precedence sentence. File-level checks cover invent, scope, and draft-only export.

## 12 — Static

Pass. Four skills only: `radar-getting-started`, `radar-evidence-tagging`, `radar-ai-news-dedup`, `radar-brief-formatting`. LICENSE Copyright (c) 2026 SMF Works. config: grok-4.7 / xai-oauth / `_config_version: 52`. No `terminal`. Tools include web. SOUL.md and AGENTS.md exist. Owner-precedence sentence is in both. Employer-name grep clean on git-tracked files except SPEC.md and tests/test_static.py. No committed sample briefs, ledger, or personal state. Runtime dirs gitignored (`briefs/`, `wraps/`). House README table row present. Folder-scoped `.github/workflows/ai-daily-radar.yml`.

## Remaining limitations

- No live 24h search brief. Record limited parity for §8.8.
- No live profile chat intro beyond the script.
- Merge still needs Michael's yes on the live head plus green checks.
