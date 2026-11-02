#!/usr/bin/env bash
# Offline half of the parity smoke list. Live GitHub cases need a throwaway repo.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
bash "$ROOT/tests/test_git_guard.sh"
python3 "$ROOT/tests/test_untrusted.py"
bash "$ROOT/tests/test_drive_coder.sh"
bash "$ROOT/tests/test_handoff.sh"
if [[ -f "$ROOT/tests/test_merge_decision.py" ]]; then
  python3 "$ROOT/tests/test_merge_decision.py"
fi
echo "smoke offline: PASS"
