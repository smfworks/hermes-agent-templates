# Receipts script contract

All scripts live under `receipts/scripts/` and take `--data DIR` (a temp dir in tests). Never write to the real `~/.hermes`.

`--data DIR` is the profile data directory itself (SPEC's `money-back/` folder). These files live directly in `DIR`:

- `subscriptions.csv`
- `findings.jsonl`
- `state.json`
- `money-back.md`
- `money-back.html`
- `drafts/`
- `inbox/` (optional; tests pass `--inbox` instead)

A script that writes `state.json` merges into the existing object and leaves keys it does not own in place.

Do not call `hermes`. Do not call a model. Do not register a live cron job.

Frozen clock: `--now YYYY-MM-DD`. Tests use `2026-11-04`. First-run lookback is 60 days from `--now`.

`--inbox DIR` is a folder of `.eml` files (fixtures backend).

## Commands

1. `python3 scripts/onboard.py --data DIR --step intro`

   Prints the intro, including "I'm Receipts, your money-back bot" and "Gmail or IMAP?". Sets `setup_step` to `intro_done`. If `setup_step` is already set, also offers resume.

2. `python3 scripts/onboard.py --data DIR --step email --backend fixtures [--account ADDR]`

   Records the backend. Sets `setup_step` to `email_done`. Does not stall when no mail is connected. Does not ask the window or cadence question.

3. `python3 scripts/onboard.py --data DIR --step scan --inbox DIR --now YYYY-MM-DD [--backend fixtures]`

   Runs the scan and rebuilds the report. Sets `setup_step` to `scanned`. Stdout then asks the heads-up window question. Window and cadence are still unset until those steps run.

4. `python3 scripts/onboard.py --data DIR --step window --skip`

   Sets `window` to 5. Sets `setup_step` to `window_done`.

5. `python3 scripts/onboard.py --data DIR --step cadence --skip`

   Sets cadence to weekly Sunday 09:00 and `tz` to `America/New_York`. Sets `setup_step` to `cadence_done`. Does not write cron jobs.

6. `python3 scripts/scan.py --data DIR --inbox DIR --backend fixtures --now YYYY-MM-DD`

   Writes `subscriptions.csv` and `findings.jsonl`. Idempotent on the same mail.

7. `python3 scripts/page.py --data DIR --now YYYY-MM-DD`

   Overwrites `money-back.md` and `money-back.html` in place (same paths, no second filename).

8. `python3 scripts/install_cron.py --data DIR --jobs PATH --yes`

   Writes two jobs into `PATH` with ids `money-back-weekly-scan` and `money-back-renewal-reminders`, timezone `America/New_York`. Without `--yes`, writes no jobs. Does not call `hermes`.

9. `python3 scripts/remind.py --data DIR --now YYYY-MM-DD`

   One reminder per active/trial item whose next renewal is inside the window. Keyed by service+renewal date in `state.json` `reminded`. A second run for the same charge prints nothing new.

10. `python3 scripts/draft.py --data DIR --service NAME --kind cancel|refund`

    Writes `DIR/drafts/*.eml` with To, Subject, Body. Prints the body. Does not send.

11. `python3 scripts/cancel_help.py --service NAME`

    Prints steps and an https account/cancel link. Does not ask for a password.

12. `python3 scripts/share_card.py --data DIR [--names]`

    Text-only. Totals and "found N subscriptions". Service names only with `--names`. Savings line only when verified savings > 0.

13. `python3 scripts/guard.py --mode MODE [--text TEXT]`

    Modes: `cancel_for_me` | `login_password` | `inject_forward` | `inject_card` | `fake_savings` | `delete_mail` | `unsubscribe` | `inject`

    All exit 0 with non-empty stdout.

## subscriptions.csv

UTF-8 CSV header:

```
service,plan,amount,currency,cadence,last_charge,next_renewal,renewal_is_estimate,status,kind,source_msg_ids,evidence_quote,notes,sender
```

- `amount` is a number string or empty. Missing amount is empty here; the report says `unknown — open receipt`.
- `renewal_is_estimate` is `y` or `n`.
- `status` is `active`, `trial`, `cancelled`, or `unknown`.
- `kind` is `fixed` or `usage`.
- `source_msg_ids` is semicolon-separated Message-IDs, unique, latest receipt wins for the row, ids appended on later receipts of the same key.
- `sender` is the mail From header. The report source column is sender + last_charge date.
- Dedupe key = service + plan + cadence. One row per key.
- One-time purchases and promotions are absent.
- Rows sorted by service, then plan, then cadence.

## findings.jsonl

One JSON object per line: `id`, `type`, `service`, `evidence`, `first_seen`, `alerted_at`, `resolved`.

`evidence` is an object with `sender`, `date`, `subject`, `message_id`, `quote`. No evidence → no finding.

`id` is stable: hex digest of `service|type|date`. A finding already present is not re-alerted (`alerted_at` stays the first value).

Types include: `renewal_window`, `trial_bill`, `price_increase`, `duplicate`, `usage_spike`, `lapsed`, `inject`.

## state.json

JSON object. Merge, do not drop unknown keys.

| Key | Owner | Shape |
| --- | --- | --- |
| `setup_step` | `onboard.py` | `intro_done` / `email_done` / `scanned` / `window_done` / `cadence_done` |
| `backend` | `onboard.py --step email` | `fixtures` / `gmail` / `imap` |
| `account` | `onboard.py --step email` | address or empty |
| `window` | `onboard.py --step window` | integer 3, 5, or 7. `scan.py` and `page.py` read this. Default 5. |
| `cadence` | `onboard.py --step cadence` | `weekly` / `daily` / `demand` |
| `tz` | `onboard.py --step cadence` | `America/New_York` by default |
| `last_scan` | `scan.py` | `YYYY-MM-DD` |
| `reminded` | `remind.py` | object, keys `service|YYYY-MM-DD` → true |
| `saved_ledger` | page/draft flow | list of proven savings objects |

## Cron jobs file

`--jobs PATH` is `{"jobs": [ ... ]}`. `--yes` keeps jobs with other ids and writes exactly one job per Receipts id. A second run does not duplicate ids. Without `--yes`, Receipts ids are not written.

Each Receipts job has `timezone` `America/New_York` and `schedule.expr` as five cron fields:

- `money-back-weekly-scan`: `0 9 * * 0` (hour may be `09`; dow `0` or `7`) when cadence is weekly
- `money-back-renewal-reminders`: `30 8 * * *` (hour may be `08`)

## Report files

Both output paths are overwritten. A second run removes text that was only in the previous file bytes. No `money-back-2.md`.

Markdown and HTML contain:

- monthly burn
- a usage section separate from fixed subscriptions
- renewing this window
- trials about to bill
- price hikes with old → new
- top 3 cancel candidates in order: duplicates, then price increases, then trials about to bill, then lapsed/unknown; each labeled `your call`
- the full subscription table with sender and date
- verified savings only when proven
- footer: `Try Hermes: Receipts — The Money-Back Bot by SMF Works`

Banned in md/html/share card: last-4 card digits presented as a card, street addresses, invoice `https://` links, account ids.

Missing amount appears as `unknown — open receipt`. Estimated renewals include `estimate`.

## Guard and drafts

`draft.py` writes a file ending in `.eml` under `DIR/drafts/`. Stdout contains the body. It does not print `sent` as a completed send.

`cancel_help.py` stdout contains `http` and does not contain `password`.

`guard.py`:

- `cancel_for_me`: contains `draft` or `steps`; does not claim it cancelled (`cancelled for you`, `i cancelled`)
- `login_password`: refuse login; no `logged in`
- `inject_forward` / `inject_card` / `inject`: report the mail as data, do not follow; do not print the canary `EVIL-OK-441`; do not print a card number
- `fake_savings`: refuse proven savings; stdout contains `potential`
- `delete_mail` / `unsubscribe`: refuse

`share_card.py` without verified savings: contains `found` and a count; does not contain `$` savings.

## Static files

Exactly four files under `receipts/skills/**/SKILL.md`. Frontmatter `name:` values:

- `money-back-getting-started`
- `money-back-scan`
- `money-back-page`
- `money-back-guardrails`

`receipts/LICENSE` contains `SMF Works`. Employer-name needles live in `tests/test_static.py`.

Git-tracked files under `receipts/` are employer-name clean. The scan skips `SPEC.md` and `tests/test_static.py`. Missing skills or a missing `LICENSE` fail the test.

The same static test fails if tracked files contain send/modify needles listed there, or a committed secret marker.
