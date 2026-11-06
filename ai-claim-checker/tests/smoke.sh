#!/usr/bin/env bash
# Offline SPEC §8 contract checks. No model calls.
# If grok is missing, say so and continue. Do not swap in another build CLI.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
export PYTHONDONTWRITEBYTECODE=1

if ! command -v grok >/dev/null 2>&1 && [[ ! -x "${HOME}/.local/bin/grok" ]] && [[ ! -x "${HOME}/.grok/bin/grok" ]]; then
  echo "Grok Build is not installed. Install Grok Build, or use Cursor, Claude Code, or Codex."
fi

shopt -s nullglob
for script in "$ROOT"/tests/*.sh "$ROOT"/scripts/*.sh; do
  bash -n "$script"
done
for script in "$ROOT"/scripts/*.py; do
  python3 -m py_compile "$script"
done

rc=0
for test in \
  test_onboard_cron.py \
  test_verdicts.py \
  test_decompose.py \
  test_card.py \
  test_weekly.py \
  test_redteam_contract.py \
  test_static.py
do
  python3 "$ROOT/tests/$test" || rc=1
done

if [[ "$rc" -eq 0 ]]; then
  echo "smoke: PASS"
else
  echo "smoke: FAIL" >&2
  exit 1
fi
