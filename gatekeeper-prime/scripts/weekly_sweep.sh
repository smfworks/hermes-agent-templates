#!/usr/bin/env bash
# Paused weekly leftover sweep. Does not merge, does not close issues on its own.
set -euo pipefail
MEM="${HERMES_PROFILE_HOME:-$HOME/.hermes/profiles/gatekeeper-prime}/memories/MEMORY.md"
if [[ ! -f "$MEM" ]] || ! grep -q 'gatekeeper-prime-setup: complete' "$MEM"; then
  exit 0
fi
echo "gatekeeper: weekly sweep found no leftover file to walk. Non-blocking Lows become issues at review time."
