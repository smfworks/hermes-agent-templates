---
name: verity-claim-card-format
description: >-
  Use to write the dated Card or Brief, save locally on request, and
  keep weekly re-checks changes-only.
---
# Verity claim card format

Title: what was checked plus the owner's local check date (default America/New_York, with zone label). Include run status, input link or location, and any unreadable or omitted input.

Table columns: Claim, Verdict, Primary source, Independent evidence, Notes, Checked on. Every factual number carries a citation in its own cell. Contradicted rows show both values. Source list distinguishes published or updated dates from retrieval timestamps.

After the table: Not checkable; Bottom line (exactly three plain-language lines: what holds up; what is vendor-only; what to be careful repeating); What would change my mind (specific evidence that would move a verdict). Footer: "Try Hermes: AI Claim Checker by SMF Works."

Brief style: the three-line bottom line, up to three most important verdict bullets with citations, and the check date. The full local card remains available. Chat gets a concise verdict summary and local paths, not a fabricated hosted link.

HTML escapes all source text and uses safe http(s) links. No source scripts or remote embeds. Text card is the default. Re-check history may append locally; the visible card stays at the same paths. No public upload is part of card creation.

On explicit "save," add claim text, scope and settings, verdict, source references, and check date to profile-local `saved-claims.json`. Weekly opt-in creates one timezone-aware Hermes cron job, suggested Monday 08:00; record the actual job id. Re-fetch saved claims, compare structured results, update the same card, report changes only. Empty saved set or unchanged result is silent. Inaccessible sources get a named reachability warning; the prior result is marked historical. Deduplicate identical outage notices until status changes.

## Hermes (this template)

The rules above do not change.

- Cards live at `claims/<slug>/claim-card.md` and `claim-card.html`, overwritten in place. Supporting files: `claims.json`, `sources.json`, `history.jsonl`. Global `state.json` and `saved-claims.json`. Slugs are sanitized local identifiers.
- `python3 scripts/render_card.py` is used by `check.py`. `python3 scripts/check.py --data DIR --slug SLUG --backend fixtures --fixtures PATH` writes the card. `--save` appends `saved-claims.json`. `--style brief` also writes `claim-brief.md`.
- `python3 scripts/weekly.py --data DIR` is the cron script. It prints nothing when the saved set is empty or unchanged.
- Chat has no terminal tool. Scripts run from cron with `--script` and `--no-agent`, or as `python3 scripts/...` in tests.
- Fixture packs are conspicuous "fixture/demo, not live verification."
