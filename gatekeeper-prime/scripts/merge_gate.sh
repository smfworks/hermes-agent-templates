#!/usr/bin/env bash
# Reviewer-only. Squash-merge locked to the head SHA the owner said yes to.
#
# The gate, in order:
#   1. every required check on the head SHA is green — check runs AND
#      commit statuses; pending is not green. Required names come from
#      the evaluated rules on the protected branch (active repo and org
#      rulesets) with classic branch protection as a fallback. No rules
#      configured: treated as green, and the reason says so.
#   2. the owner login's own yes comment names that exact head SHA
#      (merge_decision.owner_yes_comment). A push after the yes
#      invalidates it; another bot's approval words do not count.
#   3. the yes-comment id goes into the merge log ($GK_MERGE_LOG,
#      default $HERE/merge_log), then squash-merge with
#      --match-head-commit so GitHub refuses a moved head server-side.
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
PROTECTED="${PROTECTED_BRANCH:-main}"

# The view is the single source of truth for state, head and comments.
# gh pr view uses the GraphQL API, which is where headRefOid lives; the
# REST pull response has no such field.
VIEW=$("$GH_BIN" pr view "$PR" --repo "$REPO" --json state,headRefOid,comments)
SHA=$(python3 -c 'import json,sys; print(json.load(sys.stdin).get("headRefOid") or "")' <<<"$VIEW")
[[ "$SHA" =~ ^[0-9a-fA-F]{40}$ ]] || SHA=""

# gh api prints a failed request's error body on stdout and exits non-zero,
# so a `$(...) || echo default` fallback concatenates the default onto the
# error body and the result is not JSON. Keep the body only on success;
# any failure falls back to the stated empty value.
gh_json() {
  local fallback="$1"; shift
  local out
  if out=$("$GH_BIN" "$@" 2>/dev/null); then
    printf '%s' "$out"
  else
    printf '%s' "$fallback"
  fi
}
BRANCH_RULES=$(gh_json "[]" api "repos/$REPO/rules/branches/$PROTECTED")
PROTECTION=$(gh_json "{}" api "repos/$REPO/branches/$PROTECTED/protection")
CHECK_RUNS=$(gh_json "[]" api "repos/$REPO/commits/$SHA/check-runs?per_page=100" --jq '.check_runs')
STATUSES=$(gh_json "[]" api "repos/$REPO/commits/$SHA/status?per_page=100" --jq '.statuses')

export VIEW OWNER BRANCH_RULES PROTECTION CHECK_RUNS STATUSES HERE
decision=$(python3 - <<'PY'
import json, os, sys
sys.path.insert(0, os.path.join(os.environ["HERE"], "lib"))
from merge_decision import checks_green, owner_yes_comment, required_contexts

view = json.loads(os.environ["VIEW"])
sha = view.get("headRefOid") or ""

required = required_contexts(json.loads(os.environ["BRANCH_RULES"]), json.loads(os.environ["PROTECTION"]))
green, checks_why = checks_green(
    required, json.loads(os.environ["CHECK_RUNS"]), json.loads(os.environ["STATUSES"]))
if not green:
    print("\t".join(["no", "checks", checks_why, sha, "", ""]))
    raise SystemExit(0)

ok, why, cid = owner_yes_comment(view, os.environ["OWNER"])
if not ok:
    print("\t".join(["no", "yes", why, sha, "", ""]))
    raise SystemExit(0)

print("\t".join(["yes", "ready", why, sha, "" if cid is None else str(cid), checks_why]))
PY
)
IFS=$'\t' read -r ok phase why sha cid checks_why <<<"$decision"
if [[ "$ok" != "yes" ]]; then
  echo "merge_gate: refused: $why" >&2
  exit 1
fi
echo "merge_gate: checks: $checks_why"
echo "merge_gate: $why"
if [[ "$DRY" == "1" ]]; then
  echo "merge_gate: dry-run, not merging"
  exit 0
fi

# The merge log records the yes comment's REST database id. gh pr view
# hands us GraphQL node ids, so resolve it through the node API; if that
# fails, record the id we have rather than losing it.
cid_num=""
if [[ "$cid" =~ ^[0-9]+$ ]]; then
  cid_num="$cid"
elif [[ -n "$cid" ]]; then
  cid_num=$("$GH_BIN" api graphql -f id="$cid" \
    -f query='query($id:ID!){ node(id: $id) { ... on IssueComment { databaseId } } }' \
    --jq '.data.node.databaseId' 2>/dev/null || true)
fi
LOG="${GK_MERGE_LOG:-$HERE/merge_log}"
printf '%s\t%s\tpr%s\t%s\tyes-comment %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$REPO" "$PR" "$sha" "${cid_num:-$cid}" >> "$LOG"

"$GH_BIN" pr merge "$PR" --repo "$REPO" --squash --match-head-commit "$sha"
echo "merge_gate: squash-merged $REPO#$PR at $sha (yes comment ${cid_num:-$cid})"
