#!/usr/bin/env bash
# Regression test for ship_fix.sh's no-changes gate and the merge CI gate
# (review findings F1/F2, card t_940c5bd3), run against the real tree script:
#
#   F1 ship, changes present  -> must pass the gate, push, and exit 0
#   F1 ship, no changes       -> must die "no changes" and push NOTHING
#   F2 --merge, red checks    -> must refuse to merge (SPEC 3.3 rule 3(a))
#   F2 --merge, green checks  -> merges
#   F2 --merge, no checks     -> merges (no CI configured = vacuous pass)
#
# Everything is local: origin is a bare repo in a temp dir, "grok" is a fake
# that writes one file into the worktree (or nothing, with
# FAKE_GROK_MAKES_CHANGES=0), and "gh" is a fake that answers pr
# create/view/merge from fixture JSON. No network, nothing leaves /tmp.
set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SHIP_FIX="$REPO_DIR/skills/site-signal/site-signal-ship-fixes/scripts/ship_fix.sh"
[[ -f "$SHIP_FIX" ]] || { echo "FAIL: $SHIP_FIX not found" >&2; exit 1; }

fail() { echo "FAIL: $*" >&2; exit 1; }

# Interpreter with yaml + jinja2 (the sites.yaml gate and both template renders).
PY=""
for c in "$HOME/SiteSignal/.venv/bin/python3" "$(command -v python3 2>/dev/null || true)"; do
  [[ -x "$c" ]] || continue
  "$c" -c 'import yaml, jinja2' 2>/dev/null || continue
  PY="$c"; break
done
[[ -n "$PY" ]] || fail "no interpreter with pyyaml+jinja2 (tried ~/SiteSignal/.venv and python3)"

# ---------- fixtures ---------------------------------------------------------
write_fakes() { # $1 = base dir
  cat > "$1/fake-grok" <<'EOF'
#!/usr/bin/env bash
# Stands in for a successful Grok Build: writes one change into --cwd.
while [[ $# -gt 0 ]]; do [[ "$1" == "--cwd" ]] && cwd="$2"; shift; done
[[ "${FAKE_GROK_MAKES_CHANGES:-1}" == "1" ]] && \
  printf 'site signal regression fix\n' > "${cwd:?no --cwd passed}/fix-applied.txt"
echo '{"ok": true}'
EOF
  cat > "$1/fake-gh" <<'EOF'
#!/usr/bin/env bash
# Minimal gh stand-in: pr create, pr view (fixture JSON, plus the separate
# mergeCommit lookup), pr merge (marker file), pr ready. Anything else is an
# error so tests notice unexpected calls.
[[ -n "${FAKE_GH_LOG:-}" ]] && echo "$*" >> "$FAKE_GH_LOG"
if [[ "$1 $2" == "pr create" ]]; then
  echo "https://github.com/testowner/testrepo/pull/12"; exit 0
fi
if [[ "$1 $2" == "pr view" && "$*" == *"mergeCommit"* ]]; then
  echo "0f00dfeedddeadbeefc0ffee0000000000000042"; exit 0
fi
if [[ "$1 $2" == "pr view" ]]; then
  [[ -n "${FAKE_PR_VIEW_JSON:-}" ]] || { echo "fake-gh: FAKE_PR_VIEW_JSON not set" >&2; exit 9; }
  cat "$FAKE_PR_VIEW_JSON"; exit 0
fi
if [[ "$1 $2" == "pr merge" ]]; then
  [[ -n "${FAKE_MERGED:-}" ]] || { echo "fake-gh: FAKE_MERGED not set" >&2; exit 9; }
  : > "$FAKE_MERGED"; echo "squashed"; exit 0
fi
if [[ "$1 $2" == "pr ready" ]]; then echo "ready"; exit 0; fi
echo "fake-gh: unexpected call: $*" >&2; exit 9
EOF
  chmod +x "$1/fake-grok" "$1/fake-gh"
}

setup_env() { # $1 = base dir — bare origin, seed commit, SS_HOME, run dir
  local d="$1"
  git init --bare -q -b main "$d/origin.git" || fail "git init --bare failed"
  git clone -q "$d/origin.git" "$d/seed" || fail "seed clone failed"
  git -C "$d/seed" config user.name "Site Signal Test"
  git -C "$d/seed" config user.email "site-signal-test@example.invalid"
  echo "<html><body>seed</body></html>" > "$d/seed/index.html"
  git -C "$d/seed" add -A && git -C "$d/seed" commit -qm seed || fail "seed commit failed"
  git -C "$d/seed" push -q origin main || fail "seed push failed"

  mkdir -p "$d/ss/repos/testowner" "$d/run"
  git clone -q "$d/origin.git" "$d/ss/repos/testowner/testrepo" || fail "repo clone failed"
  git -C "$d/ss/repos/testowner/testrepo" config user.name "Site Signal Test"
  git -C "$d/ss/repos/testowner/testrepo" config user.email "site-signal-test@example.invalid"

  cat > "$d/ss/sites.yaml" <<'EOF'
sites:
  - domain: example.test
    repo: testowner/testrepo
    default_branch: main
    owner_verified: true
    deploy: unknown
    scan:
      pages: 1
      axe_paths: ["/"]
EOF
  # Minimal ranked report: one serious issue so select_issues picks it.
  cat > "$d/run/report.json" <<'EOF'
{"domain": "example.test",
 "issues": [{"dimension": "seo", "id": "regression-issue", "impact": "serious",
             "message": "regression fixture issue", "where": "/", "evidence": [],
             "effort": "S", "reach": 1, "fix": "Add the missing regression attribute."}]}
EOF
  printf 'forbidden-brand-x\n' > "$d/deny-terms.txt"
}

make_pr_view() { # $1 = file, $2 = green|red|none
  local rollup
  case "$2" in
    green) rollup='[{"__typename":"CheckRun","name":"ci","status":"COMPLETED","conclusion":"SUCCESS"}]' ;;
    red)   rollup='[{"__typename":"CheckRun","name":"ci","status":"COMPLETED","conclusion":"FAILURE"},{"__typename":"CheckRun","name":"lint","status":"PENDING","conclusion":null}]' ;;
    none)  rollup='[]' ;;
    *) return 1 ;;
  esac
  printf '{"state":"OPEN","isDraft":false,"mergeable":"MERGEABLE","headRefOid":"c0ffee0000000000000000000000000000000001","title":"Site Signal: regression","url":"https://github.com/testowner/testrepo/pull/12","statusCheckRollup":%s}' \
    "$rollup" > "$1"
}

# Run the real ship_fix.sh with a temp SS_HOME and the fake binaries; echoes
# its exit code, log at $base/log. Callers export FAKE_* fixture vars first.
run_ship() { # $1 = base dir; remaining args -> ship_fix.sh
  local d="$1"; shift
  (
    export SITE_SIGNAL_HOME="$d/ss"
    export SITE_SIGNAL_DENY_TERMS="$d/deny-terms.txt"
    export PYTHON="$PY"
    export GROK_BIN="$d/fake-grok"
    export GH_BIN="$d/fake-gh"
    export FAKE_GROK_MAKES_CHANGES="${FAKE_GROK_MAKES_CHANGES:-1}"
    export FAKE_PR_VIEW_JSON="${FAKE_PR_VIEW_JSON:-}"
    export FAKE_MERGED="${FAKE_MERGED:-}"
    export FAKE_GH_LOG="${FAKE_GH_LOG:-}"
    bash "$SHIP_FIX" "$@"
  ) > "$d/log" 2>&1
  echo $?
}

ss_branches() { # count of site-signal/* branches on the bare origin
  git --git-dir "$1/origin.git" for-each-ref --format='%(refname:short)' refs/heads \
    | grep -c '^site-signal/' || true
}
show_log() { sed -n '1,40p' "$1/log" >&2; }

TMP="$(mktemp -d /tmp/ss-shipfix-gate.XXXXXX)"
trap 'rm -rf "$TMP"' EXIT

# =========== Scenario 1 (F1): ship with changes -> push, exit 0 ==============
S="$TMP/ship-changes"; mkdir -p "$S"; setup_env "$S"; write_fakes "$S"
rc="$(run_ship "$S" --repo testowner/testrepo --domain example.test --run-dir "$S/run" \
        --approved-by-owner "ship testrepo" --skip-tests --no-wait)"
[[ "$rc" == "0" ]] || { show_log "$S"; fail "ship with changes exited $rc (expected 0)"; }
grep -q "branch pushed" "$S/log" || { show_log "$S"; fail "no branch pushed"; }
grep -q "awaiting owner approval" "$S/log" || { show_log "$S"; fail "did not reach the approval gate"; }
[[ "$(ss_branches "$S")" -ge 1 ]] || fail "no site-signal/* branch on origin after a successful ship"
BR="$(git --git-dir "$S/origin.git" for-each-ref --format='%(refname:short)' refs/heads | grep '^site-signal/' | head -1)"
git --git-dir "$S/origin.git" show "$BR:fix-applied.txt" >/dev/null 2>&1 \
  || fail "pushed branch $BR does not contain the seeded change"
echo "PASS: ship with changes pushes and reaches the approval gate (exit 0)"

# =========== Scenario 2 (F1): ship with NO changes -> die, push nothing ======
S="$TMP/ship-empty"; mkdir -p "$S"; setup_env "$S"; write_fakes "$S"
export FAKE_GROK_MAKES_CHANGES=0
rc="$(run_ship "$S" --repo testowner/testrepo --domain example.test --run-dir "$S/run" \
        --approved-by-owner "ship testrepo" --skip-tests --no-wait)"
unset FAKE_GROK_MAKES_CHANGES
[[ "$rc" == "1" ]] || { show_log "$S"; fail "empty ship exited $rc (expected 1)"; }
grep -q "no changes in" "$S/log" || { show_log "$S"; fail "empty ship did not die with 'no changes'"; }
if grep -q "branch pushed" "$S/log"; then show_log "$S"; fail "empty ship pushed a branch anyway"; fi
[[ "$(ss_branches "$S")" -eq 0 ]] || fail "origin gained a branch from an empty ship"
echo "PASS: ship with no changes dies at the gate and pushes nothing"

# =========== Scenario 3 (F2): --merge with a red check -> refuse =============
S="$TMP/merge-red"; mkdir -p "$S"; setup_env "$S"; write_fakes "$S"
make_pr_view "$S/pr-view.json" red
export FAKE_PR_VIEW_JSON="$S/pr-view.json" FAKE_MERGED="$S/merged" FAKE_GH_LOG="$S/gh.log"
rc="$(run_ship "$S" --merge 12 --repo testowner/testrepo --domain example.test \
        --run-dir "$S/run" --approved-by-owner "merge testrepo#12" --skip-rescan)"
[[ "$rc" == "1" ]] || { show_log "$S"; fail "red --merge exited $rc (expected 1)"; }
grep -q "CI must be green on the head SHA" "$S/log" \
  || { show_log "$S"; fail "red --merge did not cite the CI gate"; }
[[ ! -e "$S/merged" ]] || fail "red PR was merged anyway"
echo "PASS: --merge refuses a PR with failing/pending checks"

# =========== Scenario 4 (F2): --merge green -> merge =========================
S="$TMP/merge-green"; mkdir -p "$S"; setup_env "$S"; write_fakes "$S"
make_pr_view "$S/pr-view.json" green
export FAKE_PR_VIEW_JSON="$S/pr-view.json" FAKE_MERGED="$S/merged" FAKE_GH_LOG="$S/gh.log"
rc="$(run_ship "$S" --merge 12 --repo testowner/testrepo --domain example.test \
        --run-dir "$S/run" --approved-by-owner "merge testrepo#12" --skip-rescan)"
[[ "$rc" == "0" ]] || { show_log "$S"; fail "green --merge exited $rc (expected 0)"; }
grep -q "done: PR #12 merged" "$S/log" || { show_log "$S"; fail "green --merge did not complete"; }
grep -q "CI green on #12" "$S/log" || { show_log "$S"; fail "green --merge did not log the CI gate pass"; }
[[ -e "$S/merged" ]] || fail "green --merge never invoked gh pr merge"
echo "PASS: --merge merges a CI-green PR"

# =========== Scenario 5 (F2): --merge with no checks -> vacuous pass =========
S="$TMP/merge-nochecks"; mkdir -p "$S"; setup_env "$S"; write_fakes "$S"
make_pr_view "$S/pr-view.json" none
export FAKE_PR_VIEW_JSON="$S/pr-view.json" FAKE_MERGED="$S/merged" FAKE_GH_LOG="$S/gh.log"
rc="$(run_ship "$S" --merge 12 --repo testowner/testrepo --domain example.test \
        --run-dir "$S/run" --approved-by-owner "merge testrepo#12" --skip-rescan)"
[[ "$rc" == "0" ]] || { show_log "$S"; fail "no-checks --merge exited $rc (expected 0)"; }
grep -q "vacuously satisfied" "$S/log" || { show_log "$S"; fail "no-checks run did not log the vacuous pass"; }
[[ -e "$S/merged" ]] || fail "no-checks --merge never invoked gh pr merge"
echo "PASS: --merge with no checks configured logs the vacuous pass and merges"

write_sites() { # $1 base, rest is yaml on stdin
  cat > "$1/ss/sites.yaml"
}

# =========== Scenario 6: after_green_ci without consent does not merge =======
S="$TMP/policy-bare"; mkdir -p "$S"; setup_env "$S"; write_fakes "$S"
write_sites "$S" <<'EOF'
sites:
  - domain: example.test
    repo: testowner/testrepo
    default_branch: main
    owner_verified: true
    deploy: unknown
    merge: after_green_ci
    scan:
      pages: 1
      axe_paths: ["/"]
EOF
make_pr_view "$S/pr-view.json" green
export FAKE_PR_VIEW_JSON="$S/pr-view.json" FAKE_MERGED="$S/merged" FAKE_GH_LOG="$S/gh.log"
rc="$(run_ship "$S" --merge 12 --repo testowner/testrepo --domain example.test \
        --run-dir "$S/run" --skip-rescan)"
[[ "$rc" == "1" ]] || { show_log "$S"; fail "bare after_green_ci exited $rc (expected 1)"; }
[[ ! -e "$S/merged" ]] || fail "bare after_green_ci merged without a human confirmation"
grep -q "not auto-merging\|refusing to merge" "$S/log" \
  || { show_log "$S"; fail "bare after_green_ci did not explain the refusal"; }
echo "PASS: after_green_ci without merge_consent does not merge"

# =========== Scenario 7: consent naming the domain may merge =================
S="$TMP/policy-consent"; mkdir -p "$S"; setup_env "$S"; write_fakes "$S"
write_sites "$S" <<'EOF'
sites:
  - domain: example.test
    repo: testowner/testrepo
    default_branch: main
    owner_verified: true
    deploy: unknown
    merge: after_green_ci
    merge_consent:
      domain: example.test
      phrase: "always merge green PRs for example.test"
      set_by: owner
      set_at: "2026-11-06T00:00:00Z"
    scan:
      pages: 1
      axe_paths: ["/"]
EOF
make_pr_view "$S/pr-view.json" green
export FAKE_PR_VIEW_JSON="$S/pr-view.json" FAKE_MERGED="$S/merged" FAKE_GH_LOG="$S/gh.log"
rc="$(run_ship "$S" --merge 12 --repo testowner/testrepo --domain example.test \
        --run-dir "$S/run" --skip-rescan)"
[[ "$rc" == "0" ]] || { show_log "$S"; fail "named consent exited $rc (expected 0)"; }
[[ -e "$S/merged" ]] || fail "named consent never merged"
grep -q "set_by owner" "$S/log" || { show_log "$S"; fail "consent merge did not record who set it"; }
grep -q "2026-11-06T00:00:00Z" "$S/run/approval-testrepo.md" \
  || { show_log "$S"; fail "approval record did not store when consent was set"; }
echo "PASS: merge_consent naming the domain records who and when, then merges"

# =========== Scenario 8: consent for a different domain does not merge =======
S="$TMP/policy-other"; mkdir -p "$S"; setup_env "$S"; write_fakes "$S"
write_sites "$S" <<'EOF'
sites:
  - domain: example.test
    repo: testowner/testrepo
    default_branch: main
    owner_verified: true
    deploy: unknown
    merge: after_green_ci
    merge_consent:
      domain: other.example
      phrase: "always merge green PRs for other.example"
      set_by: owner
      set_at: "2026-11-06T00:00:00Z"
    scan:
      pages: 1
      axe_paths: ["/"]
EOF
make_pr_view "$S/pr-view.json" green
export FAKE_PR_VIEW_JSON="$S/pr-view.json" FAKE_MERGED="$S/merged" FAKE_GH_LOG="$S/gh.log"
rc="$(run_ship "$S" --merge 12 --repo testowner/testrepo --domain example.test \
        --run-dir "$S/run" --skip-rescan)"
[[ "$rc" == "1" ]] || { show_log "$S"; fail "foreign consent exited $rc (expected 1)"; }
[[ ! -e "$S/merged" ]] || fail "consent for another domain merged this site"
echo "PASS: merge_consent for a different domain does not merge"

echo "ALL PASS: ship_fix no-changes gate + merge CI gate (F1/F2) + merge consent"
