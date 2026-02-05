#!/usr/bin/env bash
# Auto-commit changes in ~/.openclaw/workspace safely (no secrets, no runtime).
set -euo pipefail
REPO="$HOME/.openclaw/workspace"
cd "$REPO"
# If not a repo, do nothing (quietly)
git rev-parse --is-inside-work-tree >/dev/null 2>&1 || exit 0
# Make sure ignore rules exist
[ -f .gitignore ] || exit 0
# Stage tracked + new files (gitignore will prevent sensitive stuff)
git add -A
# If nothing to commit, exit quietly
if git diff --cached --quiet; then
  exit 0
fi
# Build a short summary for the commit message
summary="$(git diff --cached --name-status | head -n 20 | tr '\n' '; ' | sed 's/; $//')"
ts="$(date '+%Y-%m-%d %H:%M:%S %Z')"
git commit -m "openclaw workspace autosave: $ts" -m "Changes: $summary"
