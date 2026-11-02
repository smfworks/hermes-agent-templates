#!/usr/bin/env bash
# Reviewer-only. Squash-merge locked to the SHA the owner reviewed.
# Refuses unless that login has an APPROVED review whose commit is the live head.
set -euo pipefail
REPO=""
PR=""
OWNER=""
DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --pr) PR="$2"; shift 2 ;;
    --owner-login) OWNER="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "merge_gate: unknown arg $1" >&2; exit 64 ;;
  esac
done
[[ -n "$REPO" && -n "$PR" && -n "$OWNER" ]] || {
  echo "usage: merge_gate.sh --repo o/n --pr N --owner-login LOGIN [--dry-run]" >&2
  exit 64
}
[[ "$PR" =~ ^[0-9]+$ ]] || { echo "merge_gate: pr must be a number" >&2; exit 64; }
GH_BIN="${GH_BIN:-gh}"
HERE=$(cd "$(dirname "$0")/.." && pwd)
VIEW=$("$GH_BIN" pr view "$PR" --repo "$REPO" --json reviewDecision,reviews,headRefOid,state)
export VIEW OWNER
decision=$(python3 - <<PY
import json, os, sys
sys.path.insert(0, "${HERE}/lib")
from merge_decision import owner_approved
view = json.loads(os.environ["VIEW"])
ok, why = owner_approved(view, os.environ["OWNER"])
print(("yes" if ok else "no") + "\t" + why + "\t" + (view.get("headRefOid") or ""))
PY
)
ok="${decision%%$'\t'*}"
rest="${decision#*$'\t'}"
why="${rest%%$'\t'*}"
sha="${rest##*$'\t'}"
if [[ "$ok" != "yes" ]]; then
  echo "merge_gate: refused: $why" >&2
  exit 1
fi
echo "merge_gate: $why ($sha)"
if [[ "$DRY" == "1" ]]; then
  echo "merge_gate: dry-run, not merging"
  exit 0
fi
"$GH_BIN" pr merge "$PR" --repo "$REPO" --squash --match-head-commit "$sha"
echo "merge_gate: squash-merged $REPO#$PR at $sha"
