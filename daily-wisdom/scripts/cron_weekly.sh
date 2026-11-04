#!/usr/bin/env bash
# Daily Wisdom weekly page. Cron runs this with --no-agent.
set -euo pipefail
HOME_DIR="${HERMES_HOME:-$(cd "$(dirname "$0")/.." && pwd)}"
DATA="${HOME_DIR}/wisdom"
mkdir -p "$DATA"
exec python3 "${HOME_DIR}/scripts/weekly.py" --data "$DATA"
