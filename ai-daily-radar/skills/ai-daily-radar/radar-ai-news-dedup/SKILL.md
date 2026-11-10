---
name: radar-ai-news-dedup
description: >-
  Use to merge same-story items against the ledger and to keep
  only material updates.
---
# Radar AI news dedup

Dedup against `ledger.jsonl` (~30 days). Same story when: same normalized primary URL (ignore tracking params, trailing slashes, locale paths); or same vendor + product/model + event type (launch, price change, benchmark, deprecation) within about 7 days; or a secondary whose main link is an already-reported primary.

Merge in-run duplicates into one item (primary plus best secondary). Skip repeats unless MATERIAL: announced to shipped or GA; vendor claim independently tested or contradicted (tag change); price, limits, or region change; rollback, deprecation, or security issue. Material → headline prefix `Update:` plus one line on what is new. Commentary, reposts, and opinion are not updates.

Append every new or updated item after successful delivery. Prune rows older than 30 days.

## Hermes (this template)

The rules above do not change.

- `python3 scripts/ledger.py` is imported by `brief.py`.
- Ledger append happens only after the brief files are written. `--no-deliver` leaves the ledger unchanged.
- Historical ledger rows are previously reported. Do not re-present them as new.
