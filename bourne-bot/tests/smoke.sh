#!/usr/bin/env bash
# Offline guard checks. No model calls. If grok is missing, say so and continue.
# Do not swap in another build CLI.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)

if ! command -v grok >/dev/null 2>&1 && [[ ! -x "${HOME}/.local/bin/grok" ]]; then
  echo "Grok Build is not installed. Install Grok Build, or use Cursor, Claude Code, or Codex."
fi

for script in "$ROOT"/scripts/*.sh "$ROOT"/tests/*.sh; do
  bash -n "$script"
done

python3 "$ROOT/tests/test_secret_paste.py"
python3 "$ROOT/tests/test_forget_memory.py"
bash "$ROOT/tests/test_chmod_memories.sh"
bash "$ROOT/tests/test_create_checkin.sh"
python3 "$ROOT/tests/test_incident_first_step.py"
python3 "$ROOT/tests/test_redteam_contract.py"
echo "smoke: PASS"
