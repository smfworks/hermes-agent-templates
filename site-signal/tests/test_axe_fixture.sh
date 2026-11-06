#!/usr/bin/env bash
# Axe fixture test (SPEC.md 7.1 step 8): run axe_scan.js against tests/fixtures/bad-a11y.html
# served on localhost; must report >=1 critical or serious violation. Exit non-zero otherwise.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
AXE_SCRIPT="$REPO_DIR/skills/site-signal/site-signal-axe-scan/scripts/axe_scan.js"

# Chromium: CHROME_PATH, else a browser on PATH. Skip when it is missing.
if [[ -z "${CHROME_PATH:-}" ]]; then
  for c in /usr/bin/chromium /usr/bin/chromium-browser /usr/bin/google-chrome; do
    [[ -x "$c" ]] && CHROME_PATH="$c" && break
  done
fi
if [[ -z "${CHROME_PATH:-}" ]] || ! command -v node >/dev/null 2>&1; then
  echo "SKIP: axe fixture needs node and Chromium (set CHROME_PATH)"
  exit 0
fi
export CHROME_PATH

# axe deps (puppeteer-core, axe-core) are not committed. Install them when npm
# is available; otherwise skip so a fresh checkout still passes.
AXE_DEPS_DIR="$(cd "$(dirname "$AXE_SCRIPT")" && pwd)"
if [[ ! -d "$AXE_DEPS_DIR/node_modules/puppeteer-core" || ! -d "$AXE_DEPS_DIR/node_modules/axe-core" ]]; then
  NPM_BIN="$(command -v npm 2>/dev/null || true)"
  if [[ -z "$NPM_BIN" ]]; then
    echo "SKIP: axe fixture needs npm dependencies in $AXE_DEPS_DIR"
    exit 0
  fi
  echo "node_modules missing — running npm ci in $AXE_DEPS_DIR" >&2
  if ! ( cd "$AXE_DEPS_DIR" && "$NPM_BIN" ci --no-audit --no-fund ) >/dev/null 2>&1; then
    echo "SKIP: npm ci failed; axe fixture not run"
    exit 0
  fi
fi

# Serve fixtures on a free port.
PORT=$(python3 - <<'PY'
import socket
s=socket.socket(); s.bind(("127.0.0.1",0)); print(s.getsockname()[1]); s.close()
PY
)
python3 -m http.server "$PORT" --bind 127.0.0.1 --directory "$SCRIPT_DIR/fixtures" >/dev/null 2>&1 &
SRV=$!
trap 'kill $SRV 2>/dev/null' EXIT
sleep 1

OUT="$(mktemp)"; trap 'kill $SRV 2>/dev/null; rm -f "$OUT"' EXIT
if ! node "$AXE_SCRIPT" --json "$OUT" "http://127.0.0.1:$PORT/bad-a11y.html" > /dev/null 2>&1; then
  echo "FAIL: axe_scan.js exited non-zero" >&2
  exit 1
fi

python3 - "$OUT" <<'PY'
import json, sys
data = json.load(open(sys.argv[1]))
def counts(d):
    c = {}
    for page in (d if isinstance(d, list) else [d]):
        v = page.get("violations", page if isinstance(page, dict) and "violations" in page else [])
        for x in v:
            c[x["impact"]] = c.get(x["impact"], 0) + len(x.get("nodes", []))
    return c
c = counts(data)
crit = c.get("critical", 0); ser = c.get("serious", 0)
print(f"axe fixture: critical={crit} serious={ser}")
if crit + ser < 1:
    print("FAIL: no critical or serious violation reported for bad-a11y.html" )
    sys.exit(1)
print("PASS: bad-a11y.html reports at least one critical/serious violation")
PY
