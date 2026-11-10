<p align="center">
  <img src="docs/hero.jpg" alt="Hermes Agent Templates — by SMF Works" width="880">
</p>


# Hermes Agent Templates

Profile templates for [Hermes Agent](https://hermes-agent.nousresearch.com/docs), published by SMF Works under the MIT license.

Each template is a directory with its own `distribution.yaml`. Install from a checkout of that directory. `hermes profile install` reads `distribution.yaml` at the root of the path you give it, so a git URL of this whole repo is not an install target.

```bash
git clone https://github.com/smfworks/hermes-agent-templates.git
cd hermes-agent-templates
hermes profile install ./site-signal --name site-signal --alias
```

Replace `site-signal` with the template you want. The alias gives you a `site-signal` command, which is `hermes -p site-signal`.

## What's here

| Directory | What it does | Status |
|---|---|---|
| `site-signal` | Scans sites you own for SEO, GEO, AEO, AI readiness, and accessibility. Ranks issues by impact and opens fix PRs when you ask. | On main. Fix PRs stay drafts until you approve. A fresh install does not treat any site as yours. |
| `builder-prime` | Plans, codes, tests, and opens pull requests. Never merges. Pair with Gatekeeper Prime. | On main. Never merges. Offline gates run in CI. |
| `gatekeeper-prime` | Reviews every pull request and squash-merges only after the owner's yes comment on that head SHA, from a different GitHub account than the one running the merge. | On main. Same merge gate as Builder Prime describes. |
| `bourne-bot` | Personal OPSEC advisor. Four skills, advice only. The profile has no terminal tool; the owner runs the scripts. | On main. Contract tests run in CI. |
| `daily-wisdom` | Morning sitting: one short reading, one sentence of context, one question. Four skills, no connectors. | On main. Contract tests run in CI. |
| `receipts` | Money-back bot. Read-only mail, one report, drafts only, never sends. | On main. Contract tests run in CI. |
| `roast-my-feed` | Wrapped-style audit of a public X handle. Witty, never cruel, every number real. | On main. Contract tests run in CI. |
| `explain-it-like-a-movie` | 60-second sourced explainer that plays like a trailer. Script, captions, then a 9:16 video. | On main. Contract tests run in CI. Video render skips when ffmpeg or TTS is missing. |
| `ai-claim-checker` | Dated, sourced card for an AI launch, benchmark, or price claim. Four verdicts only. | On main. Contract tests run in CI. |
| `fare-hawk` | Name a place and dates; day-by-day itinerary, three flights and three hotels, opt-in fare watch. You book. | On main. Contract tests run in CI. |
| `ai-daily-radar` | Short morning AI brief: up to 7 tagged changes for your stack. Radar reads and reports. | Draft. Contract tests on this PR. Awaiting Liam live smoke and owner yes. |

New templates land as a pull request. Do not push to `main`. Do not commit `.env`, tokens, or session data.

## License

MIT. See [LICENSE](LICENSE). Copyright 2026 SMF Works.

## Credits

Builder Prime and Gatekeeper Prime adapt the [prime-directive](https://github.com/smfworks/prime-directive) skills (`021a15d8d583e1b44f63723861b0490774c251be`). That repository is MIT.

Site Signal's accessibility scan depends on [axe-core](https://github.com/dequelabs/axe-core), Mozilla Public License 2.0. The library is installed by the axe script; it is not vendored here.
