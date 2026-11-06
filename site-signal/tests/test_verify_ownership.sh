#!/usr/bin/env bash
# The public seed list is empty. No domain, including the placeholder, is
# pre-verified. repo/wellknown/dns remain the mechanical checks.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
V="$ROOT/skills/site-signal/site-signal-onboard-site/scripts/verify_ownership.sh"
fail() { echo "FAIL: $*" >&2; exit 1; }

for domain in example.com www.example.com; do
  set +e
  out=$("$V" --domain "$domain" --method seed+owner 2>&1)
  rc=$?
  set -e
  [[ "$rc" -eq 1 ]] || fail "seed+owner verified $domain (rc $rc): $out"
  grep -q "empty" <<< "$out" || fail "seed refusal did not say the list is empty: $out"
done

# The script text itself must not carry a trusted seed of real sites.
# The scanner contact URL is not a seed entry.
if grep -E 'smfwisdomforge|smfclearinghouse' "$V" >/dev/null; then
  fail "verify_ownership.sh still names a seeded site"
fi
if grep -n 'smfworks\.com' "$V" | grep -v 'SMFWorks-SiteSignal' >/dev/null; then
  fail "verify_ownership.sh still names a seeded site"
fi

example="$ROOT/sites.yaml.example"
python3 - "$example" <<'PY' || fail "example registry is not a safe placeholder"
import sys, yaml
data = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
sites = data.get("sites") or []
assert sites, "no sites"
for site in sites:
    domain = str(site.get("domain") or "")
    assert domain in {"example.com", "www.example.com"}, domain
    assert site.get("owner_verified") is False, domain
    assert site.get("merge", "ask") == "ask", domain
    assert "merge_consent" not in site
text = open(sys.argv[1], encoding="utf-8").read()
for banned in ("smfwisdomforge", "smfclearinghouse"):
    assert banned not in text, banned
print("example registry: placeholder only")
PY

token=$("$V" --generate-token)
[[ "$token" == ss-* ]] || fail "generate-token did not mint an ss- token"

echo "verify_ownership: PASS"
