#!/usr/bin/env bash
# Site Signal ship-a-fix loop (SPEC.md 5.4) — end to end:
#   worktree -> fix brief -> Grok Build headless -> repo tests/build
#   -> deny_terms_check.sh -> push branch -> gh pr create (DRAFT) -> checks wait
#   -> merge gated on the owner's recorded approval, or on a human
#   merge_consent that names this domain -> gh pr merge --squash
#   --match-head-commit -> wait_deploy.sh -> re-scan live -> update the
#   Shipped table -> cleanup.
#
# Usage (ship):
#   ship_fix.sh --repo OWNER/NAME --domain DOMAIN [--run-dir DIR] [--report FILE]
#       [--top N | --with-moderate | --issues "dim/id,dim/id" | --brief FILE]
#       [--title "PR title"] [--branch-topic topic] [--max-turns N]
#       --approved-by-owner "ship the top serious on wisdomforge"
#       [--dry-run] [--skip-grok] [--no-wait] [--skip-tests] [--skip-rescan]
#       [--test-cmd CMD] [--build-cmd CMD] [--ss-home DIR]
#
# Usage (merge an already-open PR, after the owner approves):
#   ship_fix.sh --merge PR_NUMBER --repo OWNER/NAME --domain DOMAIN
#       [--approved-by-owner "merge wisdomforge#22"] [--run-dir DIR]
#       [--no-rescan] [--verify-path /sitemap.xml] [--verify-contains STR] [--dry-run]
#
# Guardrails: the default branch is never pushed, no force-push, PRs are drafts,
# merge is squash with --match-head-commit, and the owner's approval line must
# name the repo (ship) / repo + PR number (merge) — a bare "go" is refused.
# Every push/merge appends a record to $RUN_DIR/approval-<repo>.md first.
#
# gh resolution: GH_BIN env override wins; otherwise `gh` on PATH.
# Grok Build: GROK_BIN/GROK_MODEL env override config.yaml. The default model
# is grok-4.7. A local alias is optional and only works where it is defined.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
PROFILE_SKILLS="$(cd "$SKILL_DIR/.." && pwd)"
DENY_CHECK="$SCRIPT_DIR/deny_terms_check.sh"
WAIT_DEPLOY="$SCRIPT_DIR/wait_deploy.sh"

# ---------- state ----------------------------------------------------------
REPO="" DOMAIN="" RUN_DIR="" REPORT="" MODE="ship" MERGE_PR="" DRY_RUN=0
TOP="" WITH_MODERATE=0 ISSUES_SEL="" BRIEF_IN="" TITLE="" TOPIC="" SHORTID=""
APPROVED="" SKIP_GROK=0 NO_WAIT=0 SKIP_TESTS=0 SKIP_RESCAN=0
TEST_CMD="" BUILD_CMD="" MAX_TURNS=60 VERIFY_PATH="" VERIFY_CONTAINS=""
SS_HOME="${SITE_SIGNAL_HOME:-$HOME/SiteSignal}"
GH_BIN="${GH_BIN:-gh}"
GROK_BIN="${GROK_BIN:-}"
GROK_MODEL="${GROK_MODEL:-}"
DENY_TERMS_FILE="${SITE_SIGNAL_DENY_TERMS:-$HOME/.config/grok-fleet/deny-terms.txt}"
PY=""

die() { echo "ship_fix: ERROR: $*" >&2; exit 1; }
log() { echo "ship_fix: $*"; }
would() { echo "  WOULD: $*"; }

# ---------- args -----------------------------------------------------------
while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo) REPO="$2"; shift 2 ;;
    --domain) DOMAIN="$2"; shift 2 ;;
    --run-dir) RUN_DIR="$2"; shift 2 ;;
    --report) REPORT="$2"; shift 2 ;;
    --merge) MODE="merge"; MERGE_PR="$2"; shift 2 ;;
    --top) TOP="$2"; shift 2 ;;
    --with-moderate) WITH_MODERATE=1; shift ;;
    --issues) ISSUES_SEL="$2"; shift 2 ;;
    --brief) BRIEF_IN="$2"; shift 2 ;;
    --title) TITLE="$2"; shift 2 ;;
    --branch-topic) TOPIC="$2"; shift 2 ;;
    --approved-by-owner) APPROVED="$2"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --skip-grok) SKIP_GROK=1; shift ;;
    --no-wait) NO_WAIT=1; shift ;;
    --skip-tests) SKIP_TESTS=1; shift ;;
    --skip-rescan) SKIP_RESCAN=1; shift ;;
    --test-cmd) TEST_CMD="$2"; shift 2 ;;
    --build-cmd) BUILD_CMD="$2"; shift 2 ;;
    --max-turns) MAX_TURNS="$2"; shift 2 ;;
    --verify-path) VERIFY_PATH="$2"; shift 2 ;;
    --verify-contains) VERIFY_CONTAINS="$2"; shift 2 ;;
    --gh-bin) GH_BIN="$2"; shift 2 ;;
    --ss-home) SS_HOME="$2"; shift 2 ;;
    -h|--help) sed -n '2,29p' "$0"; exit 0 ;;
    *) die "unknown argument: $1 (see -h)" ;;
  esac
done
[[ -n "$DOMAIN" ]] || die "--domain is required"
[[ -n "$REPO" ]] || die "--repo OWNER/NAME is required"
[[ "$MODE" == "merge" && -z "$MERGE_PR" ]] && die "--merge needs a PR number"
SHORTID="$(LC_ALL=C tr -dc 'a-z0-9' </dev/urandom | head -c 4 || true)"; SHORTID="${SHORTID:-0000}"

# ---------- config.yaml (skills.config.site_signal) ------------------------
pick_python() {
  if [[ -x "$SS_HOME/.venv/bin/python3" ]]; then PY="$SS_HOME/.venv/bin/python3"; else PY="${PYTHON:-python3}"; fi
}
pick_python
CONFIG_YAML="$(cd "$PROFILE_SKILLS/.." && pwd)/config.yaml"
if [[ -f "$CONFIG_YAML" ]]; then
  cfg_out="$("$PY" - "$CONFIG_YAML" <<'PYEOF' 2>/dev/null || true
import sys, os, shlex
try:
    import yaml
except ImportError:
    sys.exit(0)
cfg = yaml.safe_load(open(sys.argv[1])) or {}
sc = ((cfg.get("skills") or {}).get("config") or {}).get("site_signal") or {}
def exp(v): return os.path.expanduser(str(v)) if isinstance(v, str) else v
for k in ("home", "deny_terms_file", "grok_model", "grok_bin"):
    if k in sc:
        print(f"CFG_{k.upper()}={shlex.quote(exp(sc[k]))}")
PYEOF
  )"
  if [[ -n "$cfg_out" ]]; then
    while IFS= read -r line; do eval "export $line"; done <<<"$cfg_out"
    # Precedence matches weekly_rescan.sh: an explicitly set SITE_SIGNAL_HOME /
    # SITE_SIGNAL_DENY_TERMS env wins (offline tests, custom layouts); only
    # otherwise does config.yaml fill the value in.
    [[ -n "${CFG_HOME:-}" && -z "${SITE_SIGNAL_HOME:-}" ]] && SS_HOME="$CFG_HOME"
    [[ -n "${CFG_DENY_TERMS_FILE:-}" && -z "${SITE_SIGNAL_DENY_TERMS:-}" ]] && DENY_TERMS_FILE="$CFG_DENY_TERMS_FILE"
    : "${GROK_MODEL:=${CFG_GROK_MODEL:-grok-4.7}}"
    : "${GROK_BIN:=${CFG_GROK_BIN:-grok}}"
    pick_python
  fi
fi
: "${GROK_MODEL:=grok-4.7}"; : "${GROK_BIN:=grok}"
if [[ "$GH_BIN" == */* ]]; then
  [[ -x "$GH_BIN" ]] || die "GH_BIN is not executable"
else
  command -v "$GH_BIN" >/dev/null 2>&1 || die "gh not found on PATH; install GitHub CLI or set GH_BIN"
fi

# ---------- run dir --------------------------------------------------------
if [[ -z "$RUN_DIR" ]]; then
  RUN_DIR="$(ls -1d "$SS_HOME/reports/$DOMAIN"/*/ 2>/dev/null | while read -r d; do
    [[ -f "${d}report.json" ]] && echo "$d"; done | tail -1 || true)"
  RUN_DIR="${RUN_DIR:-}"
fi
[[ -n "$RUN_DIR" ]] || die "no --run-dir and no prior run with report.json under $SS_HOME/reports/$DOMAIN (scan first)"
mkdir -p "$RUN_DIR"
REPORT="${REPORT:-$RUN_DIR/report.json}"
if [[ "$MODE" == "ship" ]]; then
  [[ -f "$REPORT" ]] || die "report not found: $REPORT (run rank.py first)"
elif [[ ! -f "$REPORT" ]]; then
  REPORT=""; log "note: no report.json in the run dir — the Shipped table will not be updated"
fi

# ---------- sites.yaml ownership gate --------------------------------------
SITES_YAML="$SS_HOME/sites.yaml"
[[ -f "$SITES_YAML" ]] || die "no $SITES_YAML — onboard the domain first (site-signal-onboard-site)"
site_out="$("$PY" - "$SITES_YAML" "$DOMAIN" "$REPO" "$MODE" <<'PYEOF'
import sys, yaml, shlex
sites_path, domain, repo, mode = sys.argv[1:5]
try:
    data = yaml.safe_load(open(sites_path)) or {}
except Exception as e:
    print("REFUSED=1"); print(f"REASON=unreadable sites.yaml: {e}"); sys.exit(0)
sites = data.get("sites") or []
entry = next((s for s in sites if s.get("domain") == domain or domain in (s.get("aliases") or [])), None)
if entry is None:
    print("REFUSED=1"); print("REASON=domain not in sites.yaml (scan-only until onboarded)"); sys.exit(0)
erepo = entry.get("repo")
if erepo and erepo != repo:
    print("REFUSED=1"); print(f"REASON=sites.yaml maps {domain} to {erepo}, not {repo}"); sys.exit(0)
if not entry.get("owner_verified"):
    print("REFUSED=1"); print("REASON=owner_verified is false — ownership not confirmed"); sys.exit(0)
if entry.get("scan_only") and mode == "ship":
    print("REFUSED=1"); print("REASON=scan_only: true — this site never gets fix PRs"); sys.exit(0)
scan = entry.get("scan") or {}
def q(v): return shlex.quote(str(v))
print("SS_REPO=" + q(erepo or repo))
print("SS_BASE=" + q(entry.get("default_branch", "main")))
print("SS_DEPLOY=" + q(entry.get("deploy", "unknown")))
print("SS_MERGE_POLICY=" + q(entry.get("merge", "ask")))
consent = entry.get("merge_consent") if isinstance(entry.get("merge_consent"), dict) else {}
phrase = str(consent.get("phrase") or "").strip()
set_by = str(consent.get("set_by") or "").strip()
set_at = str(consent.get("set_at") or "").strip()
consent_domain = str(consent.get("domain") or "").strip()
expected = "always merge green PRs for " + domain
consent_ok = (
    entry.get("merge") == "after_green_ci"
    and consent_domain.lower() == domain.lower()
    and phrase.casefold() == expected.casefold()
    and bool(set_by)
    and len(set_at) >= 10
    and set_at[0:4].isdigit()
)
print("SS_MERGE_CONSENT=" + q("yes" if consent_ok else "no"))
print("SS_MERGE_SET_BY=" + q(set_by))
print("SS_MERGE_SET_AT=" + q(set_at))
print("SS_PAGES=" + q(scan.get("pages", 5)))
print("SS_AXE_PATHS=" + q(" ".join(scan.get("axe_paths") or ["/"])))
print("SS_SCAN_ONLY=" + q(bool(entry.get("scan_only"))))
PYEOF
)" || true
REFUSED_NOTE=""; GATE_REFUSED=0
if echo "$site_out" | grep -q "REFUSED=1"; then
  reason="$(echo "$site_out" | sed -n 's/^REASON=//p' | head -1)"
  GATE_REFUSED=1
  if [[ "$DRY_RUN" -eq 1 ]]; then
    REFUSED_NOTE="GATE WOULD REFUSE: ${reason:-unknown} — continuing the dry run to print the plan (nothing is pushed or opened)."
  else
    die "ownership gate: ${reason:-refused}"
  fi
fi
eval "$(echo "$site_out" | grep -E '^(SS_[A-Z_]+)=')" || true
SS_BASE="${SS_BASE:-main}"; SS_DEPLOY="${SS_DEPLOY:-unknown}"; SS_MERGE_POLICY="${SS_MERGE_POLICY:-ask}"
SS_MERGE_CONSENT="${SS_MERGE_CONSENT:-no}"; SS_MERGE_SET_BY="${SS_MERGE_SET_BY:-}"; SS_MERGE_SET_AT="${SS_MERGE_SET_AT:-}"
SS_PAGES="${SS_PAGES:-5}"; SS_AXE_PATHS="${SS_AXE_PATHS:-/}"; SS_SCAN_ONLY="${SS_SCAN_ONLY:-False}"
REPO_DIR="$SS_HOME/repos/$REPO"
WT="$SS_HOME/wt/$REPO-$SHORTID"
BRANCH="site-signal/${TOPIC:-fixes}-$SHORTID"
APPROVAL_FILE="$RUN_DIR/approval-${REPO#*/}.md"
GROK_RULES="Never push. Never run git push or gh. Never edit .env or secrets. Commit locally only."

record_approval() { # $1 = what is about to run
  local ts; ts="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  { echo "## $ts — $MODE"
    echo "- owner instruction (--approved-by-owner): ${APPROVED:-<none>}"
    if [[ "$SS_MERGE_CONSENT" == "yes" ]]; then
      echo "- merge consent names $DOMAIN; set_by: $SS_MERGE_SET_BY; set_at: $SS_MERGE_SET_AT"
    fi
    echo "- repo: $REPO  domain: $DOMAIN  ${MERGE_PR:+PR: #$MERGE_PR  }branch: $BRANCH"
    echo "- run: $RUN_DIR"
    echo "- about to: $1"
    echo; } >> "$APPROVAL_FILE"
}

approval_names_repo() {
  local short="${REPO#*/}"
  [[ -n "$APPROVED" && ( "$APPROVED" == *"$REPO"* || "$APPROVED" == *"$short"* ) ]]
}
approval_names_pr() {
  local short="${REPO#*/}" t; t="${APPROVED,,}"
  [[ -n "$APPROVED" && ( "$APPROVED" == *"$REPO"* || "$APPROVED" == *"$short"* ) \
     && ( "$APPROVED" == *"#${MERGE_PR}"* || "$t" == *"pr ${MERGE_PR}"* || "$t" == *"pr#${MERGE_PR}"* || "$APPROVED" == *"pull/${MERGE_PR}"* ) ]]
}

# ---------- python helpers -------------------------------------------------
select_issues() { # -> $RUN_DIR/selection.json
  "$PY" - "$REPORT" "$RUN_DIR/selection.json" "$REPO" "$DOMAIN" "${TOP:-0}" "$WITH_MODERATE" "${ISSUES_SEL:-}" <<'PYEOF'
import sys, json
report_path, out_path, repo, domain, top, all_mod, want = sys.argv[1:8]
rep = json.load(open(report_path))
w = {x.strip().lower() for x in want.split(",") if x.strip()} or None
sel = []
for i in rep.get("issues", []):
    if w is not None:
        if f"{i['dimension']}/{i['id']}".lower() in w: sel.append(i)
    elif all_mod == "1" or i["impact"] in ("critical", "serious"):
        sel.append(i)
if w is not None and len(sel) != len(w):
    missing = w - {f"{i['dimension']}/{i['id']}".lower() for i in sel}
    sys.exit(f"error: --issues not found in report: {', '.join(sorted(missing))}")
if top and int(top) > 0: sel = sel[: int(top)]
if not sel: sys.exit("error: selection is empty (nothing to ship — re-check the report)")
seo, ai, counts = rep.get("seo"), rep.get("ai"), rep.get("axe_counts") or {}
before = []
if seo:
    s, g = seo["scores"], seo["grades"]
    before.append(f"SEO {s['SEO']} ({g['SEO']}) · GEO {s['GEO']} ({g['GEO']}) · "
                  f"AEO {s['AEO']} ({g['AEO']}) · Overall {s['overall']} ({g['overall']})")
if ai:
    before.append(f"AI readiness {ai['score']}/100 ({ai['grade']})")
if counts:
    before.append("axe nodes: {critical} critical / {serious} serious / {moderate} moderate / {minor} minor".format(**counts))
for i in sel:
    i["reach_n"] = -i.get("reach", -1)
    lines = []
    for ev in (i.get("evidence") or [])[:3]:
        selector = " ".join(ev.get("target", []))
        snippet = (ev.get("html") or "").replace("\n", " ")[:120]
        lines.append(f"`{selector}` — `{snippet}`")
    i["evidence_lines"] = lines or [f"{i['dimension']} check `{i['id']}` on {i.get('where', '(site-wide)')}: {i['message']}"]
title_ids = ", ".join(f"{i['dimension']}/{i['id']}" for i in sel[:3])
more = len(sel) - min(3, len(sel))
json.dump({"repo": repo, "domain": domain, "issues": sel, "before_scores": before,
           "default_title": f"Site Signal: fix {title_ids}" + (f" (+{more} more)" if more > 0 else "")},
          open(out_path, "w"), indent=2)
print(f"selected {len(sel)} issue(s) -> {out_path}")
PYEOF
}

render_template() { # $1 template, $2 context json, $3 out
  "$PY" - "$1" "$2" "$3" <<'PYEOF'
import sys, json
from jinja2 import Environment, FileSystemLoader, StrictUndefined
template, ctx_path, out_path = sys.argv[1:4]
env = Environment(loader=FileSystemLoader("/"), keep_trailing_newline=True,
                  trim_blocks=True, lstrip_blocks=True, undefined=StrictUndefined)
open(out_path, "w").write(env.get_template(template).render(**json.load(open(ctx_path))))
PYEOF
}

new_facts_scan() { # $1 wt dir, $2 base, $3 out file — numerals + new external URLs in added lines
  "$PY" - "$1" "$2" "$3" <<'PYEOF'
import subprocess, re, sys
wt, base, out = sys.argv[1], sys.argv[2], sys.argv[3]
diff = subprocess.run(["git", "-C", wt, "diff", f"origin/{base}...HEAD"],
                      capture_output=True, text=True).stdout
facts, cur_file = [], ""
for line in diff.splitlines():
    if line.startswith("+++ b/"): cur_file = line[6:]
    if not line.startswith("+") or line.startswith("+++"): continue
    if any(p in cur_file.lower() for p in ("package-lock", ".lock", "-lock.")): continue
    for url in re.findall(r'https?://[^\s"\'<>)\]]+', line):
        if url not in facts: facts.append(url)
    for tok in re.findall(r'[A-Za-z0-9._/%-]*\d[A-Za-z0-9._/%-]*', line):
        if len(tok) >= 4 and tok not in facts and not re.fullmatch(r'[\d.]+', tok):
            facts.append(tok)
with open(out, "a") as f:
    for x in facts[:15]: f.write(x + "\n")
PYEOF
}

ci_gate() { # $1 = gh pr view JSON file (with statusCheckRollup).
  # Prints GREEN / NO_CHECKS, or FAILING<TAB><names> and exits 1 when any check
  # is failing or pending on the head SHA. No checks configured = vacuous pass
  # (a repo without CI has nothing to be green on); anything unrecognized
  # refuses upstream (fail closed) — SPEC 3.3 rule 3(a) / 5.4 step 7.
  "$PY" - "$1" <<'PYEOF'
import json, sys
data = json.load(open(sys.argv[1]))
rollup = data.get("statusCheckRollup") or []
if not rollup:
    print("NO_CHECKS")
    sys.exit(0)
bad = []
for c in rollup:
    if c.get("__typename") == "CheckRun":
        ok = c.get("status") == "COMPLETED" and c.get("conclusion") == "SUCCESS"
        name, state = c.get("name") or "(unnamed check)", f"{c.get('status') or '?'}/{c.get('conclusion') or '?'}"
    else:  # StatusContext (external CI reporting via commit statuses)
        ok = c.get("state") == "SUCCESS"
        name, state = c.get("context") or "(unnamed status)", c.get("state") or "?"
    if not ok:
        bad.append(f"{name} [{state}]")
if bad:
    print("FAILING\t" + "; ".join(bad))
    sys.exit(1)
print("GREEN")
PYEOF
}

gh_exports() { # $1 gh --json output file, $2 prefix — eval-able KEY=quoted lines
  "$PY" - "$1" "$2" <<'PYEOF'
import json, shlex, sys
data, prefix = sys.argv[1:3]
v = json.load(open(data))
for k in ("state", "isDraft", "mergeable", "headRefOid", "title", "url"):
    if k in v:
        print(f"{prefix}{k.upper()}={shlex.quote(str(v[k]))}")
PYEOF
}

shipped_update_and_compare() { # $1 ship run dir, $2 after run dir, $3 pr, $4 pr_url, $5 merge sha
  "$PY" - "$1" "$2" "$3" "$4" "$5" <<'PYEOF'
import sys, json
from pathlib import Path
before_dir, after_dir, pr, pr_url, sha = sys.argv[1:6]
rep = json.loads((Path(before_dir) / "report.json").read_text())
after = json.loads((Path(after_dir) / "report.json").read_text())
row = {"pr": f"{rep.get('domain', '')}/{pr}", "url": pr_url, "status": "merged (squash)",
       "merge_sha": sha,
       "before": {"overall": (rep.get("seo") or {}).get("scores", {}).get("overall"),
                  "ai_ready": (rep.get("ai") or {}).get("score"),
                  "axe_serious": (rep.get("axe_counts") or {}).get("serious")},
       "after": {"overall": (after.get("seo") or {}).get("scores", {}).get("overall"),
                 "ai_ready": (after.get("ai") or {}).get("score"),
                 "axe_serious": (after.get("axe_counts") or {}).get("serious")}}
rep.setdefault("shipped", []).append(row)
(Path(before_dir) / "report.json").write_text(json.dumps(rep, indent=2) + "\n")
b, a = row["before"], row["after"]
print("before -> after (this PR):")
for k, lbl in (("overall", "SEO/GEO/AEO overall"), ("ai_ready", "AI readiness"), ("axe_serious", "axe serious nodes")):
    if b.get(k) is not None and a.get(k) is not None:
        print(f"  {lbl}: {b[k]} -> {a[k]}")
PYEOF
}

# ---------- git ------------------------------------------------------------
ensure_repo_and_worktree() {
  if [[ ! -d "$REPO_DIR/.git" ]]; then
    log "cloning https://github.com/$REPO.git -> $REPO_DIR (first time)"
    mkdir -p "$(dirname "$REPO_DIR")"
    timeout 600 git clone --quiet "https://github.com/$REPO.git" "$REPO_DIR" \
      || die "git clone failed — check access (git credential helper / GH_TOKEN) and network"
  fi
  timeout 60 git -C "$REPO_DIR" fetch origin --quiet || die "git fetch origin failed in $REPO_DIR"
  timeout 60 git -C "$REPO_DIR" rev-parse --verify --quiet "origin/$SS_BASE" >/dev/null \
    || die "origin/$SS_BASE not found in $REPO_DIR"
  mkdir -p "$SS_HOME/wt/$(dirname "$REPO")"
  git -C "$REPO_DIR" worktree add -b "$BRANCH" "$WT" "origin/$SS_BASE" --quiet \
    || die "git worktree add failed (does $WT already exist?)"
  log "worktree ready: $WT (branch $BRANCH from origin/$SS_BASE)"
}
cleanup_worktree() {
  git -C "$REPO_DIR" worktree remove --force "$WT" >/dev/null 2>&1 || true
  git -C "$REPO_DIR" branch -D "$BRANCH" >/dev/null 2>&1 || true
}
# A dry run must never leave a worktree behind, even after a failure.
trap 'if [[ "$DRY_RUN" -eq 1 && -n "${WT:-}" && -d "${WT:-}" ]]; then cleanup_worktree; fi' EXIT

# ===========================================================================
# SHIP PHASE
# ===========================================================================
if [[ "$MODE" == "ship" ]]; then
  log "ship phase: $REPO ($DOMAIN) from run $RUN_DIR"
  [[ -z "$TOP" || -z "$ISSUES_SEL" ]] || die "--top and --issues are mutually exclusive"
  [[ -n "$REFUSED_NOTE" ]] && echo "ship_fix: $REFUSED_NOTE"

  select_issues || die "issue selection failed"
  PR_TITLE="${TITLE:-$("$PY" -c "import json; print(json.load(open(r'$RUN_DIR/selection.json'))['default_title'])")}"
  log "PR title: $PR_TITLE"

  if [[ "$DRY_RUN" -eq 0 ]]; then
    approval_names_repo \
      || die "--approved-by-owner must name this repo (full 'smfworks/x' or short 'x') — a bare 'go' does not match"
  fi

  ensure_repo_and_worktree

  # --- fix brief -----------------------------------------------------------
  BRIEF="$RUN_DIR/fix-brief-${REPO#*/}.md"
  if [[ -n "$BRIEF_IN" ]]; then
    [[ -f "$BRIEF_IN" ]] || die "--brief file not found: $BRIEF_IN"
    cp "$BRIEF_IN" "$BRIEF"
    log "fix brief: using provided $BRIEF_IN"
  else
    CTX="$RUN_DIR/fix-ctx-${REPO#*/}.json"
    "$PY" - "$RUN_DIR/selection.json" "$CTX" "$BRANCH" "$SS_BASE" <<'PYEOF'
import sys, json
from datetime import datetime
from zoneinfo import ZoneInfo
sel_path, out, branch, base = sys.argv[1:5]
ctx = json.load(open(sel_path))
ctx["branch"], ctx["base"] = branch, base
ctx["date"] = datetime.now(ZoneInfo("America/New_York")).strftime("%Y-%m-%d %H:%M ET")
# SPEC.md 5.4 step 3 constraints + acceptance, restated for the coding model.
ctx["constraints"] = [
    "Brand everything you create (schema publishers, strings, comments) as \"SMF Works\".",
    "Do not add statistics, quotes, citations, authors, publish dates, or social/sameAs "
    "profiles. If a check needs one, leave the content suggestion in a code comment or "
    "skip it — the owner supplies facts.",
    "Do not rewrite prose. A 1-2-sentence lead or a 40-60-word answer that restates what "
    "the page already says is the ceiling; keep the existing layout and components.",
    "Small diffs: metadata, attributes, tokens, labels, schema. No new dependencies, no "
    "renames, no formatting churn; if a new dependency seems required, stop and say why.",
    "Keep every change consistent with the existing code style and file structure.",
]
ctx["acceptance"] = [
    "Repo tests pass and the production build passes.",
    "Where feasible, the specific failing scanner check passes against a local build "
    "(next dev / npm run build && npm start) of the touched pages.",
    "The final diff contains no new numerals in content and no new external URLs beyond "
    "what the site already references.",
    "Commit locally with a clear message; never push, never run gh, never touch .env.",
]
json.dump(ctx, open(out, "w"))
PYEOF
    render_template "$SKILL_DIR/templates/fix-brief.md.j2" "$CTX" "$BRIEF" \
      || die "failed to render fix brief (jinja2 missing? set PYTHON=$SS_HOME/.venv/bin/python3)"
    log "fix brief rendered: $BRIEF"
  fi

  # --- dry run: print the plan and stop before push -------------------------
  if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "---------------------------------------------------------------"
    echo "DRY RUN plan for $REPO ($DOMAIN) — none of the steps below is executed."
    echo "  gate: $( [[ "$GATE_REFUSED" -eq 1 ]] && echo 'WOULD REFUSE (real run aborts here); ' || echo 'ownership OK; ' )merge policy: $SS_MERGE_POLICY"
    echo "  branch: $BRANCH  worktree: $WT (created locally, removed at the end)"
    echo "  fix brief: $BRIEF (rendered — inspect it)"
    would "\"$GROK_BIN\" --no-auto-update -p \"\$(cat $BRIEF)\" -m $GROK_MODEL --cwd $WT --always-approve --max-turns $MAX_TURNS --output-format json --rules \"$GROK_RULES\" > $RUN_DIR/grok-${REPO#*/}.json"
    would "test:  ${TEST_CMD:-npm test --if-present}   (in $WT)"
    would "build: ${BUILD_CMD:-npm run build}   (in $WT)"
    would "$DENY_CHECK --git-diff $WT origin/$SS_BASE...HEAD <(printf '%s' \"$PR_TITLE\") $RUN_DIR/pr-body-${REPO#*/}.md $BRIEF"
    would "new-facts grep over git diff origin/$SS_BASE...HEAD (numerals + new external URLs listed for the owner)"
    would "git -C $WT push -u origin $BRANCH        <-- dry run STOPS HERE: no push, no PR, no remote changes"
    would "gh pr create --repo $REPO --base $SS_BASE --head $BRANCH --draft --title \"$PR_TITLE\" --body-file $RUN_DIR/pr-body-${REPO#*/}.md"
    would "gh pr checks <n> --repo $REPO --watch --fail-fast  (unless --no-wait)"
    if [[ "$SS_MERGE_CONSENT" == "yes" ]]; then
      would "merge (after_green_ci confirmed by $SS_MERGE_SET_BY at $SS_MERGE_SET_AT for $DOMAIN): gh pr ready <n>; gh pr merge <n> --repo $REPO --squash --match-head-commit <head sha> --subject \"$PR_TITLE (#<n>)\" --delete-branch"
      would "wait_deploy.sh $REPO <merge sha> $DOMAIN; re-scan; update Shipped table"
    else
      would "STOP: policy is '$SS_MERGE_POLICY' — print the merge command and wait for the owner's approval naming the PR"
      if [[ "$SS_MERGE_POLICY" == "after_green_ci" ]]; then
        would "after_green_ci ignored: no human confirmation naming $DOMAIN (merge_consent phrase, set_by, set_at)"
      fi
    fi
    echo "DRY RUN complete: no push, no PR, no remote changes. Worktree removed."
    echo "---------------------------------------------------------------"
    cleanup_worktree
    exit 0
  fi

  record_approval "git push -u origin $BRANCH && gh pr create (draft): $PR_TITLE"

  # --- Grok Build headless --------------------------------------------------
  if [[ "$SKIP_GROK" -eq 1 ]]; then
    log "skipping Grok Build (--skip-grok): edits are expected to already exist in $WT"
  else
    [[ -x "$GROK_BIN" ]] || die "Grok Build not found at $GROK_BIN (set GROK_BIN)"
    log "running Grok Build headless ($GROK_MODEL) — this can take minutes"
    "$GROK_BIN" --no-auto-update -p "$(cat "$BRIEF")" -m "$GROK_MODEL" --cwd "$WT" \
      --always-approve --max-turns "$MAX_TURNS" --output-format json \
      --rules "$GROK_RULES" > "$RUN_DIR/grok-${REPO#*/}.json" \
      || die "Grok Build run failed — see $RUN_DIR/grok-${REPO#*/}.json"
  fi
  if [[ -n "$(git -C "$WT" status --porcelain)" ]]; then
    git -C "$WT" add -A
    git -C "$WT" commit -q -m "Site Signal (SMF Works): $PR_TITLE" || die "could not commit changes in $WT"
  fi
  # git diff --quiet exits 0 on NO changes — so a successful Grok Build run
  # (changes present, diff --quiet exits 1) must fall through, and only an
  # empty diff dies. Inverted check would kill the happy path and push empty
  # branches (review F1, card t_940c5bd3).
  git -C "$WT" diff --quiet "origin/$SS_BASE...HEAD" \
    && die "no changes in $WT after the Grok Build step — nothing to ship"

  # --- tests / build ----------------------------------------------------------
  if [[ "$SKIP_TESTS" -eq 1 ]]; then
    log "skipping tests/build (--skip-tests)"
  elif [[ ! -f "$WT/package.json" ]]; then
    log "no package.json in the repo — skipping npm test/build"
  else
    TC="${TEST_CMD:-npm test --if-present}"; BC="${BUILD_CMD:-npm run build}"
    log "repo tests: $TC"
    ( cd "$WT" && timeout 1800 bash -lc "$TC" ) || die "repo tests failed — nothing pushed; inspect $WT"
    log "repo build: $BC"
    ( cd "$WT" && timeout 1800 bash -lc "$BC" ) || die "repo build failed — nothing pushed; inspect $WT"
  fi

  # --- PR body + deny-terms ---------------------------------------------------
  PR_BODY="$RUN_DIR/pr-body-${REPO#*/}.md"
  CTX="$RUN_DIR/pr-ctx-${REPO#*/}.json"
  "$PY" - "$RUN_DIR/selection.json" "$CTX" "$PR_TITLE" "$BRANCH" "$SS_BASE" <<'PYEOF'
import sys, json
sel_path, out, title, branch, base = sys.argv[1:6]
ctx = json.load(open(sel_path))
ctx.update(pr_title=title, branch=branch, base=base, new_facts=[], dry_note="", verification=[])
json.dump(ctx, open(out, "w"))
PYEOF
  if [[ "$SKIP_TESTS" -eq 0 && -f "$WT/package.json" ]]; then
    "$PY" - "$CTX" "${TEST_CMD:-npm test --if-present}" "${BUILD_CMD:-npm run build}" <<'PYEOF'
import sys, json
ctx_path, tc, bc = sys.argv[1:4]
ctx = json.load(open(ctx_path))
ctx["verification"] = [f"tests: `{tc}` — pass", f"build: `{bc}` — pass"]
json.dump(ctx, open(ctx_path, "w"))
PYEOF
  fi
  NF="$RUN_DIR/new-facts-${REPO#*/}.txt"; : > "$NF"
  new_facts_scan "$WT" "$SS_BASE" "$NF" || true
  nf_count=0; [[ -s "$NF" ]] && nf_count=$(wc -l < "$NF" | tr -d ' ')
  if [[ -s "$NF" ]]; then
    "$PY" - "$CTX" "$NF" <<'PYEOF'
import sys, json
ctx_path, nf = sys.argv[1:3]
ctx = json.load(open(ctx_path))
ctx["new_facts"] = [l.rstrip("\n") for l in open(nf).read().splitlines() if l.strip()][:15]
json.dump(ctx, open(ctx_path, "w"))
PYEOF
    log "new-facts review: $nf_count token(s) listed in the PR body for the owner"
  fi
  # Gate 1: the committed diff, PR title, and fix brief (the PR body is gated after render).
  "$DENY_CHECK" --git-diff "$WT" "origin/$SS_BASE...HEAD" <(printf '%s' "$PR_TITLE") "$BRIEF" \
    || die "deny-terms check failed — nothing pushed; fix the flagged target(s) and re-run"
  "$PY" - "$CTX" "$SS_BASE" <<'PYEOF'
import sys, json
ctx_path, base = sys.argv[1:3]
ctx = json.load(open(ctx_path))
ctx.setdefault("verification", []).append(
    f"deny-terms: clean (git diff origin/{base}...HEAD, PR title, fix brief)")
json.dump(ctx, open(ctx_path, "w"))
PYEOF
  render_template "$SKILL_DIR/templates/pr-body.md.j2" "$CTX" "$PR_BODY" \
    || die "failed to render PR body"
  # Gate 2: the rendered PR body itself.
  "$DENY_CHECK" "$PR_BODY" \
    || die "deny-terms check failed on the PR body — nothing pushed; fix and re-run"

  # --- push + PR --------------------------------------------------------------
  git -C "$WT" push -u origin "$BRANCH" --quiet \
    || die "git push failed — branch $BRANCH left local; fix access and re-run"
  log "branch pushed: $BRANCH"
  PR_URL="$(timeout 120 "$GH_BIN" pr create --repo "$REPO" --base "$SS_BASE" --head "$BRANCH" \
    --draft --title "$PR_TITLE" --body-file "$PR_BODY")" || die "gh pr create failed"
  PR_NUM="$(basename "$PR_URL")"
  log "draft PR #$PR_NUM opened: $PR_URL"

  # --- CI wait ------------------------------------------------------------------
  if [[ "$NO_WAIT" -eq 1 ]]; then
    log "skipping CI wait (--no-wait)"
  else
    log "waiting for checks on #$PR_NUM (up to 20 min)…"
    if ! timeout 1200 "$GH_BIN" pr checks "$PR_NUM" --repo "$REPO" --watch --fail-fast --interval 20; then
      echo "ship_fix: checks failed or pending on #$PR_NUM — PR left open for inspection." >&2
      echo "ship_fix: merge later with: ship_fix.sh --merge $PR_NUM --repo $REPO --domain $DOMAIN --run-dir $RUN_DIR --approved-by-owner 'merge ${REPO#*/}#$PR_NUM'" >&2
      exit 8
    fi
    log "PR #$PR_NUM is green."
  fi

  # --- merge gate ----------------------------------------------------------------
  if [[ "$SS_MERGE_CONSENT" == "yes" ]] || { [[ -n "$APPROVED" ]] && approval_names_pr; }; then
    MODE="merge"
    if [[ "$SS_MERGE_CONSENT" == "yes" ]]; then
      log "merge consent for $DOMAIN set by $SS_MERGE_SET_BY at $SS_MERGE_SET_AT — merging #$PR_NUM"
    else
      log "owner approval names this PR — merging #$PR_NUM"
    fi
    MERGE_PR="$PR_NUM"
  else
    log "PR #$PR_NUM is green — awaiting owner approval (policy: $SS_MERGE_POLICY)."
    echo "ship_fix: to merge after approval: ship_fix.sh --merge $PR_NUM --repo $REPO --domain $DOMAIN --run-dir $RUN_DIR --approved-by-owner 'merge ${REPO#*/}#$PR_NUM'"
    exit 0
  fi
fi

# ===========================================================================
# MERGE PHASE (via --merge N, or falls through from ship on policy/approval)
# ===========================================================================
if [[ "$MODE" == "merge" ]]; then
  log "merge phase: PR #$MERGE_PR in $REPO ($DOMAIN)"
  if [[ "$SS_MERGE_CONSENT" != "yes" ]]; then
    if [[ "$SS_MERGE_POLICY" == "after_green_ci" ]]; then
      log "merge: after_green_ci is set for $DOMAIN but merge_consent does not name this domain with set_by and set_at — not auto-merging"
    fi
    approval_names_pr \
      || die "refusing to merge: --approved-by-owner must name the repo and PR (#$MERGE_PR, e.g. 'merge ${REPO#*/}#$MERGE_PR'); a bare 'go' does not match. after_green_ci auto-merges only when merge_consent names $DOMAIN, who set it, and when"
  else
    log "honoring merge consent for $DOMAIN (set_by $SS_MERGE_SET_BY at $SS_MERGE_SET_AT)"
  fi
  if [[ "$DRY_RUN" -eq 1 ]]; then
    would "gh pr view $MERGE_PR --repo $REPO --json state,isDraft,mergeable,headRefOid,title,statusCheckRollup"
    would "require CI green on the head SHA (statusCheckRollup all-success — SPEC 3.3 rule 3(a))"
    would "gh pr ready $MERGE_PR (if draft) — owner approved this merge"
    would "gh pr merge $MERGE_PR --repo $REPO --squash --match-head-commit <head sha> --subject \"<title> (#$MERGE_PR)\" --delete-branch"
    would "wait_deploy.sh $REPO <merge sha> $DOMAIN${VERIFY_PATH:+ --path $VERIFY_PATH}; re-scan; update Shipped table"
    echo "DRY RUN complete: nothing merged."
    exit 0
  fi
  record_approval "gh pr merge #$MERGE_PR --squash --match-head-commit <head sha>"

  VIEW="$(mktemp)"
  timeout 60 "$GH_BIN" pr view "$MERGE_PR" --repo "$REPO" \
    --json state,isDraft,mergeable,headRefOid,title,url,statusCheckRollup > "$VIEW" || die "cannot read PR #$MERGE_PR"
  eval "$(gh_exports "$VIEW" "PR_")" || die "could not parse gh pr view output"
  [[ "${PR_STATE:-}" == "OPEN" ]] || die "PR #$MERGE_PR is ${PR_STATE:-unknown}, refusing to merge"
  [[ "${PR_MERGEABLE:-}" == "MERGEABLE" ]] || die "PR #$MERGE_PR is not mergeable (${PR_MERGEABLE:-unknown}) — resolve conflicts first"
  # --- CI-green gate (SPEC 3.3 rule 3(a) / 5.4 step 7) -------------------------
  # Sandbox repos have no branch protection, so the merge itself must refuse a
  # red or pending PR (review F2, card t_940c5bd3). --match-head-commit below
  # already pins the merge to the inspected head; statusCheckRollup is that
  # same head's check state, fetched in the single pr view above.
  ci_out="$(ci_gate "$VIEW")" || true
  case "$ci_out" in
    GREEN) log "CI green on #$MERGE_PR — merge gate satisfied (SPEC 3.3 rule 3(a))" ;;
    NO_CHECKS) log "no checks configured on #$MERGE_PR — CI gate vacuously satisfied" ;;
    FAILING*) die "PR #$MERGE_PR checks are failing or pending — CI must be green on the head SHA before merge (SPEC 3.3 rule 3(a)): ${ci_out#FAILING$'\t'} — re-run --merge once checks pass" ;;
    *) die "could not determine CI status for PR #$MERGE_PR — refusing to merge (fail closed)" ;;
  esac
  PR_TITLE="${PR_TITLE:-$TITLE}"
  if [[ "${PR_ISDRAFT:-False}" == "True" ]]; then
    timeout 60 "$GH_BIN" pr ready "$MERGE_PR" --repo "$REPO" || die "could not mark PR ready"
    log "PR marked ready for merge (owner approved)"
  fi
  # F5 (Paula review): pin the head sha from the SAME pr view that ci_gate
  # inspected ($VIEW contains headRefOid), so the merge can never pin a sha
  # whose checks were never looked at.
  PR_HEAD="$("$PY" - "$VIEW" <<'PYEOF'
import json, sys
print(json.load(open(sys.argv[1]))["headRefOid"])
PYEOF
)" || die "cannot read head sha from the inspected PR view"
  timeout 120 "$GH_BIN" pr merge "$MERGE_PR" --repo "$REPO" --squash --match-head-commit "$PR_HEAD" \
    --subject "$PR_TITLE (#$MERGE_PR)" --delete-branch || die "squash merge failed (head moved? re-check green CI)"
  MERGE_SHA="$(timeout 60 "$GH_BIN" pr view "$MERGE_PR" --repo "$REPO" --json mergeCommit --jq .mergeCommit.oid 2>/dev/null || true)"
  log "merged #$MERGE_PR (squash) at ${MERGE_SHA:-unknown}"
  record_approval "merged #$MERGE_PR at ${MERGE_SHA:-unknown}"

  # --- deploy wait -------------------------------------------------------------
  if [[ "$SS_DEPLOY" == "vercel" && -n "$MERGE_SHA" ]]; then
    wd_args=("$REPO" "$MERGE_SHA" "$DOMAIN")
    [[ -n "$VERIFY_PATH" ]] && wd_args+=(--path "$VERIFY_PATH")
    [[ -n "$VERIFY_CONTAINS" ]] && wd_args+=(--expect-contains "$VERIFY_CONTAINS")
    wd_rc=0; "$WAIT_DEPLOY" "${wd_args[@]}" || wd_rc=$?
    [[ $wd_rc -eq 0 ]] || echo "ship_fix: deploy wait did not confirm (exit $wd_rc) — verify the artifact manually before re-scan."
  else
    log "deploy wait skipped (deploy: $SS_DEPLOY, merge sha: ${MERGE_SHA:-none})"
  fi

  # --- re-scan live --------------------------------------------------------------
  if [[ "$SKIP_RESCAN" -eq 1 ]]; then
    log "skipping re-scan (--skip-rescan)"
  else
    RES="$SS_HOME/reports/$DOMAIN/$(date +%Y-%m-%dT%H%M)-after"
    mkdir -p "$RES"
    log "re-scanning live into $RES"
    SEO_PY="$PROFILE_SKILLS/site-signal-seo-geo-aeo/scripts/seo_geo_aeo_scan.py"
    AI_PY="$PROFILE_SKILLS/site-signal-ai-readiness/scripts/ai_ready_scan.py"
    AXE_JS="$PROFILE_SKILLS/site-signal-axe-scan/scripts/axe_scan.js"
    RANK_PY="$PROFILE_SKILLS/site-signal-report/scripts/rank.py"
    RENDER_PY="$PROFILE_SKILLS/site-signal-report/scripts/render_report.py"
    seo_ok=1; ai_ok=1; axe_ok=1
    "$PY" "$SEO_PY" "https://$DOMAIN" --pages "$SS_PAGES" --json "$RES/seo.json" || seo_ok=0
    "$PY" "$AI_PY" "https://$DOMAIN" --json "$RES/ai.json" || ai_ok=0
    if command -v node >/dev/null 2>&1; then
      # shellcheck disable=SC2086
      axe_urls=(); for p in $SS_AXE_PATHS; do
        case "$p" in http*) axe_urls+=("$p") ;; *) axe_urls+=("https://$DOMAIN$p") ;; esac
      done
      node "$AXE_JS" --json "$RES/axe.json" "${axe_urls[@]}" || axe_ok=0
    else
      axe_ok=0; log "node missing — axe re-scan skipped"
    fi
    [[ "$seo_ok" -eq 1 && "$ai_ok" -eq 1 && "$axe_ok" -eq 1 ]] \
      || log "warning: one or more re-scan scanners failed; check $RES"
    "$PY" "$RANK_PY" "$RES" || true
    "$PY" "$RENDER_PY" "$RES" >/dev/null 2>&1 || true
    if [[ -n "$MERGE_SHA" && -n "$REPORT" ]]; then
      shipped_update_and_compare "$RUN_DIR" "$RES" "$MERGE_PR" "${PR_URL:-}" "$MERGE_SHA" || true
      "$PY" "$RENDER_PY" "$RUN_DIR" >/dev/null 2>&1 || true
    fi
  fi

  cleanup_worktree
  log "done: PR #$MERGE_PR merged (squash), worktree removed, live re-scan complete."
  exit 0
fi
