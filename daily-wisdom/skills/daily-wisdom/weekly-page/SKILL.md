---
name: wisdom-weekly-page
description: >-
  Use to build or refresh the weekly "What changed in me" page in place.
  Load wisdom-guardrails first.
---
# Daily Wisdom weekly page

Build or refresh the weekly reflection artifact in place.

Contents: the week's readings, the streak, recurring themes, patterns quoted briefly in the owner's own words, one encouragement, and next week's focus.

If there are no notes, include the readings, the streak, and the focus only. Never invent a reflection.

One file per owner, updated in place: `wisdom/what-changed-in-me.md` and the rendered `wisdom/what-changed-in-me.html` from `templates/weekly.html`.

Deliver it on the owner's channel with one warm line and the path or a short summary.

## Hermes (this template)

Tool names only. The rules above do not change.

- First run is when `memories/USER.md` has no sitting or onboarding record. Placeholders are not a record.
- Sittings, notes, and state live under the profile data dir `wisdom/`. The chat profile writes them with the `file` tool. Scripts take `--data` pointed at that directory.
- The `cronjob` tool installs two jobs named `daily-wisdom-sitting` and `daily-wisdom-weekly`. Hermes assigns a 12-character hex job id; you cannot choose it. Weekly uses `script=cron_weekly.sh` and `no_agent=true`.
- Load `wisdom-guardrails` with `skill_view` before a sitting, a page, a card, or a note reply.
- A page is a markdown file and an html file in `wisdom/`. There is no hosted link.
- No connectors. A calendar reminder is out of scope.
- Write `wisdom/what-changed-in-me.md` and `wisdom/what-changed-in-me.html` with the `file` tool, overwritten in place. Fill the HTML from `templates/weekly.html`.
- No terminal tool. No web tool. No browser. No delegation.
