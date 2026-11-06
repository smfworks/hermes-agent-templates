#!/usr/bin/env bash
# A shared owner login must not be able to post the yes comment and merge.
# gh is a stub. Nothing here hits the network.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
G="$ROOT/scripts/merge_gate.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }
SHA=aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

cat > "$TMP/gh" <<EOF
#!/usr/bin/env bash
if [[ "\$1" == "pr" ]]; then
  author="\${FAKE_AUTHOR:-ownerlogin}"
  printf '%s\n' "{\"state\":\"OPEN\",\"headRefOid\":\"${SHA}\",\"comments\":[{\"id\":7,\"author\":{\"login\":\"\${author}\"},\"body\":\"yes — approved at ${SHA}\"}]}"
  exit 0
fi
if [[ "\$1" == "api" && " \$* " == *" user "* ]]; then
  if [[ -n "\${FAKE_ACTOR:-}" ]]; then
    printf '%s\n' "\$FAKE_ACTOR"
    exit 0
  fi
  printf '%s' '{"message":"Requires authentication","status":"401"}'
  exit 1
fi
printf '%s' '{"message":"Branch not protected","status":"404"}'
exit 1
EOF
chmod +x "$TMP/gh"

# Same login as the owner: the yes comment is real, and the merge still refuses.
set +e
out=$(GH_BIN="$TMP/gh" FAKE_ACTOR=ownerlogin "$G" --repo ownerlogin/demo --pr 7 --owner-login ownerlogin --dry-run 2>&1)
rc=$?
set -e
[[ "$rc" -ne 0 ]] || fail "shared owner login was allowed to merge: $out"
grep -q "Traceback" <<< "$out" && fail "gate crashed: $out"
grep -qi "shared login" <<< "$out" || fail "refusal did not name the shared login: $out"
grep -qi "squash-merged" <<< "$out" && fail "shared login merged: $out"

# Missing actor (gh api user failed) fails closed even with a valid yes.
set +e
out=$(GH_BIN="$TMP/gh" "$G" --repo ownerlogin/demo --pr 7 --owner-login ownerlogin --dry-run 2>&1)
rc=$?
set -e
[[ "$rc" -ne 0 ]] || fail "missing actor was allowed to merge: $out"
grep -qi "could not read" <<< "$out" || fail "missing actor did not fail closed: $out"

# A different account may pass the dry run. It does not call pr merge.
set +e
out=$(GH_BIN="$TMP/gh" FAKE_ACTOR=merge-bot "$G" --repo ownerlogin/demo --pr 7 --owner-login ownerlogin --dry-run 2>&1)
rc=$?
set -e
[[ "$rc" -eq 0 ]] || fail "distinct merge account was refused: $out"
grep -q "dry-run, not merging" <<< "$out" || fail "dry-run did not stop before merge: $out"
grep -qi "squash-merged" <<< "$out" && fail "dry-run merged: $out"

# The repository owner login is refused even when --owner-login is someone else,
# as long as that someone else wrote the yes comment.
set +e
out=$(GH_BIN="$TMP/gh" FAKE_ACTOR=ownerlogin FAKE_AUTHOR=alice "$G" --repo ownerlogin/demo --pr 7 --owner-login alice --dry-run 2>&1)
rc=$?
set -e
[[ "$rc" -ne 0 ]] || fail "repository owner account was allowed to merge: $out"
grep -qi "repository owner" <<< "$out" || fail "refusal did not name the repository owner: $out"

echo "merge_gate_actor: PASS"
