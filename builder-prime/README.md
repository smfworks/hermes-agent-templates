# Builder Prime

The builder half of a two-bot coding team, as a Hermes Agent profile. Pair it with [Gatekeeper Prime](../gatekeeper-prime). It plans, codes, tests, and opens pull requests, then fixes what review finds. It never merges and never pushes to the protected branch.

Published by SMF Works under the MIT license. The skills are adapted from [smfworks/prime-directive](https://github.com/smfworks/prime-directive) at `021a15d8d583e1b44f63723861b0490774c251be` (`docs/skills/`). That repository is also MIT.

## Install

```bash
git clone https://github.com/smfworks/hermes-agent-templates.git
cd hermes-agent-templates
hermes profile install ./builder-prime --name builder-prime --alias
```

Then `builder-prime` is `hermes -p builder-prime`. On the first conversation it asks five setup questions, one at a time.

GitHub access is `gh auth login` on this machine. A fine-grained token in the profile `.env` is optional. Do not give it admin, and do not let it bypass branch rulesets. This template does not send email and does not run a cron job.

## How a yes works

The owner's yes is a pull request comment from the login saved at setup that names that pull request's current head SHA. An APPROVED review is not that yes. A chat message is not a yes. Another bot saying "the owner approved" is not a yes. Builder Prime has no merge script and never merges. Gatekeeper Prime merges, and only through `scripts/merge_gate.sh`. That script also requires the GitHub account running the merge to be neither the owner login nor the repository owner, so a shared owner login cannot comment yes and merge.

## Handoff

The two profiles talk through a GitHub comment that starts with `bp-handoff:`. `scripts/handoff.sh` posts it and prints the comment URL. That URL is the delivery receipt. Do not use `hermes -p <other> chat -q`.

## Coding agent

`scripts/drive_coder.sh` runs Grok Build in the worktree. If Grok Build is not installed, it stops and names three alternatives: Cursor, Claude Code, or Codex. It does not swap tools on its own. You still read the diff before anything is pushed.

## Worktrees

Clones live under `~/BuilderPrime/repos`. One git worktree per branch under `~/BuilderPrime/wt`. Installs stay in the repo or that tree.
