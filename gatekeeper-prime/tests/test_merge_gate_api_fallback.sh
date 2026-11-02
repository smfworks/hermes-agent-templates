#!/usr/bin/env bash
# gh api prints a failed request's error body on stdout and exits non-zero.
# merge_gate's fallbacks must keep only a successful body; gluing the
# fallback onto the error body makes JSON that json.loads rejects, and the
# gate crashes instead of refusing. Nothing here hits the network: gh is a
# stub that returns the exact 404 body the real API returns.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
G="$ROOT/scripts/merge_gate.sh"
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT
fail() { echo "FAIL: $*" >&2; exit 1; }

cat > "$TMP/gh" <<'STUB'
#!/usr/bin/env bash
# Stub gh: pr view returns a valid open PR with no comments; every api
# call returns the 404 error body on stdout and exits 1.
case "$1" in
  pr)
    printf '%s\n' '{"state":"OPEN","headRefOid":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","comments":[]}'
    ;;
  api)
    printf '%s' '{"message":"Branch not protected","documentation_url":"https://docs.github.com/rest/branches/branch-protection#get-branch-protection","status":"404"}'
    exit 1
    ;;
esac
STUB
chmod +x "$TMP/gh"

set +e
out=$(GH_BIN="$TMP/gh" "$G" --repo smfworks/x --pr 7 --owner-login smfworks 2>&1)
rc=$?
set -e
[[ "$rc" -ne 0 ]] || fail "gate did not refuse a PR with no yes comment"
grep -q "Traceback" <<< "$out" && fail "gate crashed parsing the 404 body: $out"
grep -qi "refus" <<< "$out" || fail "refusal did not say why: $out"

echo "merge_gate_api_fallback: PASS"
