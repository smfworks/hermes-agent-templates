#!/usr/bin/env bash
# Default smoke is offline. It does not call production sites and it does not
# require Chromium. Live scans are opt-in: SITE_SIGNAL_LIVE=1 and
# SITE_SIGNAL_LIVE_URLS="https://example.com".
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_DIR"

FAILED=0
PY="${PYTHON:-python3}"

if ! "$PY" -c 'import requests, bs4, yaml, jinja2, pytest' 2>/dev/null; then
  echo "FAIL: install site-signal/requirements.txt (requests, beautifulsoup4, PyYAML, Jinja2, pytest)" >&2
  exit 1
fi

echo "== pytest (fixtures) =="
"$PY" -m pytest -q tests/test_rank.py tests/test_seo_geo_aeo.py tests/test_ai_ready.py || FAILED=1

echo "== ownership seed =="
bash tests/test_verify_ownership.sh || FAILED=1

echo "== ship-fix gate =="
bash tests/test_ship_fix_gate.sh || FAILED=1

echo "== axe fixture =="
bash tests/test_axe_fixture.sh || FAILED=1

if [[ "${SITE_SIGNAL_LIVE:-}" == "1" ]]; then
  echo "== live scan (opt-in) =="
  if [[ -z "${SITE_SIGNAL_LIVE_URLS:-}" ]]; then
    echo "FAIL: SITE_SIGNAL_LIVE=1 needs SITE_SIGNAL_LIVE_URLS" >&2
    FAILED=1
  else
    SK="$REPO_DIR/skills/site-signal"
    RUN="${SITE_SIGNAL_LIVE_RUN:-/tmp/site-signal-live-smoke}"
    mkdir -p "$RUN"
    for SITE in $SITE_SIGNAL_LIVE_URLS; do
      HOST=$(echo "$SITE" | sed -E 's#https://(www\.)?##; s#/$##')
      DIR="$RUN/$HOST"
      mkdir -p "$DIR"
      "$PY" "$SK/site-signal-seo-geo-aeo/scripts/seo_geo_aeo_scan.py" \
        "$SITE" --pages 5 --json "$DIR/seo.json" || FAILED=1
      "$PY" "$SK/site-signal-ai-readiness/scripts/ai_ready_scan.py" \
        "$SITE" --json "$DIR/ai.json" || FAILED=1
      if command -v node >/dev/null 2>&1; then
        node "$SK/site-signal-axe-scan/scripts/axe_scan.js" --json "$DIR/axe.json" \
          "$SITE/" || FAILED=1
      else
        echo "SKIP live axe: node missing"
      fi
      "$PY" "$SK/site-signal-report/scripts/rank.py" "$DIR" || FAILED=1
      "$PY" "$SK/site-signal-report/scripts/render_report.py" "$DIR" || FAILED=1
    done
  fi
fi

if [[ "$FAILED" != "0" ]]; then
  echo "SMOKE: FAILED"
  exit 1
fi
echo "SMOKE: OK"
