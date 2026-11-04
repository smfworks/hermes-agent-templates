---
name: wisdom-daily-sitting
description: >-
  Use for the morning sitting, a one-line night reply, the streak, and a
  text-only quote card. Load wisdom-guardrails first.
---
# Daily Wisdom daily sitting

Pick the next tradition not used in the last 3 local days, and a theme not used this calendar week.

Rotation: Stoic; Greek/classical; Christian (patristic, contemplative); Jewish; Buddhist; Islamic/Sufi; Confucian/Taoist; Hindu; modern essayists.

Themes: flourishing, contemplation and action, faith and reason, attention, gratitude, courage, death and time, friendship, work.

The reading is 2–5 lines, attributed (author, work, section when known). One sentence of plain context. One question, answerable in a line. Close with: "Reply with one line tonight if you like."

Log the sitting. A second run the same day re-sends the logged sitting and does not create a new one.

## Format

```
**Today's reading — <Tradition>**
> 2–5 lines
— Author, *Work*, section   (or "(paraphrase)")
<one sentence of context>
**Question for today:** <one line>
Reply with one line tonight if you like.
```

## Question

One question, answerable in one line, livable today (a concrete action or a point of attention), tied to the reading. No yes/no question. No therapy framing. Do not repeat a question within 30 days.

## Reply

On a reply, thank the owner in one line. Append the note to `notes.md`. Update the streak. No lecture.

Streak means consecutive local days with a reply (a note or the word "done"). A missed day resets the streak to 0, gently. Encourage. Never guilt.

Storage under the profile data dir `wisdom/`:

- `sittings.csv` — date, tradition, source, reading, question, replied y/n
- `notes.md` — date, sitting id, note. Private.
- `state.json` — streak, longest, last_reply_date, tz, prefs, schedule

Writes are atomic. The streak is computed from `sittings.csv` so it can be rebuilt.

## Quote card

On request, send a text-only card of that day's reading. Do not include private notes.

## Hermes (this template)

Tool names only. The rules above do not change.

- First run is when `memories/USER.md` has no sitting or onboarding record. Placeholders are not a record.
- Sittings, notes, and state live under the profile data dir `wisdom/`. The chat profile writes them with the `file` tool. Scripts take `--data` pointed at that directory.
- The `cronjob` tool installs `daily-wisdom-sitting` and `daily-wisdom-weekly`. Those jobs run with `--script` and `--no-agent`.
- Load `wisdom-guardrails` with `skill_view` before a sitting, a page, a card, or a note reply.
- A page is a markdown file and an html file in `wisdom/`. There is no hosted link.
- No connectors. A calendar reminder is out of scope.
- No terminal tool. No web tool. No browser. No delegation.
