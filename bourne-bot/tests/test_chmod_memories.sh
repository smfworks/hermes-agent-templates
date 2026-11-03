#!/usr/bin/env bash
# A 0644 memory file must be 0600 after chmod_memories.sh.
set -euo pipefail
ROOT=$(cd "$(dirname "$0")/.." && pwd)
S="$ROOT/scripts/chmod_memories.sh"
fail() { echo "FAIL: $*" >&2; exit 1; }

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

dir="$tmp/memories"
mkdir -p "$dir"
echo placeholder > "$dir/USER.md"
echo other > "$dir/MEMORY.md"
chmod 0644 "$dir/USER.md" "$dir/MEMORY.md"

bash "$S" "$dir"

user_mode=$(stat -c %a "$dir/USER.md")
mem_mode=$(stat -c %a "$dir/MEMORY.md")
[[ "$user_mode" == "600" || "$user_mode" == "0600" ]] || fail "USER.md mode $user_mode"
[[ "$mem_mode" == "600" || "$mem_mode" == "0600" ]] || fail "MEMORY.md mode $mem_mode"
# Directory stays usable. 0600 on a directory would drop the execute bit.
[[ -r "$dir/USER.md" ]] || fail "USER.md not readable after chmod"

listed="$tmp/STATE.md"
echo scratch > "$listed"
chmod 0644 "$listed"
bash "$S" "$listed"
listed_mode=$(stat -c %a "$listed")
[[ "$listed_mode" == "600" || "$listed_mode" == "0600" ]] || fail "listed file mode $listed_mode"

echo "chmod_memories: PASS"
