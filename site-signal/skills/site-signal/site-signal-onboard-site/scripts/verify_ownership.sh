#!/usr/bin/env bash
# Ownership verification for Site Signal (SPEC.md 5.1 step 3).
# Checks one method and exits 0 (verified) or 1 (NOT verified — fail closed).
# The agent records the passing method as verified_by in ~/SiteSignal/sites.yaml.
#
# Usage:
#   verify_ownership.sh --domain DOMAIN --method seed+owner|repo|wellknown|dns
#                       [--repo OWNER/NAME] [--token ss-...] [--gh-bin PATH]
#                       [--timeout SECONDS]
#   verify_ownership.sh --generate-token      # mint a token for methods wellknown/dns
#
# Exit codes: 0 verified; 1 not verified (fail closed); 2 usage/environment error.
# Never prints secrets; the deny-terms list is unrelated here. GH_BIN overrides the
# gh binary (the ~/.local/bin/gh mise wrapper deadlocks on this host); the default
# is the working binary recorded in PREREQ-RESULTS.md.
set -euo pipefail

GH_BIN_DEFAULT="$HOME/.local/share/mise/installs/gh/2.103.3/gh_2.103.3_linux_amd64/bin/gh"
UA="SMFWorks-SiteSignal/1.0 (+https://smfworks.com)"
METHOD="" DOMAIN="" REPO="" TOKEN="" TIMEOUT=20

die() { echo "verify_ownership: $*" >&2; exit "${2:-2}"; }
log() { echo "verify_ownership: $*"; }

resolve_gh() {
  local gh="${GH_BIN:-$GH_BIN_DEFAULT}"
  if [[ ! -x "$gh" ]]; then
    # Fall back to the newest mise-installed gh (version-bump resilience).
    local cand
    cand=$(ls -1 "$HOME"/.local/share/mise/installs/gh/*/*/bin/gh 2>/dev/null | sort -V | tail -1 || true)
    [[ -n "$cand" ]] && gh="$cand"
  fi
  [[ -x "$gh" ]] || die "no working gh binary; set GH_BIN (bare \`gh\` is a broken mise wrapper here)" 2
  printf '%s' "$gh"
}

normalize_domain() {
  local d="${1#*://}"; d="${d%%/*}"; d="${d%%:*}"; printf '%s' "$(echo "$d" | tr 'A-Z' 'a-z')"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --method) METHOD="$2"; shift 2 ;;
    --domain) DOMAIN="$2"; shift 2 ;;
    --repo) REPO="$2"; shift 2 ;;
    --token) TOKEN="$2"; shift 2 ;;
    --gh-bin) export GH_BIN="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --generate-token)
      printf 'ss-%s\n' "$(head -c 16 /dev/urandom | od -An -tx1 | tr -d ' \n' | head -c 16)"
      exit 0 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) die "unknown argument: $1" 2 ;;
  esac
done

[[ -n "$DOMAIN" ]] || die "--domain is required" 2
[[ -n "$METHOD" ]] || die "--method is required" 2
DOMAIN="$(normalize_domain "$DOMAIN")"

case "$METHOD" in
  seed+owner)
    # SPEC.md 5.1 step 3a: domains observed under owner work in Oct 2026.
    # Membership alone is NOT verification — the agent must record the owner's
    # chat confirmation before writing verified_by: seed+owner.
    case "$DOMAIN" in
      smfwisdomforge.com)
        log "in seed list: $DOMAIN -> smfworks/wisdomforge"
        log "agent must record the owner's chat confirmation, then save verified_by: seed+owner"
        exit 0 ;;
      smfclearinghouse.com|www.smfclearinghouse.com)
        log "in seed list: $DOMAIN -> smfworks/aiclearinghouse-site (www and apex serve the same site)"
        log "agent must record the owner's chat confirmation, then save verified_by: seed+owner"
        exit 0 ;;
      smfworks.com)
        log "in seed list: $DOMAIN -> smfworks/smfworks-site"
        log "agent must record the owner's chat confirmation, then save verified_by: seed+owner"
        log "note: smfworks.com is scan_only until Michael assigns fix ownership (SPEC.md 6.3)"
        exit 0 ;;
      *)
        log "NOT in seed list — fail closed (try --method repo|wellknown|dns)"
        exit 1 ;;
    esac ;;

  repo)
    [[ -n "$REPO" ]] || die "--repo OWNER/NAME is required for --method repo" 2
    GH="$(resolve_gh)"
    homepage="$(timeout "$((TIMEOUT + 25))" "$GH" api "repos/$REPO" --jq '.homepage // ""' 2>/dev/null)" \
      || die "gh could not read $REPO (access missing?) — fail closed" 1
    [[ -n "$homepage" ]] || die "$REPO has no homepage field pointing at a domain — fail closed" 1
    home_host="$(normalize_domain "$homepage")"
    if [[ "$home_host" == "$DOMAIN" || "$home_host" == "www.$DOMAIN" \
       || "$DOMAIN" == "www.${home_host#www.}" ]]; then
      log "verified: $REPO homepage ($home_host) points at $DOMAIN — verified_by: repo"
      exit 0
    fi
    log "NOT verified: $REPO homepage is '$homepage' (wanted $DOMAIN) — fail closed"
    exit 1 ;;

  wellknown)
    [[ -n "$TOKEN" ]] || die "--token ss-... is required for --method wellknown" 2
    body="$(curl -fsSL --max-time "$TIMEOUT" -A "$UA" \
      "https://$DOMAIN/.well-known/site-signal.txt" 2>/dev/null)" \
      || { log "NOT verified: no reachable /.well-known/site-signal.txt at $DOMAIN — fail closed"; exit 1; }
    if grep -qx "$TOKEN" <<<"$body" || grep -q "$TOKEN" <<<"$body"; then
      log "verified: token matched at https://$DOMAIN/.well-known/site-signal.txt — verified_by: wellknown"
      exit 0
    fi
    log "NOT verified: token file present but does not contain the expected token — fail closed"
    exit 1 ;;

  dns)
    [[ -n "$TOKEN" ]] || die "--token ss-... is required for --method dns" 2
    txt=""
    if command -v dig >/dev/null 2>&1; then
      txt="$(dig +short TXT "site-signal-verification.$DOMAIN" +time="$TIMEOUT" +tries=1 2>/dev/null || true)"
    elif command -v nslookup >/dev/null 2>&1; then
      txt="$(nslookup -type=TXT "site-signal-verification.$DOMAIN" 2>/dev/null | grep 'text =' || true)"
    else
      die "need dig or nslookup for --method dns" 2
    fi
    if grep -q "$TOKEN" <<<"$txt"; then
      log "verified: DNS TXT site-signal-verification.$DOMAIN contains the token — verified_by: dns"
      exit 0
    fi
    log "NOT verified: no matching TXT record — fail closed"
    exit 1 ;;

  *) die "unknown method: $METHOD (seed+owner|repo|wellknown|dns)" 2 ;;
esac
