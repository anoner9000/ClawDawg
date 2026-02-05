#!/usr/bin/env bash
set -euo pipefail

QLOG="$(scripts/gmail_latest_quarantine_log_path.sh)"
MAX="${1:-5}"

# Safety guard: require at least one quarantined action in the log
if ! grep -q '"action"[[:space:]]*:[[:space:]]*"quarantined"' "${QLOG}"; then
  echo "Refusing to trash: no entries with action=quarantined found in ${QLOG}" >&2
  exit 1
fi

python3 modules/gmail/scripts/gmail_cleanup_trash.py --quarantine-log "${QLOG}" --confirm TrashApply --max "${MAX}" --apply
