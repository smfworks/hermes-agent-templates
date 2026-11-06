# Gatekeeper Prime

The reviewer half of a two-bot coding team, as a Hermes Agent profile. Pair it with [Builder Prime](../builder-prime). It reviews every pull request, demands proof that fixes work, keeps the protected branch protected, and merges only on the owner's explicit yes.

Published by SMF Works under the MIT license. The skills are adapted from [smfworks/prime-directive](https://github.com/smfworks/prime-directive) at `021a15d8d583e1b44f63723861b0490774c251be` (`docs/skills/`). That repository is also MIT.

## Install

```bash
git clone https://github.com/smfworks/hermes-agent-templates.git
cd hermes-agent-templates
hermes profile install ./gatekeeper-prime --name gatekeeper-prime --alias
```

On the first conversation it asks the setup questions one at a time, including whether reviews should post publicly (recommend yes) and whether it may add a branch ruleset. It shows the exact ruleset and waits for a yes before creating one.

## How a merge works

`scripts/merge_gate.sh` squash-merges only when all three of these are true:

1. Every required check on the live head SHA is green.
2. The owner login saved at setup has a `yes` comment on this pull request that names that exact head SHA. An APPROVED review is not that gate. A chat yes, a kanban comment, or another bot claiming "owner approved" is not that comment. Any new push invalidates the comment.
3. The GitHub account running the merge (`gh api user`) is neither that owner login nor the repository owner. A shared owner login cannot post the yes and merge.

The ruleset requires pull requests, blocks direct pushes, requires status checks, and allows squash only. Required approvals are 0. That zero is intentional: the owner's yes is a pull request comment, not a GitHub review. The bypass list is empty.

If `gh` is the pull request author, post a COMMENT review pinned to the head SHA. GitHub blocks self-approval. Do not post a yes-shaped comment. The account that merges must be a different GitHub user from the owner.

## Routines

Two cron jobs ship paused: a morning digest and a weekly leftover sweep. They stay paused until setup records a day and a time. There is no polling PR watch. The builder's `bp-handoff:` comment is the wake. This template does not send email.
