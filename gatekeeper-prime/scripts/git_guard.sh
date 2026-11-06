#!/usr/bin/env bash
# Floor under both profiles. Refuses merge, push to the protected branch,
# a silent force-push, and yes-shaped comments posted by a bot. The owner
# types their own yes. The merge account must be a different GitHub user.
# Branch protection is still the real lock.
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

# A yes naming the head SHA is the owner's own signature. The account
# that merges must be a different GitHub user, and a bot must still never
# post that comment. Inspect the body the bot is about to send and
# refuse yes-shaped ones: body starts with a yes ($GK_YES_REGEX,
# case-insensitive) AND contains a 40-hex SHA. handoff's bp-handoff bodies
# name SHAs but never start with a yes, so they pass. Prints "yes" or
# "ok"; never echoes the pattern itself.
comment_classify() {
  GK_YES_REGEX="${GK_YES_REGEX:-^yes\b}" python3 - "$@" <<'PY'
import json, os, re, sys

args = sys.argv[1:]
hex40 = re.compile(r"[0-9a-fA-F]{40}")
try:
    yes_rx = re.compile(os.environ.get("GK_YES_REGEX", r"^yes\b"), re.IGNORECASE)
except re.error:
    yes_rx = re.compile(r"^yes\b", re.IGNORECASE)


def read_path(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


def stdin_body():
    return os.environ.get("GK_STDIN_BODY") or ""


def field_value(val):
    # gh -F/--field magic: @file reads a file, @- reads stdin.
    if val.startswith("@"):
        return stdin_body() if val[1:] == "-" else read_path(val[1:])
    return val


def file_body(path):
    return stdin_body() if path == "-" else read_path(path)


def payload_body(text):
    try:
        parsed = json.loads(text)
    except ValueError:
        return text
    if isinstance(parsed, dict) and isinstance(parsed.get("body"), str):
        return parsed["body"]
    return text


def body_from_comment_args(seq):
    i = 0
    while i < len(seq):
        a = seq[i]
        if a in ("--body", "-b", "--body-file") and i + 1 < len(seq):
            return seq[i + 1] if a != "--body-file" else file_body(seq[i + 1])
        if a.startswith("--body=") or a.startswith("-b="):
            return a.split("=", 1)[1]
        if a.startswith("--body-file="):
            return file_body(a.split("=", 1)[1])
        i += 1
    return None


def body_from_api_args(seq):
    endpoint = any(
        re.search(r"issues/\d+/comments$", a)
        for a in seq[1:] if not a.startswith("-")
    )
    if not endpoint:
        return None
    method = None
    fields = []
    input_val = None
    i = 0
    while i < len(seq):
        a = seq[i]
        nxt = seq[i + 1] if i + 1 < len(seq) else None
        if a in ("--method", "-X") and nxt is not None:
            method = nxt.upper()
            i += 2
            continue
        if a.startswith("--method="):
            method = a.split("=", 1)[1].upper()
            i += 1
            continue
        if a in ("-f", "--raw-field", "-F", "--field") and nxt is not None:
            fields.append(nxt)
            i += 2
            continue
        if a.startswith(("--field=", "--raw-field=", "-F=", "-f=")):
            fields.append(a.split("=", 1)[1])
            i += 1
            continue
        if a == "--input" and nxt is not None:
            input_val = nxt
            i += 2
            continue
        if a.startswith("--input="):
            input_val = a.split("=", 1)[1]
            i += 1
            continue
        i += 1
    # gh posts when a method is given, or when -f/-F fields or an --input
    # body imply one; inspect any body aimed at the comments endpoint.
    if not ((method == "POST") or (method is None and (bool(fields) or input_val is not None))):
        return None
    for f in fields:
        name, _, val = f.partition("=")
        if name == "body":
            return field_value(val)
    if input_val is not None:
        return payload_body(stdin_body()) if input_val == "-" else payload_body(read_path(input_val))
    return None


if len(args) >= 3 and args[0] in ("pr", "issue") and args[1] == "comment":
    body = body_from_comment_args(args[2:])
elif args and args[0] == "api":
    body = body_from_api_args(args)
else:
    body = None

if body and yes_rx.search(body) and hex40.search(body):
    print("yes")
else:
    print("ok")
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
      die "refusing gh pr merge. Builder never merges. Gatekeeper merges only through scripts/merge_gate.sh after the owner's yes comment on this head SHA, from a GitHub account that is not the owner."
    fi
    if [[ "${1:-}" == "api" ]]; then
      blob="$*"
      if [[ "$blob" == *"/merge"* || "$blob" == *"/merges"* ]]; then
        die "refusing GitHub merge API. Use scripts/merge_gate.sh on the reviewer profile, and only after the owner's yes comment on this SHA from a different GitHub account."
      fi
    fi
    # A comment body can arrive on stdin (--input -, --body-file -,
    # -F body=@-). Stash it so the guard can inspect it, then re-feed it.
    STDIN_SAVED=""
    if [[ "$*" == *"--input -"* || "$*" == *"--input=-"* || "$*" == *"--body-file -"* \
       || "$*" == *"--body-file=-"* || "$*" == *"body=@-"* ]]; then
      STDIN_SAVED=$(cat 2>/dev/null || true)
    fi
    verdict=$(GK_STDIN_BODY="$STDIN_SAVED" comment_classify "$@")
    if [[ "$verdict" == "yes" ]]; then
      die "refusing yes-shaped comment. A bot must never post a yes; the owner types their own yes on the PR, and the merge account must not be that owner login."
    fi
    if [[ "$cmd" == "check-gh" ]]; then
      echo "git_guard: gh check ok"
      exit 0
    fi
    GH_BIN="${GH_BIN:-gh}"
    if [[ -n "$STDIN_SAVED" ]]; then
      printf '%s' "$STDIN_SAVED" | "$GH_BIN" "$@"
    else
      exec "$GH_BIN" "$@"
    fi
    ;;
  *)
    usage
    ;;
esac
