#!/usr/bin/env bash
set -euo pipefail
ROOT="$(git -C "${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}" rev-parse --show-toplevel 2>/dev/null || true)"
if [ -z "$ROOT" ]; then
  ROOT="${OPENCLAW_WORKSPACE:-$HOME/.openclaw/workspace}"
fi
exec python3 "$ROOT/agents/scribe/time_now.py" "$@"
