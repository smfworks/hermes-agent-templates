#!/usr/bin/env bash
# The check-in job is written only with --yes, and hermes is not invoked.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
S="$ROOT/scripts/create_checkin.sh"
REAL="$ROOT/cron/jobs.json"
fail() { echo "FAIL: $*" >&2; exit 1; }

real_before=$(cat "$REAL")
[[ ! -d "$ROOT/checkins" ]] || fail "checkins/ already exists"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

jobs="$tmp/jobs.json"
printf '%s\n' '[]' > "$jobs"
before=$(cat "$jobs")

out=$(bash "$S" --jobs "$jobs")
after=$(cat "$jobs")
[[ "$before" == "$after" ]] || fail "jobs.json changed without --yes"
printf '%s' "$out" | grep -q "not created" || fail "missing no-yes message"

bin="$tmp/bin"
mkdir -p "$bin"
cat > "$bin/hermes" <<'EOF'
#!/bin/sh
echo invoked > "$(dirname "$0")/../hermes-invoked"
exit 99
EOF
chmod +x "$bin/hermes"

PATH="$bin:$PATH" bash "$S" --yes --jobs "$jobs" >"$tmp/out"
[[ ! -f "$tmp/hermes-invoked" ]] || fail "hermes was invoked"
grep -q "Not registered" "$tmp/out" || fail "missing not-registered line"
[[ ! -d "$ROOT/checkins" ]] || fail "create_checkin wrote a status directory"

python3 - "$jobs" <<'PY'
import json, sys
data = json.loads(open(sys.argv[1], encoding="utf-8").read())
jobs = data["jobs"]
assert len(jobs) == 1, len(jobs)
job = jobs[0]
assert job["id"] == "bourne-security-checkin"
assert job["enabled"] is True
assert job["state"] == "scheduled"
assert job["no_agent"] is False
assert job["schedule"]["expr"] == "0 9 1 1,4,7,10 *"
blob = json.dumps(job)
assert "as of <date>" in blob
assert "checkins/" in blob
assert "As of" in blob
PY

# Second yes replaces the same id. An unrelated job stays.
python3 - "$jobs" <<'PY'
import json, sys
path = sys.argv[1]
data = json.loads(open(path, encoding="utf-8").read())
data["jobs"].insert(0, {"id": "other-job", "name": "keep"})
open(path, "w", encoding="utf-8").write(json.dumps(data))
PY
bash "$S" --yes --jobs "$jobs" >/dev/null
python3 - "$jobs" <<'PY'
import json, sys
jobs = json.loads(open(sys.argv[1], encoding="utf-8").read())["jobs"]
ids = [j["id"] for j in jobs]
assert ids.count("bourne-security-checkin") == 1, ids
assert "other-job" in ids
PY

real_after=$(cat "$REAL")
[[ "$real_before" == "$real_after" ]] || fail "repo cron/jobs.json changed"
[[ ! -d "$ROOT/checkins" ]] || fail "status directory created in the repo"

echo "create_checkin: PASS"
