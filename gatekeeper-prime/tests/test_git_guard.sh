#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
G="$ROOT/scripts/git_guard.sh"
fail() { echo "FAIL: $*" >&2; exit 1; }

out=$(PROTECTED_BRANCH=main "$G" check-push -- origin feat/thing)
echo "$out" | grep -q "push check ok" || fail "feature push should pass"

if PROTECTED_BRANCH=main "$G" check-push -- origin main >/tmp/gg.out 2>/tmp/gg.err; then
  fail "push to main should refuse"
fi
grep -q "refusing push" /tmp/gg.err || fail "main refusal message missing"

if PROTECTED_BRANCH=main "$G" check-push -- -u origin HEAD:main >/tmp/gg.out 2>/tmp/gg.err; then
  fail "HEAD:main should refuse"
fi

set +e
PROTECTED_BRANCH=main "$G" check-push -- --force origin feat/thing >/tmp/gg.out 2>/tmp/gg.err
rc=$?
set -e
[[ "$rc" == "3" ]] || fail "force-push exit $rc, want 3"
grep -q "overwrite" /tmp/gg.err || fail "force-push should explain overwrite"

OWNER_CONFIRMED_OVERWRITE=yes OVERWRITE_REASON="replaces the typo commit" \
  PROTECTED_BRANCH=main "$G" check-push -- --force origin feat/thing | grep -q "push check ok" \
  || fail "confirmed force-push of a feature branch should pass the check"

if "$G" check-gh -- pr merge 1 >/tmp/gg.out 2>/tmp/gg.err; then
  fail "gh pr merge should refuse"
fi
grep -q "refusing gh pr merge" /tmp/gg.err || fail "merge refusal message"

if "$G" check-gh -- api repos/acme/app/pulls/1/merge >/tmp/gg.out 2>/tmp/gg.err; then
  fail "merge API should refuse"
fi

"$G" check-gh -- pr comment 1 --body hi | grep -q "gh check ok" || fail "pr comment should pass"
echo "git_guard: PASS"
