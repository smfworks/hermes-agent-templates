# Receipts — The Money-Back Bot

Receipts reads the owner's email (read-only) and puts every subscription it can prove on one Money Back report: what renews this week, trials about to bill, price hikes, duplicates, usage spikes, and the top 3 cancel candidates. It drafts cancellation and refund mail. It never cancels, sends, pays, or logs in on its own.

SMF Works publishes this template under the MIT license.

## Install

From a checkout of this repository:

```bash
hermes profile install ./receipts --name receipts-dev --alias
```

`receipts-dev` is the development profile name. The distribution name is `receipts`. Hermes Agent 0.22.0 or newer.

## After install

Copy `templates/USER.md` and `templates/MEMORY.md` into the profile `memories/` directory. Placeholders are not an onboarding record. Keep non-secret preferences only. Never put a password, an app password, an API key, or a mail body in memory or in chat.

Subscriptions and the report live under the profile data directory `money-back/`. There is no hosted link.

Mail backends: Gmail API with `gmail.readonly` only, IMAP opened read-only, or a fixtures folder of `.eml` files. Tokens and app passwords live in the Hermes secrets store or a 0600 file outside the repo. Never commit them. Outlook is deferred.

The profile tools are file, memory, skills, clarify, cronjob, and todo. It has no terminal tool and no web tool. No send path.

The first conversation is a short intro, the email question, then a first scan and report before any other questions. Skip keeps the defaults (5-day heads-up, weekly Sunday 9:00 AM America/New_York). Cron jobs install only on an explicit yes.

The shipped `config.yaml` starts a model with `grok-4.7` and `provider: xai-oauth`. After install, copy `.env.EXAMPLE` to the profile `.env` and replace the placeholder:

```bash
cp receipts/.env.EXAMPLE ~/.hermes/profiles/receipts-dev/.env
chmod 0600 ~/.hermes/profiles/receipts-dev/.env
# Open that file and set: XAI_API_KEY=<paste-key-here>
```

If `hermes auth status xai-oauth` is already logged in, the placeholder may stay empty and the first chat should start. To point at a different provider instead:

```bash
hermes --profile receipts-dev config set model.default <model>
hermes --profile receipts-dev config set model.provider <provider>
```

Do not copy a host-local endpoint into this folder.

Owner-facing cron:

```bash
hermes cron create --timezone America/New_York --script --no-agent
```

Jobs: `money-back-weekly-scan` (Sun 09:00, or daily 08:00) and `money-back-renewal-reminders` (daily 08:30). Timezone names keep DST honest.

## Skills

- `money-back-getting-started`
- `money-back-scan`
- `money-back-page`
- `money-back-guardrails`

## Scripts

Cron runs scan and remind with `--script` and `--no-agent`. They do not call a model. `--data` is the profile `money-back/` directory.

- `scripts/mail_fetch.py` reads mail.
- `scripts/scan.py` writes `subscriptions.csv` and `findings.jsonl`. Same mail, same CSV.
- `scripts/page.py` overwrites `money-back.md` and `money-back.html`.
- `scripts/onboard.py` walks `setup_step`.
- `scripts/install_cron.py --yes` records the two job ids. It does not register a live job.
- `scripts/remind.py` reminds once per charge.
- `scripts/draft.py` writes `.eml` drafts.
- `scripts/cancel_help.py` prints steps and a link.
- `scripts/share_card.py` prints a text card with no unverified savings.
- `scripts/guard.py` answers a guardrail check.

## Tests

From this directory:

```bash
bash tests/smoke.sh
```

That runs the file-level contract tests. It does not call a model. If `grok` is missing, smoke prints that you should install Grok Build or use Cursor, Claude Code, or Codex, then continues. It does not switch to another build CLI.

Liam owns the live smoke and the red-team in SPEC §10. The file-level tests are not the live red-team.
