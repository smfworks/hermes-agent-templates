---
name: money-back-scan
description: >-
  Use to scan mail since the last run, write subscriptions.csv, then
  hand off to money-back-page. Load money-back-guardrails first.
---
# Receipts scan

Since last scan (first run: 60 days). Writes `subscriptions.csv`, then hands off to `money-back-page`.

## Search

Gmail: `newer_than:60d (subject:(receipt OR invoice OR subscription OR renewal OR "renews" OR "trial" OR "price" OR "your plan") OR "auto-renew" OR "will renew" OR "free trial ends")`. IMAP: SINCE the date, same terms. Skip Promotions and marketing unless the mail says a charge happened.

## Classify

Group by service (normalized sender domain + product name). Open the newest receipt per service. Read amount, currency, plan, service period, cadence, payment date.

- fixed subscription — recurring charge receipt/invoice, or a "will renew" notice with an amount
- usage-billed — cloud/API credits; tracked separately; never "unused" or a cancel candidate by default
- one-time — ignored
- trial — "trial ends", "first charge on", "after your free trial"
- price change — "new price", "price increase", or amount higher than the previous receipt for the same plan and cadence

## Flags

Renews or trial bills within the window. Price increase vs previous receipt (old → new, both sourced). Duplicate (two plans, same service). Usage spike (>25% vs previous bill, name the top line item). Lapsed (monthly with no receipt 45+ days → status "unknown", ask).

Evidence required per finding: sender, email date, subject, message id, and the quoted line containing the amount or date. No evidence → not a finding.

Next renewal = service-period end when given; else last charge + cadence, labeled "estimate".

## Dedupe

Key = service + plan + cadence. Latest receipt wins. Message ids appended, never duplicated rows. A finding already alerted (id = hash(service, type, date)) is not re-alerted.

## Storage

Under `money-back/`: `subscriptions.csv`, `findings.jsonl`, `state.json`. Atomic writes.

## Hermes (this template)

- `scripts/mail_fetch.py` then `scripts/scan.py --data DIR --inbox DIR --backend fixtures --now DATE`.
- Load `money-back-guardrails` with `skill_view` first.
- Re-running over the same mail must produce the same CSV.
