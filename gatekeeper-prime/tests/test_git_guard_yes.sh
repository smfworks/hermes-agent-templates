#!/usr/bin/env bash
# The bot's gh path must never carry a yes-shaped comment. The owner types
# their own yes, and merge_gate refuses when the merge account is that
# same login. Everything here runs with check-gh, so nothing hits the network.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
G="$ROOT/scripts/git_guard.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa   # 40 hex

# 1. A yes-shaped pr comment is refused, and the refusal never leaks the
#    pattern itself.
set +e
"$G" check-gh -- pr comment 7 --repo smfworks/x --body "yes — approved at $SHA" \
  >"$TMP/out" 2>"$TMP/err"
rc=$?
set -e
[[ "$rc" -ne 0 ]] || fail "yes-shaped pr comment passed the guard"
if grep -qF '^yes' "$TMP/out" "$TMP/err"; then
  fail "refusal leaked the regex pattern"
fi
grep -q "owner" "$TMP/err" || fail "refusal should tell the bot why"

# 2. The same body on the real gh path is refused before exec, so it can
#    never reach GitHub.
set +e
"$G" gh -- pr comment 7 --repo smfworks/x --body "yes — approved at $SHA" \
  >"$TMP/out" 2>"$TMP/err"
rc=$?
set -e
[[ "$rc" -ne 0 ]] || fail "yes-shaped comment passed the guard on the gh path"

# 3. A yes posted through the issues-comments API is refused too.
set +e
"$G" check-gh -- api --method POST repos/smfworks/x/issues/7/comments \
  -f body="yes — approved at $SHA" >"$TMP/out" 2>"$TMP/err"
rc=$?
set -e
[[ "$rc" -ne 0 ]] || fail "yes-shaped api comment passed the guard"

# 3b. A body arriving on stdin (--input -) is inspected as well, JSON or raw.
set +e
echo "{\"body\": \"yes — approved at $SHA\"}" | "$G" check-gh -- api --method POST \
  repos/smfworks/x/issues/7/comments --input - >"$TMP/out" 2>"$TMP/err"
rc=$?
printf 'yes — approved at %s\n' "$SHA" | "$G" check-gh -- api --method POST \
  repos/smfworks/x/issues/7/comments --input - >"$TMP/out2" 2>"$TMP/err2"
rc2=$?
set -e
[[ "$rc" -ne 0 ]] || fail "stdin JSON yes body passed the guard"
[[ "$rc2" -ne 0 ]] || fail "stdin raw yes body passed the guard"

# 4. handoff's bp-handoff body names a SHA and still passes.
"$G" check-gh -- api --method POST repos/smfworks/x/issues/7/comments \
  -f body="bp-handoff: to=builder-prime from=gatekeeper-prime sha=$SHA pr=7

merged on the owner's yes" | grep -q "gh check ok" \
  || fail "bp-handoff comment must pass the guard"

# 5. Plain comments pass, even ones that mention yes mid-sentence.
"$G" check-gh -- pr comment 7 --repo smfworks/x --body "looks good; say yes to the owner maybe" \
  | grep -q "gh check ok" || fail "plain comment must pass the guard"

# 6. GK_YES_REGEX steers the filter on both sides; with the override, the
#    plain "yes <sha>" shape no longer matches it.
set +e
GK_YES_REGEX='^ship it: yes\b' "$G" check-gh -- pr comment 7 --repo smfworks/x \
  --body "ship it: yes — approved at $SHA" >"$TMP/out" 2>"$TMP/err"
rc=$?
set -e
[[ "$rc" -ne 0 ]] || fail "override pattern did not refuse its own yes shape"
GK_YES_REGEX='^ship it: yes\b' "$G" check-gh -- pr comment 7 --repo smfworks/x \
  --body "yes — approved at $SHA" | grep -q "gh check ok" \
  || fail "override pattern should replace the default, not add to it"

echo "git_guard_yes: PASS"
