#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
D="$ROOT/scripts/drive_coder.sh"
tmp=$(mktemp)
echo "do nothing" > "$tmp"
set +e
out=$(GROK_BIN="/no/such/grok-build" "$D" --cwd /tmp --prompt-file "$tmp" 2>&1)
rc=$?
set -e
rm -f "$tmp"
[[ "$rc" == "4" ]] || { echo "FAIL exit $rc"; echo "$out"; exit 1; }
echo "$out" | grep -q "Cursor" || { echo "FAIL missing Cursor"; exit 1; }
echo "$out" | grep -q "Claude Code" || { echo "FAIL missing Claude Code"; exit 1; }
echo "$out" | grep -q "Codex" || { echo "FAIL missing Codex"; exit 1; }
echo "$out" | grep -q "will not swap" || { echo "FAIL missing refusal"; exit 1; }
echo "drive_coder: PASS"
