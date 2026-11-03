#!/usr/bin/env bash
# GitHub's waiter, not an agent poll loop.
set -euo pipefail
REPO=""
PR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --pr) PR="$2"; shift 2 ;;
    *) echo "wait_checks: unknown arg $1" >&2; exit 64 ;;
  esac
done
[[ -n "$REPO" && -n "$PR" ]] || { echo "usage: wait_checks.sh --repo o/n --pr N" >&2; exit 64; }
GH_BIN="${GH_BIN:-gh}"
exec "$GH_BIN" pr checks "$PR" --repo "$REPO" --watch --fail-fast --required
