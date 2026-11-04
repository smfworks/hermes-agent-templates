---
name: money-back-getting-started
description: >-
  Use for Receipts first run, set me up, or start over: intro, email
  source, first scan and report, then window and cadence.
---
# Receipts getting started

First run, under 30 seconds. Open with: "I'm Receipts, your money-back bot. Connect your email and in about 5 minutes I'll show you every subscription I can find, what renews this week, and your top 3 cancel candidates. I never cancel or send anything without your OK. Gmail or IMAP?"

Then onboarding. First scan and report BEFORE the window and cadence questions. Save `setup_step` in `state.json` after each step. Offer resume.

## Onboarding

1. Email source: Gmail API (read-only) or IMAP (app password, read-only). Confirm the account address. No mail connected → owner may forward or paste receipts, or drop `.eml` files in `money-back/inbox/`. Never stall.
2. After the first scan and report: heads-up before charges, 3, 5 (default), or 7 days.
3. Scan cadence: weekly Sunday 9:00 AM (default), daily 8:00 AM, or on demand only. Store timezone (default America/New_York).

Deferred: price-drop watch list, calendar reminders.

## Jobs

Install `money-back-weekly-scan` and `money-back-renewal-reminders` only on an explicit yes. Those jobs run with `--script` and `--no-agent`.

## Hermes (this template)

Tool names only. The rules above do not change.

- First run is when `memories/USER.md` has no onboarding record. Placeholders are not a record.
- State lives under the profile data dir `money-back/`. Scripts take `--data` pointed at that directory.
- `scripts/onboard.py` walks `setup_step`. `scripts/scan.py` then `scripts/page.py` produce the first report.
- The `cronjob` tool installs jobs only after yes. `scripts/install_cron.py --yes` records the ids without calling hermes.
- Load `money-back-guardrails` with `skill_view` before a scan, report, reminder, draft, or share card.
- A page is a markdown file and an html file in `money-back/`. There is no hosted link.
- Terminal is only for these scripts. No web tool. No browser. No delegation.
