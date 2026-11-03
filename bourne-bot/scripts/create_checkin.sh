#!/usr/bin/env bash
# Write the quarterly Bourne check-in into a Hermes cron/jobs.json.
# The file changes only when --yes is present. This does not call hermes
# and does not register a job on this host.
#
# The job prompt documents the command that writes a dated markdown status
# file labelled "as of <date>". This script does not run that command.
set -euo pipefail

ROOT=$(cd "$(dirname "$0")/.." && pwd)
YES=0
JOBS=""

usage() {
  echo "usage: create_checkin.sh [--yes] [--jobs PATH]" >&2
  exit 64
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --yes)
      YES=1
      shift
      ;;
    --jobs)
      [[ $# -ge 2 ]] || usage
      JOBS=$2
      shift 2
      ;;
    -h|--help)
      usage
      ;;
    *)
      echo "create_checkin: unknown argument" >&2
      usage
      ;;
  esac
done

if [[ -z "$JOBS" ]]; then
  JOBS="$ROOT/cron/jobs.json"
fi

if [[ "$YES" -ne 1 ]]; then
  echo "Check-in not created. Pass --yes to write cron/jobs.json. The file was not changed."
  exit 0
fi

python3 - "$JOBS" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

path = Path(sys.argv[1])
if path.exists():
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw) if raw.strip() else []
    except (OSError, json.JSONDecodeError):
        sys.stderr.write("create_checkin: jobs.json could not be read. Nothing written.\n")
        sys.exit(2)
else:
    data = []

if data == [] or data is None:
    jobs = []
elif isinstance(data, list):
    jobs = data
elif isinstance(data, dict) and isinstance(data.get("jobs"), list):
    jobs = data["jobs"]
else:
    sys.stderr.write("create_checkin: jobs.json shape was not a job list. Nothing written.\n")
    sys.exit(2)

prompt = """Write a dated markdown status file for the quarterly security check-in. Label the page "as of <date>" with today's date in YYYY-MM-DD. Path: checkins/<YYYY-MM-DD>.md. The gateway message is two lines plus that path. Use the file tool. Do not store secrets.

Documented command (create_checkin.sh does not run it, and this script does not register a hermes job):
d=$(date +%F); mkdir -p checkins; printf '# Security check-in\\n\\nAs of %s\\n' "$d" > "checkins/${d}.md"
"""

job = {
    "id": "bourne-security-checkin",
    "name": "Bourne security check-in",
    "prompt": prompt,
    "skills": ["bourne-threat-model"],
    "skill": "bourne-threat-model",
    "model": None,
    "provider": None,
    "base_url": None,
    "script": None,
    "no_agent": False,
    "context_from": None,
    "schedule": {
        "kind": "cron",
        "expr": "0 9 1 1,4,7,10 *",
        "display": "0 9 1 1,4,7,10 *",
    },
    "schedule_display": "0 9 1 1,4,7,10 *",
    "deliver": "local",
    "origin": None,
    "enabled_toolsets": ["file", "memory", "skills"],
    "workdir": None,
    "enabled": True,
    "state": "scheduled",
    "paused_at": None,
    "paused_reason": None,
}

jobs = [item for item in jobs if item.get("id") != job["id"]]
jobs.append(job)
payload = {
    "jobs": jobs,
    "updated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
}
path.parent.mkdir(parents=True, exist_ok=True)
tmp = path.with_name(path.name + ".tmp")
tmp.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
tmp.replace(path)
PY

echo "Check-in job written. Not registered with hermes."
