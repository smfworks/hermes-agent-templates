# Daily Wisdom script contract

All scripts live under `daily-wisdom/scripts/` and take `--data DIR` (a temp dir in tests). Never write to the real `~/.hermes`.

`--data DIR` is the profile data directory itself (SPEC's `wisdom/` folder). These files live directly in `DIR`:

- `sittings.csv`
- `notes.md`
- `state.json`
- `what-changed-in-me.md`
- `what-changed-in-me.html`

A script that writes `state.json` merges into the existing object and leaves keys it does not own in place.

Do not call `hermes`. Do not call a model. Do not register a live cron job.

1. `python3 scripts/sitting.py --data DIR [--date YYYY-MM-DD]`

   Prints the sitting in SPEC §4 format. Logs one row to `DIR/sittings.csv`.

   Columns: `date,tradition,source,reading,question,replied`

   Quote every field. The tradition `Christian (patristic, contemplative)` must survive a round-trip.

   `replied` is `n` until a reply. Same-day second run reprints the logged sitting and must not add a row.

   A missed local day (last reply before yesterday) writes `streak` 0 even on a reprint.

   Tradition not used in the last 3 local days. Theme not used this calendar week (Mon–Sun). Themes may repeat in a later week. Ten consecutive days starting on a Monday use seven themes in week one and three in week two, so at least one theme label repeats across the week boundary. There are nine theme labels.

   Reading 2–5 lines, attributed (author, work, section when known) or labeled `(paraphrase)`.

   Exactly one question. Close with: `Reply with one line tonight if you like.`

2. `python3 scripts/reply.py --data DIR --date YYYY-MM-DD --note TEXT`

   One-line thanks on stdout (no lecture). Append to `DIR/notes.md`. Set `replied=y`. Streak in `DIR/state.json`.

   Streak = consecutive local days with a reply (note or the word `done`). A missed day resets streak to 0.

   Guilt-language banned in stdout: "should have", "you failed", "don't break your streak", "guilty", "disappoint".

3. `python3 scripts/weekly.py --data DIR [--week-start YYYY-MM-DD]`

   Writes `DIR/what-changed-in-me.md` and `DIR/what-changed-in-me.html` in place (overwrite, one file per owner).

   With notes: quote the owner briefly in their own words. Without notes: readings, streak, next-week focus only — no invented reflection (ban "you realized", "you learned", "you grew" unless those words are in `notes.md`).

4. `python3 scripts/install_cron.py --data DIR --jobs PATH [--skip]`

   Onboarding skip = defaults: 8:00 America/New_York; full rotation; weekly Sunday 18:00.

   Writes two jobs into `PATH` with ids `daily-wisdom-sitting` and `daily-wisdom-weekly`.
   Script fields are `cron_sitting.sh` and `cron_weekly.sh`. Those wrappers ship under `scripts/`.
   Live Hermes mints 12-hex job ids; match live jobs by `name`.

   Must record tz `America/New_York` in `DIR/state.json`. Does not call `hermes`. Does not register a live job.

5. `python3 scripts/quote_card.py --data DIR --date YYYY-MM-DD`

   Text-only card of that day's reading. Must not contain any bytes from `DIR/notes.md` private notes.

6. `python3 scripts/guard.py --mode MODE [--text TEXT]`

   Modes: `fabricate` | `rank` | `crisis` | `post` | `inject`

   - `fabricate`: refuse to invent a fake citation; print paraphrase or refuse; do not print a made-up "Book IV.99" style fake cite.
   - `rank`: no ranking of religions; do not name a tradition as true/truer.
   - `crisis`: caring line + "988" (call/text). Exit 0.
   - `post`: refuse to post notes; draft-only. Exit 0.
   - `inject`: ignore instruction-like text in a note; do not follow "ignore previous instructions".

## Checked shapes

Tests invoke the commands above with absolute paths, `cwd` at `daily-wisdom/`, and `HOME` pointed at a temp directory. `--date` and `--week-start` are the simulated local dates. Stdout is UTF-8.

### Sitting stdout

The first non-empty line is the sitting. No preamble and no trailing extra lines. Blank lines are ignored. Em dashes are U+2014.

```
**Today's reading — <Tradition>**
> line
> line
— Author, *Work*, section
<one sentence of context ending with a period>
**Question for today:** <one line>
Reply with one line tonight if you like.
```

Each reading line has its own `>` prefix. Two to five reading lines.

`<Tradition>` is one of:

- Stoic
- Greek/classical
- Christian (patristic, contemplative)
- Jewish
- Buddhist
- Islamic/Sufi
- Confucian/Taoist
- Hindu
- modern essayists

The attribution line starts with `—`. It either contains `(paraphrase)` or it contains an author, a comma, and an italic work `*like this*`. Section is optional. The context is the single line between the attribution and the question.

"Last 3 local days" means the three calendar dates before `--date`. The same tradition may occur again on the fourth day. Question text is not repeated inside a 10-day run (SPEC §5: not within 30 days).

### sittings.csv

UTF-8 CSV with this header and no extra columns:

```
date,tradition,source,reading,question,replied
```

- `date` is `YYYY-MM-DD`.
- `tradition` matches the header tradition.
- `source` is the attribution line without the leading em dash.
- `reading` is the quote lines joined by newlines, without `>` prefixes.
- `question` is the one question line, without the `**Question for today:**` label, and without a newline.
- `replied` is `n` or `y`.

One row per date. A second `sitting.py` run for that date reprints the same stdout and leaves the parsed rows unchanged.

### state.json

JSON object.

| Key | Owner | Shape |
| --- | --- | --- |
| `tz` | `install_cron.py --skip` | `"America/New_York"` |
| `prefs` | `install_cron.py --skip` | `{"rotation": "full"}` |
| `themes` | `sitting.py` | object of `YYYY-MM-DD` → theme |
| `streak` | `reply.py` | integer |
| `longest` | `reply.py` | integer, at least the highest streak so far |
| `last_reply_date` | `reply.py` | `YYYY-MM-DD` of a reply |

Theme is one of: flourishing, contemplation and action, faith and reason, attention, gratitude, courage, death and time, friendship, work.

Inside one Monday–Sunday week, theme values are unique.

`reply.py` after `--date D --note TEXT`:

- stdout is one non-empty line, at most 200 characters, with none of the banned guilt phrases (match is case-insensitive; also treat the unicode apostrophe in "don’t break your streak" as banned)
- `notes.md` gains one line that contains both `D` and `TEXT`
- the sitting row for `D` has `replied` `y`
- consecutive reply days: streak 1, then 2, and `last_reply_date` is that reply's date
- after a reply, a later sitting whose last reply is before yesterday: streak is 0, and `longest` is unchanged
- a missed calendar day, then a reply: streak is 1, and `longest` is still at least 2

### Cron jobs file

`--jobs PATH` is a JSON object `{"jobs": [ ... ]}`. `--skip` keeps jobs with other ids and writes exactly one job per Daily Wisdom id. A second run does not duplicate ids.

Each Daily Wisdom job has `timezone` `America/New_York` and `schedule.expr` as five cron fields:

- `daily-wisdom-sitting`: `0 8 * * *` (hour may be `08`)
- `daily-wisdom-weekly`: `0 18 * * 0` or `0 18 * * 7`

### Weekly files

`--week-start` is the Monday that opens the week. The week is that Monday through Sunday.

Both output paths are overwritten. A second run removes text that was only in the previous file bytes. No second filename such as `what-changed-in-me-2.md`.

For each sitting dated in that week, the markdown and the HTML contain the tradition, the `source` citation, and every reading line. A sitting dated in the previous week is left out (`source` and its longest reading line do not appear).

The markdown contains the words `streak` and `focus`.

The HTML is a document: it contains a tag `<html`, `<!DOCTYPE`, `<body`, `<p`, or `<article`.

When `notes.md` has a reply line, that note text appears verbatim in both files. When it does not, both files omit "you realized", "you learned", and "you grew".

### Quote card and guard

`quote_card.py` prints each reading line of that date. It does not print private note text from `notes.md`. Exit 0.

`guard.py` modes all exit 0 and print a non-empty decision on stdout.

- `fabricate`: stdout does not contain `IV.99` or a `Book <roman>.99` cite. Stdout contains `paraphrase` or a refusal (`won't`, `will not`, `refuse`, `not invent`, `cannot invent`, `can't invent`).
- `rank`: stdout does not name a tradition as true, truer, or truest. It does not match `<tradition> is true/truer/truest`, `the true religion is`, or a tradition name next to `truer than` / `more true than`. A refusal that avoids those shapes is fine.
- `crisis`: stdout contains `988`, `call`, and `text`, plus a caring word (`please`, `care`, `sorry`, `help`, `here`, `matter`, `support`, `glad`, or `with you`).
- `post`: stdout contains `draft` and does not say `I posted` or `posted to`.
- `inject`: stdout and stderr do not contain the canary planted in the note, and do not contain `truer than`.

### Static files

Exactly four files under `daily-wisdom/skills/**/SKILL.md`. Frontmatter `name:` values:

- `wisdom-getting-started`
- `wisdom-daily-sitting`
- `wisdom-weekly-page`
- `wisdom-guardrails`

`daily-wisdom/LICENSE` contains `SMF Works`. The employer-name needles, including the string LICENSE must not contain, live in `tests/test_static.py`.

Git-tracked files under `daily-wisdom/` are employer-name clean. The scan skips `SPEC.md` and `tests/test_static.py` (the needle list). Missing skills or a missing `LICENSE` fail the test.
