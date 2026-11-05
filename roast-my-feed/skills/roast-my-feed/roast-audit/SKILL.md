---
name: roast-audit
description: >-
  Use to audit one public X handle: resolve, read, measure, pick the
  best post and worst habit, write the report, and make the share card.
  Load roast-guardrails first.
---
# Roast My Feed audit

Load `roast-guardrails` before the audit, the report, the drafts, and the card.

## Resolve

Resolve the user by username. Keep `created_at` and `public_metrics`. If the user is not found, ask for a profile link.

## Read

Read the user's posts. Exclude retweets. `start_time` is now minus 7 days, ISO UTC. Fields: `created_at`, `public_metrics`, `referenced_tweets`, `conversation_id`. Paginate with `next_token` until the pages run out or 20 pages (about 500 posts). If the read stops at the cap, the window is the oldest post read through now, and the report states that window. If the 7-day read has fewer than 20 posts, rerun with 30 days. Fallback search: `from:<handle> -is:retweet`.

## Measure

Count. Do not guess.

- Posts in the window, and posts per day.
- Share of replies, quotes, and originals.
- Emoji-only posts and link-only posts.
- Posts with a number or a named thing in line one.
- Median likes and max likes. Views when they are present.
- Most active hours in the owner's timezone. Default `America/New_York`.

## Pick

- Best post: most likes, then most views.
- Worst habit: the most frequent low-performing pattern, with its count and its performance against the median.
- Archetype: a playful label of 2 to 4 words.

## Plan and drafts

Seven daily actions. Each one works on the worst habit and repeats what the best post did.

Three drafts in the owner's voice, from topics they actually posted. Invent no claims.

## Report and share card

Write `roast/<handle>/roast.md` and `roast.html` from `templates/report.html`. Overwrite those paths on a re-run. Sections, in order: window, archetype, stats, best post (verbatim, with a link), worst habit (count against the median), 7-day plan, 3 drafts. Footer: "Try Hermes: Roast My Feed by SMF Works".

Reply with the markdown path and the share-card text. The share card is a local PNG, `roast/<handle>/card.png`, plus a text version. A weekly re-run compares the habit count with the last run in `history.jsonl`.

## Hermes (this template)

The rules above do not change. The model writes the archetype label, the 7 daily actions, and the 3 drafts. It does not invent the counts.

- No terminal tool. No web tool. No browser. No delegation. Cron runs this audit with `--script` and `--no-agent`. A manual run is `python3 scripts/audit.py`.
- `python3 scripts/x_read.py` does the read. Backend `fixtures` for tests and for no-token use. Backend `live` uses an app-only Bearer (`X_BEARER_TOKEN`) and GET only. With no token, tell the owner how to add one, or accept a `tweets.js` archive.
- `python3 scripts/roast_metrics.py` writes the counts, the best-post id, and the worst habit. Read that output. Do not recompute it.
- `python3 scripts/audit.py --data DIR --handle HANDLE` overwrites `roast/<handle>/roast.md` and `roast.html`, appends one `history.jsonl` line, and prints the markdown path plus the text card. It does not install cron.
- `python3 scripts/card.py` writes `roast/<handle>/card.png`. The text card includes the footer and leaves out post bodies, bios, and third-party profile fields.
- The best-post link is `https://x.com/<handle>/status/<id>`.
- The first audit for a handle includes the sentence `No earlier roast for this handle.` A later audit includes `Last run worst habit <habit> count was <count>.` using the previous history line.
- Default timezone is `America/New_York`, stored in `state.json`. Pass `--tz` when the owner has another IANA name there.
- Load `roast-guardrails` with `skill_view` first.
