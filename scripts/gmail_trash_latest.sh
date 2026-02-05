#!/usr/bin/env bash
set -euo pipefail

QLOG="$(scripts/gmail_latest_quarantine_log_path.sh)"
MAX="${1:-5}"

python3 modules/gmail/scripts/gmail_cleanup_trash.py --quarantine-log "${QLOG}" --confirm TrashApply --max "${MAX}" --apply
