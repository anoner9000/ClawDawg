#!/usr/bin/env bash
set -euo pipefail

progress_file="projects/agent_ops/PROGRESS.md"

if [[ ! -f "$progress_file" ]]; then
  echo "ERROR: Required progress file not found: $progress_file" >&2
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 \"Short title\"" >&2
  exit 2
fi

title="$*"
ts="$(date '+%Y-%m-%d %H:%M:%S %Z')"

printf "\n" >> "$progress_file"
printf "### %s — %s\n" "$ts" "$title" >> "$progress_file"
cat >> "$progress_file" <<'ENTRY_EOF'
- What changed:
  - [Placeholder]
  - Unknown facts marked as [Unknown]; TODO to verify.
- Files created/modified:
  - [Placeholder]
- Commands run (if any):
  - [Placeholder]
- Evidence/refs (file paths + section headings):
  - [Placeholder]
- Next steps:
  - [Placeholder]
ENTRY_EOF
printf "\n" >> "$progress_file"
