#!/usr/bin/env bash
set -euo pipefail

WS="$HOME/.openclaw/workspace"
LOG_DIR="$HOME/.openclaw/runtime/logs"
mkdir -p "$LOG_DIR"

STAMP="$(date -u +'%Y-%m-%d_%H%M%S')"
LOG_FILE="$LOG_DIR/cron_gmail_cleanup_${STAMP}.log"

# Cron won't have your venv activated, so pick an explicit python if present.
PY=""
if [[ -x "$WS/venv/bin/python3" ]]; then
  PY="$WS/venv/bin/python3"
elif [[ -x "$WS/.venv/bin/python3" ]]; then
  PY="$WS/.venv/bin/python3"
else
  PY="$(command -v python3)"
fi

cd "$WS"

{
  echo "[nightly] start_utc=$(date -u --iso-8601=seconds)"

  # 1) Build manifest from your configured sender list
  $PY modules/gmail/scripts/gmail_cleanup_from_config.py

  # 2) Quarantine ALL messages from the latest manifest
  MANIFEST="$(ls -1t "$HOME/.openclaw/runtime/logs"/mail_cleanup_manifest_*.jsonl | head -n 1)"
  echo "[nightly] manifest=$MANIFEST"
  $PY modules/gmail/scripts/gmail_cleanup_quarantine.py --manifest "$MANIFEST" --apply

  # 3) Trash ALL quarantined messages from the quarantine log
  QLOG="${MANIFEST}.quarantine_log"
  echo "[nightly] quarantine_log=$QLOG"
  $PY modules/gmail/scripts/gmail_cleanup_trash.py --quarantine-log "$QLOG" --confirm TrashApply --apply

  echo "[nightly] done_utc=$(date -u --iso-8601=seconds)"
} | tee -a "$LOG_FILE"
