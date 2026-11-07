# AI Claim Checker

AI Claim Checker (Verity) checks a specific AI launch post, benchmark chart, or price claim. You get a dated, sourced card with one of four verdicts: supported, vendor-only, contradicted, or unverifiable.

SMF Works publishes this template under the MIT license.

## Install

From a checkout of this repository:

```bash
hermes profile install ./ai-claim-checker --name claim-checker-dev --alias
```

`claim-checker-dev` is the development profile name. The distribution name is `ai-claim-checker`. Hermes Agent 0.22.0 or newer.

## After install

Copy `templates/USER.md` and `templates/MEMORY.md` into the profile `memories/` directory. Keep non-secret preferences only. Never put a password, a code, or an API key in memory or in chat.

Cards live under the profile data directory `claims/<slug>/`. The report is a markdown file and an HTML file there. There is no hosted link.

The profile tools are file, memory, skills, clarify, cronjob, todo, and web. Web search discovers URLs. The page-extract tool reads a page. A search snippet is discovery, not evidence. No terminal. No browser. No delegation.

The first conversation is the intro, then one setup question at a time. A pasted claim interrupts setup and runs the check.

The shipped `config.yaml` starts a model with `grok-4.7` and `provider: xai-oauth`. After install, copy `.env.EXAMPLE` to the profile `.env` and replace the placeholder if you want a live research key. Fixture smoke does not need that key:

```bash
cp ai-claim-checker/.env.EXAMPLE ~/.hermes/profiles/claim-checker-dev/.env
chmod 0600 ~/.hermes/profiles/claim-checker-dev/.env
```

If `hermes auth status xai-oauth` is already logged in, the placeholder may stay empty and the first chat should start. To point at a different provider instead:

```bash
hermes --profile claim-checker-dev config set model.default <model>
hermes --profile claim-checker-dev config set model.provider <provider>
```

Do not copy a host-local endpoint into this folder.

Optional live research may use a search key in the environment or the Hermes secret store. Documented Hermes tool names after checking this install: `web` toolset (search + page extract), `file`, `memory`, `skills`, `clarify`, `cronjob`, `todo`. If a screenshot arrives and vision is available in the chat, extract axes and numbers; otherwise ask for a transcription.

Weekly re-check stays off until an explicit yes. Tested commands:

```bash
hermes cron create "0 8 * * 1" --name verity-weekly-recheck --timezone America/New_York --script scripts/weekly.py --no-agent
```

Pass the timezone stored in `state.json`. Disable stops future delivery (`hermes cron delete` / `install_cron.py --disable` for the recorded job). Without a working scheduler, manual re-check still works.

## Skills

- `verity-getting-started`
- `verity-claim-decomposition`
- `verity-verdict-rubric`
- `verity-claim-card-format`

## Scripts

`--data` is the profile data directory. These scripts do not call a model.

- `scripts/onboard.py` walks intro and setup. A `--claim` interrupts.
- `scripts/decompose.py` keeps eight claims and the omitted count.
- `scripts/claim_validate.py` enforces the four verdicts, citations, run ids, and dates.
- `scripts/check.py` writes the card from a fixture pack. `--save` is separate.
- `scripts/weekly.py` re-checks saved claims and stays silent when nothing changed.
- `scripts/install_cron.py --yes` records the Monday 08:00 job. It does not call hermes.
- `scripts/guard.py` answers a guardrail check.

## Tests

From this directory:

```bash
bash tests/smoke.sh
```

That runs the file-level contract tests. It does not call a model. If `grok` is missing, smoke prints that you should install Grok Build or use Cursor, Claude Code, or Codex, then continues. It does not switch to another build CLI.

Liam owns the live smoke and the red-team in SPEC §8. The file-level tests are not the live red-team.

Public bot this template tracks: https://x.ai/bot/G48vC01p5cAxckACKFIaM
