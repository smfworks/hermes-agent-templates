# ENV-NOTES — hermes-gatekeeper-prime (omarchy-2)

- Host: Linux omarchy-2. User mikesai1. Tree: /home/mikesai1/src/hermes-gatekeeper-prime
- Grok wrapper ~/.local/bin/grok hangs (mise). Use:
  /home/mikesai1/.local/share/mise/installs/npm-xai-official-grok/1.0.70/node_modules/.mise/@xai-official+grok@1.0.70/node_modules/@xai-official/grok/bin/grok
- Default model grok-4.7. Do not use spark-glm or MiniMax H3 for this build.
- gh wrapper ~/.local/bin/gh is broken. Use:
  /home/mikesai1/.local/share/mise/installs/gh/2.103.3/gh_2.103.3_linux_amd64/bin/gh
  (gh 2.103.3; `gh pr comment` has no --json; post comments via `gh api` issues comments)
- Git identity already set: Liam (SMF Works) / liam@smfworks.com
- Templates repo: /home/mikesai1/src/hermes-agent-templates (smfworks/hermes-agent-templates). Draft PR 2 (builder-prime-v1) still ships the old required-reviewer gate. Do not push main. Do not merge.
- Source skills: ~/src/prime-directive at 021a15d. examples/ruleset.json there already has required_approving_review_count: 0.
- Worktrees home: ~/GatekeeperPrime (create later, step 4).
