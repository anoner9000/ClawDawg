#!/usr/bin/env bash
set -euo pipefail

repo_root="$(git rev-parse --show-toplevel 2>/dev/null || true)"

if [[ -z "$repo_root" || ! -d "$repo_root/.git" ]]; then
  echo "ERROR: Not inside a git repository (missing .git directory)." >&2
  exit 1
fi

src="$repo_root/projects/agent_ops/tools/hooks/pre-commit"
dst="$repo_root/.git/hooks/pre-commit"

if [[ ! -f "$src" ]]; then
  echo "ERROR: Source hook not found: $src" >&2
  exit 1
fi

cp "$src" "$dst"
chmod +x "$dst"

echo "Installed pre-commit hook successfully."
echo "Path: $dst"
