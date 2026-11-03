#!/usr/bin/env bash
# Drive Grok Build in a worktree. If it is missing, stop and name the alternatives.
# Never swap in another CLI on your own.
set -euo pipefail
CWD=""
PROMPT=""
MODEL="${GROK_MODEL:-spark-glm}"
GROK_BIN="${GROK_BIN:-grok}"
MAX_TURNS="${MAX_TURNS:-40}"
while [[ $# -gt 0 ]]; do
  case "$1" in
    --cwd) CWD="$2"; shift 2 ;;
    --prompt-file) PROMPT="$2"; shift 2 ;;
    --model) MODEL="$2"; shift 2 ;;
    *) echo "drive_coder: unknown arg $1" >&2; exit 64 ;;
  esac
done
[[ -n "$CWD" && -n "$PROMPT" && -f "$PROMPT" ]] || {
  echo "usage: drive_coder.sh --cwd DIR --prompt-file FILE [--model NAME]" >&2
  exit 64
}
missing() {
  cat <<EOF
drive_coder: Grok Build is not installed (looked for: $GROK_BIN).
Install Grok Build, or tell me to drive one of these instead: Cursor, Claude Code, or Codex.
I will not swap in another CLI on my own.
EOF
  exit 4
}
if [[ "$GROK_BIN" == */* ]]; then
  [[ -x "$GROK_BIN" ]] || missing
else
  command -v "$GROK_BIN" >/dev/null 2>&1 || missing
fi
exec "$GROK_BIN" --no-auto-update -m "$MODEL" --cwd "$CWD" --always-approve --max-turns "$MAX_TURNS" --output-format json -p "$(cat "$PROMPT")"
