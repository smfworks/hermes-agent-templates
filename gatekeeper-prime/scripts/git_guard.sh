#!/usr/bin/env bash
# Floor under both profiles. Refuses merge, push to the protected branch,
# and a silent force-push. Branch protection is still the real lock.
set -euo pipefail

PROTECTED="${PROTECTED_BRANCH:-main}"

die() { echo "git_guard: $*" >&2; exit 2; }

usage() {
  echo "usage: git_guard.sh {check-push|push|check-gh|gh} -- <args>" >&2
  exit 64
}

[[ $# -ge 1 ]] || usage
cmd="$1"
shift
[[ "${1:-}" == "--" ]] && shift || true

python_classify() {
  PROTECTED_BRANCH="$PROTECTED" python3 - "$@" <<'PY'
import os, sys
protected = os.environ.get("PROTECTED_BRANCH", "main")
args = sys.argv[1:]
force = False
positionals = []
for a in args:
    if a in ("-f", "--force", "--force-with-lease", "--force-if-includes") or a.startswith("--force"):
        force = True
        continue
    if a.startswith("-") and not a.startswith("--") and "f" in a[1:]:
        force = True
        continue
    if not a.startswith("-"):
        positionals.append(a)
refspecs = positionals[1:] if len(positionals) >= 2 else positionals
hit = False
for ref in refspecs:
    dst = ref.split(":")[-1]
    if dst.startswith("refs/heads/"):
        dst = dst[len("refs/heads/"):]
    if dst in ("", "HEAD"):
        # Fail closed. Push the branch name, not HEAD.
        hit = True
        break
    if dst == protected or dst.endswith("/" + protected):
        hit = True
        break
print("force" if force else "noforce")
print("protected" if hit else "ok")
PY
}

case "$cmd" in
  check-push|push)
    mapfile -t cls < <(python_classify "$@")
    force="${cls[0]}"
    where="${cls[1]}"
    if [[ "$where" == "protected" ]]; then
      die "refusing push to protected branch '$PROTECTED' (or HEAD). Push a feature branch name."
    fi
    if [[ "$force" == "force" ]]; then
      if [[ "${OWNER_CONFIRMED_OVERWRITE:-}" != "yes" || -z "${OVERWRITE_REASON:-}" ]]; then
        echo "git_guard: force-push refused. Tell the owner exactly what it would overwrite and wait for an explicit yes. Then re-run with OWNER_CONFIRMED_OVERWRITE=yes and OVERWRITE_REASON set." >&2
        exit 3
      fi
      echo "git_guard: force-push allowed after owner confirmation: $OVERWRITE_REASON" >&2
    fi
    if [[ "$cmd" == "check-push" ]]; then
      echo "git_guard: push check ok"
      exit 0
    fi
    exec git push "$@"
    ;;
  check-gh|gh)
    if [[ "${1:-}" == "pr" && "${2:-}" == "merge" ]]; then
      die "refusing gh pr merge. Builder never merges. Gatekeeper merges only through scripts/merge_gate.sh after the owner's GitHub review on this head SHA."
    fi
    if [[ "${1:-}" == "api" ]]; then
      blob="$*"
      if [[ "$blob" == *"/merge"* || "$blob" == *"/merges"* ]]; then
        die "refusing GitHub merge API. Use scripts/merge_gate.sh on the reviewer profile, and only after the owner's review on this SHA."
      fi
    fi
    if [[ "$cmd" == "check-gh" ]]; then
      echo "git_guard: gh check ok"
      exit 0
    fi
    GH_BIN="${GH_BIN:-gh}"
    exec "$GH_BIN" "$@"
    ;;
  *)
    usage
    ;;
esac
