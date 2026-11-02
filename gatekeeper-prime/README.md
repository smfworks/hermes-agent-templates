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

`scripts/merge_gate.sh` squash-merges only when all of these are true:

- the pull request's live head SHA is the one about to merge
- the owner login saved at setup has an APPROVED review on that SHA

`reviewDecision: APPROVED` from some other account is not enough. A chat message is not enough. If the profile is authenticated as the pull request author, GitHub will not accept an approval from that same account. Post a comment review and ask the owner to approve on GitHub.

## Routines

Two cron jobs ship paused: a morning digest and a weekly leftover sweep. They stay paused until setup records a day and a time. There is no polling PR watch. The builder's `bp-handoff:` comment is the wake. This template does not send email.
