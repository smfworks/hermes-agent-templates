#!/usr/bin/env bash
# Paused until setup records a rhythm. Silent if there is nothing to say.
set -euo pipefail
MEM="${HERMES_PROFILE_HOME:-$HOME/.hermes/profiles/gatekeeper-prime}/memories/MEMORY.md"
if [[ ! -f "$MEM" ]] || ! grep -q 'gatekeeper-prime-setup: complete' "$MEM"; then
  exit 0
fi
echo "gatekeeper: morning digest is not filled in yet. Setup saved the marker; the owner still names which repos to summarize."
