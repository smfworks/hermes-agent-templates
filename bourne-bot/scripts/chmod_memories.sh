#!/usr/bin/env bash
# Set memory files to mode 0600.
# A directory argument applies to regular files inside it. The directory
# itself stays traversable (it needs the execute bit). There is no
# encryption-at-rest.
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: chmod_memories.sh DIR|FILE..." >&2
  exit 64
fi

status=0
for target in "$@"; do
  if [[ ! -e "$target" ]]; then
    echo "chmod_memories: missing path" >&2
    status=1
    continue
  fi
  if [[ -d "$target" ]]; then
    while IFS= read -r -d '' file; do
      chmod 0600 "$file"
    done < <(find "$target" -xdev -type f -print0)
  elif [[ -f "$target" ]]; then
    chmod 0600 "$target"
  else
    echo "chmod_memories: not a file or directory" >&2
    status=1
  fi
done

exit "$status"
