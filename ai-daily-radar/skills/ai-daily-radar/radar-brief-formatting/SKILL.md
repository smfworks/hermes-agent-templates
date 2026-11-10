---
name: radar-brief-formatting
description: >-
  Use to write Standard, Quick, and Friday wrap briefs, apply
  topic weights, and keep the never-list.
---
# Radar brief formatting

Standard (default), per item: Headline (≤12 words; `Update:` prefix for material updates); What changed: 1–2 sentences; Why it matters to you: 1 sentence tied to the owner's stack; Tag: exactly one; Links: primary source, plus one secondary if it exists. End with Try this today: one concrete ~10-minute action.

Quick: one line per item `[Tag] Headline. One-line why. (primary link)`, then the Try this today line.

Friday wrap (Fridays only, inside the Friday Daily Brief job): write `wraps/<week>.md/.html` with The week in 5 lines, One thing I'd ignore, and an archive of the week's tagged items. Chat gets the normal Friday brief plus ONE headline sentence on the biggest shift and the local wrap path. Do not append the full wrap to the daily brief.

Header line: date in owner local time with zone label. Footer: "Try Hermes: AI Daily Radar by SMF Works." Chat never shows an invented hosted link.

Never: more than 7 items; an item without a primary link; an item with zero or two tags; election, candidate, or campaign content; stock or investment angles.

Feedback: replies like "👍 3", "👎 2", "less X", "more Y" adjust `topic-weights.json`. Thumbs-down lowers rank and frequency but keeps the category; three or more on the same topic may drop it to "only if major" and Radar says so. Feedback never removes tagging, sourcing, or safety rules and never hides a material update.

## Hermes (this template)

The rules above do not change.

- `python3 scripts/render_brief.py` is used by `brief.py`.
- `python3 scripts/feedback.py --data DIR --topic TOPIC --dir down|up --now ISO` writes weights.
- One or two items force Quick style.
- Nothing qualifies → send nothing; the run is logged.
