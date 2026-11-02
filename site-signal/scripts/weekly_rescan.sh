#!/usr/bin/env bash
# Site Signal weekly re-scan (SPEC.md 5.5, Mode A) — no-agent cron script.
#
# Scans every owner_verified site in $SS_HOME/sites.yaml with all three
# scanners, ranks + renders a report into $SS_HOME/reports/<domain>/, and
# compares against the domain's last entry in $SS_HOME/history.jsonl.
# Prints a short diff ONLY when:
#   - a score (overall/SEO/GEO/AEO/AI readiness) dropped >= 3 points, or
#   - a new critical/serious issue appeared (including more violation nodes
#     on a critical/serious axe rule), or
#   - a scan step failed.
# Empty stdout = silent tick. The first scan of a site is silent (no prior
# baseline to diff against; PLAN-site-signal.md: no invented deltas).
#
# Cron runs NEVER open or merge PRs and never push anywhere (SPEC.md 5.5);
# the only writes are under $SS_HOME. Hard configuration errors print one
# ERROR line and exit 1; everything else is reported per the rules above.
#
# Scheduled by cron/jobs.json as "site-signal-weekly-rescan" (Mondays 08:00
# America/New_York, shipped PAUSED — enable only after the owner says yes).
# Hermes runs .sh scripts under bash and resolves script paths against
# $HERMES_HOME/scripts, so this works both from the profile checkout and
# after `hermes profile install`.
#
# Usage: weekly_rescan.sh   (no arguments; env overrides below)
#   SITE_SIGNAL_HOME   data dir            (default ~/SiteSignal, then config.yaml)
#   SITE_SIGNAL_PROFILE profile dir        (default: script location, then
#                                          ~/.hermes/profiles/site-signal)
#   PYTHON             fallback interpreter when $SS_HOME/.venv is missing
#   GH_BIN / NODE_BIN  binary overrides (see the resolution blocks below)
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------- profile root (holds skills/) -----------------------------------
if [[ -d "$SCRIPT_DIR/../skills/site-signal" ]]; then
  PROFILE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
elif [[ -n "${SITE_SIGNAL_PROFILE:-}" && -d "$SITE_SIGNAL_PROFILE/skills/site-signal" ]]; then
  PROFILE_ROOT="$SITE_SIGNAL_PROFILE"
elif [[ -d "$HOME/.hermes/profiles/site-signal/skills/site-signal" ]]; then
  PROFILE_ROOT="$HOME/.hermes/profiles/site-signal"
else
  PROFILE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
fi

SS_HOME="${SITE_SIGNAL_HOME:-$HOME/SiteSignal}"
pick_python() {
  if [[ -x "$SS_HOME/.venv/bin/python3" ]]; then PY="$SS_HOME/.venv/bin/python3"; else PY="${PYTHON:-python3}"; fi
}
pick_python

# Precedence: an explicitly set SITE_SIGNAL_HOME wins (offline tests, custom
# layouts); otherwise config.yaml (skills.config.site_signal.home); otherwise
# ~/SiteSignal.
if [[ -z "${SITE_SIGNAL_HOME:-}" && -f "$PROFILE_ROOT/config.yaml" ]]; then
  cfg_home="$("$PY" - "$PROFILE_ROOT/config.yaml" <<'PYEOF' 2>/dev/null || true
import sys
try:
    import yaml
    sc = ((yaml.safe_load(open(sys.argv[1])) or {}).get("skills") or {}).get("config") or {}
    print(str((sc.get("site_signal") or {}).get("home") or ""))
except Exception:
    print("")
PYEOF
)"
  if [[ -n "$cfg_home" ]]; then
    SS_HOME="$cfg_home"
    SS_HOME="${SS_HOME/#\~/$HOME}"
  fi
fi
pick_python

fail() { echo "Site Signal weekly re-scan: ERROR: $*"; exit 1; }

SEO_PY="$PROFILE_ROOT/skills/site-signal/site-signal-seo-geo-aeo/scripts/seo_geo_aeo_scan.py"
AI_PY="$PROFILE_ROOT/skills/site-signal/site-signal-ai-readiness/scripts/ai_ready_scan.py"
AXE_JS="$PROFILE_ROOT/skills/site-signal/site-signal-axe-scan/scripts/axe_scan.js"
RANK_PY="$PROFILE_ROOT/skills/site-signal/site-signal-report/scripts/rank.py"
RENDER_PY="$PROFILE_ROOT/skills/site-signal/site-signal-report/scripts/render_report.py"
for f in "$SEO_PY" "$AI_PY" "$AXE_JS" "$RANK_PY" "$RENDER_PY"; do
  [[ -f "$f" ]] || fail "missing $f — is the site-signal profile installed?"
done

# gh resolution — same convention as ship_fix.sh/wait_deploy.sh (GH_BIN env
# override, then the working binary recorded in PREREQ-RESULTS.md, then the
# newest mise install). Weekly runs never invoke gh: cron opens and merges no
# PRs (SPEC.md 5.5); resolving it here keeps any operator-added verification
# off the broken bare `gh` mise wrapper on this host.
GH_BIN="${GH_BIN:-$HOME/.local/share/mise/installs/gh/2.103.3/gh_2.103.3_linux_amd64/bin/gh}"
if [[ ! -x "$GH_BIN" ]]; then
  cand="$(ls -1 "$HOME"/.local/share/mise/installs/gh/*/*/bin/gh 2>/dev/null | sort -V | tail -1 || true)"
  [[ -n "$cand" ]] && GH_BIN="$cand"
fi
export GH_BIN

# node for the axe scanner: PATH first, then the mise installs (cron's env may
# lack the mise shims).
NODE_BIN="${NODE_BIN:-$(command -v node 2>/dev/null || true)}"
if [[ -z "$NODE_BIN" ]]; then
  cand="$(ls -1 "$HOME"/.local/share/mise/installs/node/*/bin/node 2>/dev/null | sort -V | tail -1 || true)"
  [[ -n "$cand" ]] && NODE_BIN="$cand"
fi

# npm for the axe scanner's node_modules (puppeteer-core, axe-core): the deps
# are gitignored and not shipped in the profile, so they must be restored with
# `npm ci` in the axe scripts dir (PREREQ-NOTES.md). npm lives next to node in
# the mise installs (cron's env may lack the mise shims).
NPM_BIN=""
if [[ -n "$NODE_BIN" && -x "$(dirname "$NODE_BIN")/npm" ]]; then
  NPM_BIN="$(dirname "$NODE_BIN")/npm"
fi
[[ -n "$NPM_BIN" ]] || NPM_BIN="$(command -v npm 2>/dev/null || true)"

ensure_axe_deps() { # $1 = log file — npm ci once if the axe scripts dir has no node_modules
  local axe_dir; axe_dir="$(dirname "$AXE_JS")"
  [[ -d "$axe_dir/node_modules" ]] && return 0
  if [[ -z "$NPM_BIN" ]]; then
    echo "npm not found — cannot restore axe node_modules (run: npm ci in $axe_dir)" >> "$1"
    return 1
  fi
  echo "node_modules missing — running npm ci in $axe_dir" >> "$1"
  ( cd "$axe_dir" && timeout 300 "$NPM_BIN" ci --no-audit --no-fund ) >> "$1" 2>&1
}

[[ -d "$SS_HOME" ]] || fail "$SS_HOME does not exist yet — run the first scan/onboarding"
SITES_YAML="$SS_HOME/sites.yaml"
[[ -f "$SITES_YAML" ]] || fail "no $SITES_YAML — onboard a site first (site-signal-onboard-site)"

# One run at a time; an overlapping tick stays silent.
if command -v flock >/dev/null 2>&1; then
  exec 9>"$SS_HOME/.weekly_rescan.lock"
  flock -n 9 || exit 0
fi

sites_list="$(mktemp /tmp/ss-sites.XXXXXX)"
trap 'rm -f "$sites_list"' EXIT

# owner_verified sites only, as DOMAIN<TAB>PAGES<TAB>AXE_PATHS (space-joined).
"$PY" - "$SITES_YAML" > "$sites_list" <<'PYEOF'
import sys
try:
    import yaml
except ImportError:
    sys.stderr.write("pyyaml is not installed for this interpreter\n")
    sys.exit(1)
try:
    data = yaml.safe_load(open(sys.argv[1])) or {}
except Exception as e:
    sys.stderr.write(f"cannot read {sys.argv[1]}: {e}\n")
    sys.exit(1)
for s in data.get("sites") or []:
    if not isinstance(s, dict) or not s.get("owner_verified"):
        continue
    domain = s.get("domain")
    if not domain:
        continue
    scan = s.get("scan") or {}
    pages = scan.get("pages") or 5
    paths = " ".join(str(p) for p in (scan.get("axe_paths") or ["/"]))
    print(f"{domain}\t{pages}\t{paths}")
PYEOF
[[ $? -eq 0 ]] || fail "could not parse $SITES_YAML"

while IFS=$'\t' read -r domain pages axe_paths; do
  [[ -n "$domain" ]] || continue
  run_dir="$SS_HOME/reports/$domain/$(date +%Y-%m-%dT%H%M)-weekly"
  mkdir -p "$run_dir"
  LOG="$run_dir/scan.log"; FAILS="$run_dir/failures.txt"
  : > "$LOG"; : > "$FAILS"
  echo "== $domain $(date -u '+%Y-%m-%dT%H:%M:%SZ') ==" >> "$LOG"

  # Baseline: the domain's last history.jsonl entry (before this run appends)
  # plus that run's report.json for issue-level comparison.
  PREV="$run_dir/.prev.json"
  "$PY" - "$SS_HOME" "$domain" "$PREV" <<'PYEOF' >> "$LOG" 2>&1 || true
import json, sys
from pathlib import Path
ss_home, domain, out = sys.argv[1:4]
prev = {"prior": False, "metrics": {}, "issues": [], "axe_nodes": []}
hist = Path(ss_home) / "history.jsonl"
if hist.exists():
    last = None
    for line in hist.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue
        if rec.get("domain") == domain:
            last = rec
    if last:
        prev["prior"] = True
        prev["metrics"] = {"overall": last.get("overall"), "seo": last.get("seo"),
                           "geo": last.get("geo"), "aeo": last.get("aeo"),
                           "ai_ready": last.get("ai_ready")}
        run = last.get("run")
        if run:
            try:
                rep = json.loads((Path(run) / "report.json").read_text())
            except Exception:
                rep = None
            if isinstance(rep, dict):
                prev["issues"] = [[i.get("dimension"), i.get("id")] for i in rep.get("issues") or []]
                prev["axe_nodes"] = [[i.get("id"), int(i.get("nodes") or 0)]
                                     for i in rep.get("issues") or []
                                     if i.get("dimension") == "a11y"]
Path(out).write_text(json.dumps(prev))
PYEOF

  seo_rc=0; ai_rc=0; axe_rc=0
  timeout 900 "$PY" "$SEO_PY" "https://$domain" --pages "${pages:-5}" --json "$run_dir/seo.json" >> "$LOG" 2>&1 || seo_rc=$?
  timeout 300 "$PY" "$AI_PY" "https://$domain" --json "$run_dir/ai.json" >> "$LOG" 2>&1 || ai_rc=$?
  if [[ -n "$NODE_BIN" ]]; then
    ensure_axe_deps "$LOG" || true  # axe below fails loudly into FAILS if the restore failed
    # shellcheck disable=SC2086
    axe_urls=(); for p in $axe_paths; do
      case "$p" in http*) axe_urls+=("$p") ;; *) axe_urls+=("https://$domain$p") ;; esac
    done
    timeout 600 "$NODE_BIN" "$AXE_JS" --json "$run_dir/axe.json" "${axe_urls[@]}" >> "$LOG" 2>&1 || axe_rc=$?
  else
    echo "node not found — axe skipped" >> "$LOG"
    axe_rc=127
  fi
  [[ "$seo_rc" -eq 0 ]] || echo "seo scanner failed (exit $seo_rc)" >> "$FAILS"
  [[ "$ai_rc" -eq 0 ]] || echo "ai-readiness scanner failed (exit $ai_rc)" >> "$FAILS"
  [[ "$axe_rc" -eq 0 ]] || echo "axe scanner failed (exit $axe_rc)" >> "$FAILS"

  timeout 120 "$PY" "$RANK_PY" "$run_dir" --ss-home "$SS_HOME" >> "$LOG" 2>&1 \
    || echo "rank.py failed (exit $?)" >> "$FAILS"
  timeout 120 "$PY" "$RENDER_PY" "$run_dir" >> "$LOG" 2>&1 \
    || echo "report render failed" >> "$FAILS"

  # Print a short diff only on regression / new critical-serious / failure.
  site_out="$("$PY" - "$domain" "$PREV" "$run_dir" <<'PYEOF'
import json, sys
from pathlib import Path
domain, prev_path, run_dir = sys.argv[1], Path(sys.argv[2]), Path(sys.argv[3])

def load(p):
    try:
        return json.loads(Path(p).read_text())
    except Exception:
        return None

alerts = []
if (run_dir / "failures.txt").exists():
    alerts += ["scan failed: " + l.strip()
               for l in (run_dir / "failures.txt").read_text().splitlines() if l.strip()]
for name in ("seo.json", "ai.json", "axe.json"):
    p = run_dir / name
    if not p.exists():
        alerts.append(f"scan failed: {name} missing")
    elif load(p) is None:
        alerts.append(f"scan failed: {name} is not valid JSON")

rep = load(run_dir / "report.json")
if rep is None:
    if (run_dir / "seo.json").exists() or (run_dir / "ai.json").exists():
        alerts.append("scan failed: no report.json (rank step)")
elif (prev := load(prev_path)) and prev.get("prior"):
    m = prev.get("metrics") or {}
    scores = (rep.get("seo") or {}).get("scores") or {}
    pairs = [("overall", m.get("overall"), scores.get("overall")),
             ("SEO", m.get("seo"), scores.get("SEO")),
             ("GEO", m.get("geo"), scores.get("GEO")),
             ("AEO", m.get("aeo"), scores.get("AEO")),
             ("AI readiness", m.get("ai_ready"), (rep.get("ai") or {}).get("score"))]
    for label, old, new in pairs:
        if isinstance(old, (int, float)) and isinstance(new, (int, float)) and old - new >= 3:
            alerts.append(f"{label} {old} -> {new} (-{old - new})")
    old_pairs = {tuple(x) for x in prev.get("issues") or []}
    hi = ("critical", "serious")
    for i in rep.get("issues") or []:
        if i.get("impact") not in hi or i.get("dimension") == "a11y":
            continue
        if (i.get("dimension"), i.get("id")) not in old_pairs:
            where = str(i.get("where") or "")[:40]
            alerts.append(f"new {i['impact']} {i['dimension']}/{i['id']}" + (f" ({where})" if where else ""))
    old_axe = {x[0]: x[1] for x in prev.get("axe_nodes") or []}
    for i in rep.get("issues") or []:
        if i.get("dimension") != "a11y" or i.get("impact") not in hi:
            continue
        nid, n = i.get("id"), int(i.get("nodes") or 0)
        if nid not in old_axe:
            alerts.append(f"new {i['impact']} a11y/{nid} ({n} nodes)")
        elif n > old_axe[nid]:
            alerts.append(f"a11y/{nid} nodes {old_axe[nid]} -> {n}")

if alerts:
    print(f"Site Signal weekly re-scan — {domain}:")
    for a in alerts:
        print(f"  {a}")
    print(f"  report: {run_dir / 'report.md'}")
PYEOF
)"
  if [[ -n "$site_out" ]]; then
    printf '%s\n' "$site_out"
  fi
done < "$sites_list"

exit 0
