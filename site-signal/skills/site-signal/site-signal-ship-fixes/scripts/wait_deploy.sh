#!/usr/bin/env bash
# Wait for the production deploy of a merged commit, then curl-verify the
# artifact on the live domain (SPEC.md 5.4 step 8).
#
# Usage:
#   wait_deploy.sh REPO MERGE_SHA DOMAIN [--path /some/artifact]
#       [--expect-status 200] [--expect-contains SUBSTRING]
#       [--timeout 900] [--interval 20] [--skip-checks] [--gh-bin PATH]
#
# Defaults: poll GitHub check runs + deployment statuses on MERGE_SHA for a
# Vercel/production success (≤15 min), then curl https://DOMAIN/ expecting 200.
#
# Exit codes: 0 deployed and artifact verified; 1 artifact check failed;
# 2 deploy not observed within --timeout (nothing verified — check manually).
# GH_BIN overrides the gh binary (the ~/.local/bin/gh mise wrapper deadlocks on
# this host); the default is the working binary recorded in PREREQ-RESULTS.md.
set -uo pipefail

GH_BIN_DEFAULT="$HOME/.local/share/mise/installs/gh/2.103.3/gh_2.103.3_linux_amd64/bin/gh"
UA="SMFWorks-SiteSignal/1.0 (+https://smfworks.com)"

REPO="" SHA="" DOMAIN="" PATH_="/" EXPECT_STATUS=200 EXPECT_CONTAINS=""
TIMEOUT=900 INTERVAL=20 SKIP_CHECKS=0

die() { echo "wait_deploy: $*" >&2; exit "${2:-2}"; }
log() { echo "wait_deploy: $*"; }

resolve_gh() {
  local gh="${GH_BIN:-$GH_BIN_DEFAULT}"
  if [[ ! -x "$gh" ]]; then
    local cand
    cand=$(ls -1 "$HOME"/.local/share/mise/installs/gh/*/*/bin/gh 2>/dev/null | sort -V | tail -1 || true)
    [[ -n "$cand" ]] && gh="$cand"
  fi
  [[ -x "$gh" ]] || die "no working gh binary; set GH_BIN (bare \`gh\` is a broken mise wrapper here)" 2
  printf '%s' "$gh"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --path) PATH_="$2"; shift 2 ;;
    --expect-status) EXPECT_STATUS="$2"; shift 2 ;;
    --expect-contains) EXPECT_CONTAINS="$2"; shift 2 ;;
    --timeout) TIMEOUT="$2"; shift 2 ;;
    --interval) INTERVAL="$2"; shift 2 ;;
    --skip-checks) SKIP_CHECKS=1; shift ;;
    --gh-bin) export GH_BIN="$2"; shift 2 ;;
    -h|--help) sed -n '2,16p' "$0"; exit 0 ;;
    *) if [[ -z "$REPO" ]]; then REPO="$1"; elif [[ -z "$SHA" ]]; then SHA="$1";
       elif [[ -z "$DOMAIN" ]]; then DOMAIN="$1"; else die "unexpected argument: $1" 2; fi; shift ;;
  esac
done
[[ -n "$REPO" && -n "$SHA" && -n "$DOMAIN" ]] || die "usage: wait_deploy.sh REPO MERGE_SHA DOMAIN [options]" 2
GH="$(resolve_gh)"

deploy_observed=""
if [[ "$SKIP_CHECKS" -ne 1 ]]; then
  log "polling deploy status for $REPO@$SHA (timeout ${TIMEOUT}s)…"
  deadline=$(( $(date +%s) + TIMEOUT ))
  while [[ $(date +%s) -lt $deadline ]]; do
    # 1) Check runs on the merge SHA (Vercel posts "Vercel"/"vercel (Production)").
    cr="$(timeout 30 "$GH" api "repos/$REPO/commits/$SHA/check-runs" \
      --jq '[.check_runs[] | select((.name | ascii_downcase) | test("vercel|deploy|production"))
             | select(.conclusion == "success") | .name] | unique | .[0] // ""' 2>/dev/null || true)"
    if [[ -n "$cr" ]]; then
      log "deploy confirmed by check run: $cr (success)"; deploy_observed="check-run:$cr"; break
    fi
    # 2) Deployment statuses on the merge SHA (environment production/success).
    dep="$(timeout 30 "$GH" api "repos/$REPO/deployments?sha=$SHA" \
      --jq '[.[] | select((.environment // "") | test("production"; "i"))][0].id // ""' 2>/dev/null || true)"
    if [[ -n "$dep" ]]; then
      st="$(timeout 30 "$GH" api "repos/$REPO/deployments/$dep/statuses" --jq '.[0].state // ""' 2>/dev/null || true)"
      if [[ "$st" == "success" ]]; then
        log "deploy confirmed by deployment status (env production, success)"; deploy_observed="deployment:$dep"; break
      fi
    fi
    sleep "$INTERVAL"
  done
  if [[ -z "$deploy_observed" ]]; then
    echo "wait_deploy: TIMED OUT after ${TIMEOUT}s — no successful deploy check on $REPO@$SHA." >&2
    echo "wait_deploy: the deploy may still be building; check the Vercel dashboard, then re-run with --skip-checks." >&2
    exit 2
  fi
else
  log "skipping deploy-check polling (--skip-checks); curl-verifying directly"
fi

# --- curl-verify the artifact ---------------------------------------------------
url="https://$DOMAIN$PATH_"
body="$(mktemp)"; trap 'rm -f "$body"' EXIT
code="$(curl -sS -o "$body" -w '%{http_code}' --max-time 30 -A "$UA" "$url" 2>/dev/null)" \
  || { echo "wait_deploy: FAIL curl could not reach $url" >&2; exit 1; }
if [[ "$code" != "$EXPECT_STATUS" ]]; then
  echo "wait_deploy: FAIL $url returned $code (expected $EXPECT_STATUS) — deploy not verified." >&2
  exit 1
fi
if [[ -n "$EXPECT_CONTAINS" ]] && ! grep -qF -- "$EXPECT_CONTAINS" "$body"; then
  echo "wait_deploy: FAIL $url returned $code but does not contain the expected artifact content." >&2
  exit 1
fi
log "verified: $url -> $code${EXPECT_CONTAINS:+ (contains expected content)}"
log "deploy wait complete ($deploy_observed)."
exit 0
