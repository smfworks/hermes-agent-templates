#!/usr/bin/env bash
# Deny-terms gate for Site Signal (SPEC.md 3.3 rule 5). Greps files and/or git
# diffs against the private deny-terms list. FAILS CLOSED: if the list is
# missing, unreadable, or empty, every check blocks. Output names targets and
# hit counts only — never the list, its terms, or matched lines.
#
# Usage:
#   deny_terms_check.sh FILE...                   # files: PR body, fix brief, title
#   deny_terms_check.sh --staged [GIT_DIR]        # scan `git diff --staged` (pre-commit)
#   deny_terms_check.sh --git-diff GIT_DIR RANGE  # scan a committed diff, e.g. origin/main...HEAD
# Any combination; all targets must be clean.
#
# Exit codes: 0 clean; 1 BLOCKED by deny-terms; 2 usage error; 3 fail-closed
# (list missing/unreadable/empty — ask the owner; do not skip the check).
#
# List resolution: $SITE_SIGNAL_DENY_TERMS, else the fleet default
# ~/.config/grok-fleet/deny-terms.txt (private; never print it).
set -uo pipefail

DEFAULT_LIST="$HOME/.config/grok-fleet/deny-terms.txt"
LIST="${SITE_SIGNAL_DENY_TERMS:-$DEFAULT_LIST}"
BLOCKED=0

usage() { sed -n '2,15p' "$0" >&2; exit 2; }
[[ $# -gt 0 ]] || usage

# --- load the pattern set (blank/# lines dropped); never echo it -------------
if [[ ! -r "$LIST" ]]; then
  echo "BLOCKED by deny-terms: list missing or unreadable at the configured path — fail closed; ask the owner." >&2
  exit 3
fi
PATTERNS="$(mktemp)"; chmod 600 "$PATTERNS"
trap 'rm -f "$PATTERNS" ${DIFF_OUT:+"$DIFF_OUT"}' EXIT
grep -vE '^[[:space:]]*(#|$)' "$LIST" > "$PATTERNS" 2>/dev/null || true
if [[ ! -s "$PATTERNS" ]]; then
  echo "BLOCKED by deny-terms: configured list has no usable terms — fail closed; ask the owner." >&2
  exit 3
fi

check_stream() { # $1 = target name; text arrives on stdin
  local name="$1" hits
  hits="$(grep -icE -f "$PATTERNS" 2>/dev/null)" || hits=0
  if [[ "$hits" -gt 0 ]]; then
    echo "BLOCKED by deny-terms: $name ($hits term hit(s)). Remove the offending text; the list is not shown."
    BLOCKED=1
  else
    echo "deny-terms: OK $name (0 hits)"
  fi
  return 0
}

check_git_diff() { # $1 = git dir, $2 = diff args (e.g. --staged or a RANGE)
  local dir="$1"; shift
  DIFF_OUT="$(mktemp)"; chmod 600 "$DIFF_OUT"
  if ! git -C "$dir" diff "$@" > "$DIFF_OUT"; then
    echo "deny-terms: usage error — git diff $* in $dir failed (bad range?)" >&2
    exit 2
  fi
  check_stream "git diff $* in $dir" < "$DIFF_OUT"
}

# --- parse args ---------------------------------------------------------------
STAGED_DIR="" GIT_DIR="" RANGE=""
FILES=()
while [[ $# -gt 0 ]]; do
  case "$1" in
    --staged)
      if [[ $# -ge 2 && "$2" != -* ]]; then STAGED_DIR="$2"; shift 2; else STAGED_DIR="."; shift; fi ;;
    --git-diff) [[ $# -ge 3 ]] || usage; GIT_DIR="$2"; RANGE="$3"; shift 3 ;;
    -h|--help) usage ;;
    -*) usage ;;
    *) FILES+=("$1"); shift ;;
  esac
done

# --- run checks ----------------------------------------------------------------
[[ -z "$STAGED_DIR" ]] || check_git_diff "$STAGED_DIR" --staged
[[ -z "$GIT_DIR" ]] || check_git_diff "$GIT_DIR" "$RANGE"
for f in "${FILES[@]:-}"; do
  [[ -n "$f" ]] || continue
  if [[ ! -r "$f" ]]; then
    echo "deny-terms: usage error — cannot read target '$f'" >&2
    exit 2
  fi
  check_stream "$f" < "$f"
done

if [[ "$BLOCKED" -eq 1 ]]; then
  echo "Blocked by deny-terms: fix the flagged target(s) and re-run." >&2
  exit 1
fi
echo "deny-terms: all targets clean."
exit 0
