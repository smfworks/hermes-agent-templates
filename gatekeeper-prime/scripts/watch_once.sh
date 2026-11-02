#!/usr/bin/env bash
# One-off watcher for a single PR (the §10 self-deleting check watch).
# Waits until the PR's checks resolve or the PR closes or merges, then
# exits 0. Sleeps between API probes — the house rule is event waits, not
# polling loops — and gives up with a note after 30 minutes.
set -euo pipefail
REPO=""
PR=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --pr) PR="$2"; shift 2 ;;
    *) echo "watch_once: unknown arg $1" >&2; exit 64 ;;
  esac
done
[[ -n "$REPO" && -n "$PR" ]] || { echo "usage: watch_once.sh --repo o/n --pr N" >&2; exit 64; }
[[ "$PR" =~ ^[0-9]+$ ]] || { echo "watch_once: pr must be a number" >&2; exit 64; }
GH_BIN="${GH_BIN:-gh}"
MAX_SECONDS="${GK_WATCH_MAX_SECONDS:-1800}"   # 30 minutes, then give up with a note
PAUSE="${GK_WATCH_PAUSE:-25}"                 # >= 20s between API probes
START=$SECONDS

while :; do
  # State first: a merged or closed PR ends the watch immediately.
  state=$("$GH_BIN" pr view "$PR" --repo "$REPO" --json state --jq .state 2>/dev/null || true)
  case "$state" in
    MERGED) echo "watch_once: $REPO#$PR merged; watch done"; exit 0 ;;
    CLOSED) echo "watch_once: $REPO#$PR closed; watch done"; exit 0 ;;
  esac
  # gh pr checks: 0 all green, 1 at least one failed, 8 still pending.
  # Any final state counts as resolved; the caller decides what to do.
  rc=0
  "$GH_BIN" pr checks "$PR" --repo "$REPO" >/dev/null 2>&1 || rc=$?
  case "$rc" in
    0) echo "watch_once: checks green on $REPO#$PR"; exit 0 ;;
    1) echo "watch_once: checks finished with failures on $REPO#$PR"; exit 0 ;;
  esac
  if (( SECONDS - START >= MAX_SECONDS )); then
    echo "watch_once: checks still not resolved on $REPO#$PR after ${MAX_SECONDS}s; giving up"
    exit 0
  fi
  sleep "$PAUSE"
done
