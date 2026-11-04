---
name: money-back-page
description: >-
  Use to rebuild the Money Back report in place, give cancel help, or
  draft cancel and refund mail. Load money-back-guardrails first.
---
# Receipts page

Build or refresh the report in place. Cancel help and drafts.

## Report

One file per owner, overwritten in place: `money-back/money-back.md` and `money-back/money-back.html` (`templates/report.html`).

Contents: monthly burn (fixed monthly + annual/12 labeled); usage-billed shown separately; renewing this window; trials about to bill; price hikes (old → new); top 3 cancel candidates (duplicates, then price increases, then trials about to bill, then lapsed/unknown), each with reason + source date, labeled "your call"; full subscription table with source (sender + date); verified savings (only proven). Footer: "Try Hermes: Receipts — The Money-Back Bot by SMF Works".

Chat reply: one or two lines plus the path. Share card (text only): totals and "found N subscriptions"; service names only if the owner OKs; savings line only when verified savings > 0.

## Cancel help and drafts

Give the provider's account/cancel page and steps. Never log in with the owner's password. Never submit forms.

Draft a cancel or refund email only when the provider needs one, or the owner asks. Draft = `.eml` in `money-back/drafts/` (To, Subject, Body). Show it in chat in full. No send path in v1.

"Saved" only with proof: cancellation confirmation, refund receipt, lower-price receipt in mail, or the owner says they cancelled → `saved_ledger`.

## Hermes (this template)

- `scripts/page.py --data DIR --now DATE` overwrites the same two paths.
- `scripts/cancel_help.py --service NAME` prints steps and a link.
- `scripts/draft.py --data DIR --service NAME --kind cancel|refund` writes `.eml`.
- `scripts/share_card.py --data DIR` prints the card.
- Load `money-back-guardrails` with `skill_view` first.
- There is no hosted link.
