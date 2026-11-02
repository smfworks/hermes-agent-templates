#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
H="$ROOT/scripts/handoff.sh"
SHA="0123456789abcdef0123456789abcdef01234567"
out=$("$H" --dry-run --repo acme/app --pr 57 --to gatekeeper-prime --from builder-prime --sha "$SHA" --line "PR 57 fixes the null check.")
echo "$out" | grep -q "^bp-handoff: to=gatekeeper-prime from=builder-prime sha=$SHA pr=57$" || { echo "FAIL header"; echo "$out"; exit 1; }
echo "$out" | grep -q "null check" || { echo "FAIL line"; exit 1; }
if "$H" --dry-run --repo acme/app --pr 57 --to gk --sha "not-a-sha" --line hi >/tmp/ho.out 2>/tmp/ho.err; then
  echo "FAIL bad sha should refuse"; exit 1
fi
echo "handoff: PASS"
