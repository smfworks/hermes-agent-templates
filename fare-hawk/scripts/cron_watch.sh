#!/usr/bin/env bash
# One watch check for a trip slug. Does not call hermes and does not use a model.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
DATA_DIR=${FARE_HAWK_DATA:-}
SLUG=${1:-${FARE_HAWK_SLUG:-}}
if [[ -z "${DATA_DIR}" || -z "${SLUG}" ]]; then
  echo "usage: FARE_HAWK_DATA=DIR cron_watch.sh SLUG" >&2
  exit 2
fi
shift || true
exec python3 "$ROOT/scripts/watch_prices.py" --data "$DATA_DIR" --slug "$SLUG" "$@"
