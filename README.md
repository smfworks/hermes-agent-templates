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
| `site-signal` | Scans sites you own for SEO, GEO, AEO, AI readiness, and accessibility. Ranks issues by impact and opens fix PRs when you ask. | In progress. Not on `main` yet. |

New templates land as a pull request. Do not push to `main`. Do not commit `.env`, tokens, or session data.

## License

MIT. See [LICENSE](LICENSE). Copyright 2026 SMF Works.
