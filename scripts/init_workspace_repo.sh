#!/usr/bin/env bash
# init_workspace_repo.sh - initialize a private git repo for the workspace (non-destructive)
set -euo pipefail
WS=~/.openclaw/workspace
cd "$WS"
if [ -d .git ]; then
  echo "Repo already initialized"
  exit 0
fi
git init
git add AGENTS.md SOUL.md TOOLS.md IDENTITY.md USER.md HEARTBEAT.md || true
git commit -m "Add agent workspace" || true
echo "Created git repo in $WS; add private remote and push as needed."
