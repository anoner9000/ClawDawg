#!/usr/bin/env bash
set -euo pipefail

WORKSPACE="${HOME}/.openclaw/workspace"
PY="${HOME}/.openclaw/venv/bin/python3"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3)"
fi

exec "$PY" -u "$WORKSPACE/modules/gmail/scripts/gmail_cleanup_manage_senders.py" "$@"
