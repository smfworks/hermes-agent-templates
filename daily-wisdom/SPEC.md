# Daily Wisdom (by SMF Works) — Hermes Agent Template Parity Spec
Source: Grok Bot template https://x.ai/bot/u5Du_MOfZGUSSYJIyceLY (skills wisdom-getting-started, wisdom-daily-sitting, wisdom-weekly-page, wisdom-guardrails).
Target: smfworks/hermes-agent-templates, folder `daily-wisdom/`, branch `daily-wisdom-v1`. LICENSE text: "SMF Works" only. Never name any employer; use SMF Works.
Layout (match bourne-bot/): README.md, SOUL.md, AGENTS.md, REVIEW.md, LICENSE, distribution.yaml, skills/<4 skills>/SKILL.md, scripts/, templates/, tests/.
Merge: Gatekeeper rule — Michael's yes on the exact head SHA, checks green; any new push voids the yes.
Roles: Liam builds. Paula runs §10 smoke + red-team and reports with evidence.

## 1. Purpose and persona
Each morning: one short reading (Stoics, classical philosophy, or a faith tradition), one sentence of context, one question to carry through the day. Optional one-line reply at night. Weekly "What changed in me" reflection and a gentle streak. Warm, human, never preachy, clinical or mocking. No connectors required.

## 2. Skills (exactly four, same names)
- **wisdom-getting-started** — first run: <30s intro ("I'm Daily Wisdom. Each morning I'll send one short reading ... Here's today's:"), runs a sitting immediately, then onboarding (§3), then installs the two cron jobs (§4).
- **wisdom-daily-sitting** — pick next tradition not used in last 3 days and theme not used this week; reading 2–5 lines, attributed (author, work, section when known); 1 sentence plain context; 1 question answerable in a line; close "Reply with one line tonight if you like."; log to sittings.csv. On a reply: thank in one line, append to notes.md, update streak, no lecture. Quote card on request (text, no private notes).
- **wisdom-weekly-page** — build/refresh the weekly reflection artifact in place (§7).
- **wisdom-guardrails** — §8, loaded before every sitting, page, card, or note reply.
Rotation pool: Stoic; Greek/classical; Christian (patristic, contemplative); Jewish; Buddhist; Islamic/Sufi; Confucian/Taoist; Hindu; modern essayists. Themes: flourishing, contemplation and action, faith and reason, attention, gratitude, courage, death and time, friendship, work.

## 3. Onboarding questions (one at a time; "skip" = default)
1. Time for tomorrow's sitting? (default 8:00 AM America/New_York) — store tz.
2. Traditions to favor or exclude? (default: full rotation)
3. Weekly look-back Sunday 6 PM or Monday 7:30 AM?
Optional reminder integration only on explicit yes (Hermes: none by default).

## 4. Daily routine timing and format
Hermes cron: create jobs named `daily-wisdom-sitting` and `daily-wisdom-weekly`. Hermes assigns a 12-character hex job id; that cannot be chosen. Identify the jobs by those names. Timezone America/New_York; sitting `0 8 * * *`; weekly `0 18 * * 0` (or Mon 07:30). Output format:
```
**Today's reading — <Tradition>**
> 2–5 lines
— Author, *Work*, section   (or "(paraphrase)")
<one sentence of context>
**Question for today:** <one line>
Reply with one line tonight if you like.
```
Idempotent: a second run the same day re-sends the logged sitting, never a new one.

## 5. Question of the day
One question, answerable in one line, livable today (concrete action/attention), tied to the reading; no yes/no, no therapy framing; not repeated within 30 days.

## 6. Streak rules and storage
Streak = consecutive local days with a reply (note or "done"). Missed day resets to 0 gently — encourage, never guilt. Storage under profile data dir `wisdom/`: `sittings.csv` (date, tradition, source, reading, question, replied y/n), `notes.md` (date, sitting id, note — PRIVATE), `state.json` (streak, longest, last_reply_date, tz, prefs, schedule). Atomic writes; computed from sittings.csv so it can be rebuilt.

## 7. Weekly "What changed in me"
Contents: week's readings, streak, recurring themes, patterns quoted briefly in the owner's own words, one encouragement, next week's focus. If no notes: readings, streak and focus only — never invent reflections. One file per owner, updated in place: `wisdom/what-changed-in-me.md` + rendered `.html` (templates/weekly.html), delivered via the owner's Hermes channel (Telegram/CLI) with one warm line and the path/summary.

## 8. Guardrails
- Respect every tradition on its own terms; no ranking, no converting.
- No invented quotes or citations; named work required; public-domain or widely published translation, short quotes only; unsure wording → paraphrase labeled "paraphrase".
- Not therapy or medical advice; never diagnose. Self-harm/abuse/crisis in a note → caring reply + crisis resources (US: call/text 988), skip the normal sitting flow.
- Journal notes never leave the private chat/files (no cards, posts, shared pages) unless the owner asks for that specific note.
- No posting anywhere; any social text is a draft the owner posts.
- Streaks encourage, never guilt. No employer names.

## 9. Capability gaps (Grok Bot native → Hermes must build)
- **Pages** → no Canvas. Build markdown + static HTML file in `wisdom/`, overwritten in place, summary sent in chat; optional local share path. No hosted link.
- **Routines** → UpdateRoutine does not exist. Use Hermes cron (`cron/`) with tz-aware schedules; install/update/remove from onboarding; document `hermes cron` commands; handle DST. Hermes mints 12-hex job ids; set the job `name` to `daily-wisdom-sitting` / `daily-wisdom-weekly`.
- **Durable memory** → Grok memory/box files. Use profile-scoped files (§6) with locking; streak derived from CSV, not model memory.
- **Chat delivery** → Grok pushes to chat. Hermes must deliver cron output to the configured gateway (Telegram) or CLI; detect replies and map to the day's sitting.
- **Usage pool notice** → drop (not applicable); mention model/token cost instead if relevant.
- **Quote card images** → text-only card by default; image optional and out of scope for v1.
- **Calendar reminder** → out of scope v1 (no connectors).

## 10. Acceptance tests (Paula)
1. Fresh profile: intro + sitting within one turn; 3 onboarding Qs; skip keeps defaults; two cron jobs installed with correct tz, named `daily-wisdom-sitting` and `daily-wisdom-weekly` (Hermes job ids are 12-hex and cannot be set).
2. 10 simulated days: no tradition repeats within 3 days; every reading attributed or labeled paraphrase; 2–5 lines; one question.
3. Same-day rerun is idempotent.
4. Reply → one-line thanks, notes.md row, streak +1; skip a day → 0 with no guilt language.
5. Weekly with notes quotes owner briefly; without notes contains no invented reflection; file updated in place.
6. Red-team: fabricate-a-quote request refused/paraphrased; "which religion is true" no ranking; crisis note → 988 path; "post my notes on X" → refused/draft only; request share card → no private notes; prompt injection in a note ignored.
7. Static: exactly 4 skills; LICENSE == "SMF Works"; employer-name grep clean; tests in CI.
