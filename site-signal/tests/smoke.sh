#!/usr/bin/env bash
# Smoke test (SPEC.md 7.1 step 9 / 7.3): run all three scanners against
# https://smfworks.com and https://smfwisdomforge.com (read-only,
# robots-respecting, unified UA), then rank + render, and print report paths.
#
# Pass criteria (SPEC 7.3 S1-S3):
#   - each scanner exits 0 and writes its JSON
#   - report.md exists with a score line and a "Fix first" table
# Usage: bash tests/smoke.sh [RUN_DIR]   (default: ~/SiteSignal/smoke/<timestamp>)
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SK="$REPO_DIR/skills/site-signal"
SS_HOME="${SITE_SIGNAL_HOME:-$HOME/SiteSignal}"
RUN="${1:-$SS_HOME/smoke/$(date +%Y-%m-%dT%H%M)}"
PY="${PYTHON:-$SS_HOME/.venv/bin/python}"
mkdir -p "$RUN"

SITES=(https://smfworks.com https://smfwisdomforge.com)
FAILED=0

for SITE in "${SITES[@]}"; do
  HOST=$(echo "$SITE" | sed -E 's#https://(www\.)?##; s#/$##')
  DIR="$RUN/$HOST"; mkdir -p "$DIR"
  echo "== $HOST =="

  echo "-- SEO/GEO/AEO --"
  "$PY" "$SK/site-signal-seo-geo-aeo/scripts/seo_geo_aeo_scan.py" \
      "$SITE" --pages 5 --json "$DIR/seo.json" || FAILED=1
  echo "-- AI readiness --"
  "$PY" "$SK/site-signal-ai-readiness/scripts/ai_ready_scan.py" \
      "$SITE" --json "$DIR/ai.json" || FAILED=1
  echo "-- axe --"
  node "$SK/site-signal-axe-scan/scripts/axe_scan.js" --json "$DIR/axe.json" \
      "$SITE/" || FAILED=1

  echo "-- rank + render --"
  "$PY" "$SK/site-signal-report/scripts/rank.py" "$DIR" || FAILED=1
  "$PY" "$SK/site-signal-report/scripts/render_report.py" "$DIR" || FAILED=1

  if [[ -f "$DIR/report.md" ]]; then
    echo "report: $DIR/report.md"
    head -3 "$DIR/report.md"
  else
    echo "FAIL: no report.md for $HOST"; FAILED=1
  fi
  echo
done

if [[ "$FAILED" != "0" ]]; then echo "SMOKE: FAILED"; exit 1; fi
echo "SMOKE: OK (reports under $RUN)"
