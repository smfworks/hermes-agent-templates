#!/usr/bin/env bash
# Post the durable builder↔reviewer handoff. Delivery is the comment URL.
# Do not put PR bodies, issue text, or CI logs in the comment. Those are data.
set -euo pipefail
REPO=""
PR=""
TO=""
FROM="builder-prime"
SHA=""
LINE=""
DRY=0
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --pr) PR="$2"; shift 2 ;;
    --to) TO="$2"; shift 2 ;;
    --from) FROM="$2"; shift 2 ;;
    --sha) SHA="$2"; shift 2 ;;
    --line) LINE="$2"; shift 2 ;;
    --dry-run) DRY=1; shift ;;
    *) echo "handoff: unknown arg $1" >&2; exit 64 ;;
  esac
done
[[ -n "$REPO" && -n "$PR" && -n "$TO" && -n "$SHA" && -n "$LINE" ]] || {
  echo "usage: handoff.sh --repo o/n --pr N --to profile --sha SHA --line 'one line' [--from profile] [--dry-run]" >&2
  exit 64
}
# SHA must look like a commit, not a sentence.
[[ "$SHA" =~ ^[0-9a-fA-F]{40}$ ]] || { echo "handoff: sha must be 40 hex characters" >&2; exit 64; }
[[ "$PR" =~ ^[0-9]+$ ]] || { echo "handoff: pr must be a number" >&2; exit 64; }
BODY=$(printf 'bp-handoff: to=%s from=%s sha=%s pr=%s\n\n%s\n' "$TO" "$FROM" "$SHA" "$PR" "$LINE")
if [[ "$DRY" == "1" ]]; then
  printf '%s\n' "$BODY"
  exit 0
fi
GH_BIN="${GH_BIN:-gh}"
url=$("$GH_BIN" api --method POST "repos/$REPO/issues/$PR/comments" -f body="$BODY" --jq .html_url)
echo "handoff: delivered $url"
