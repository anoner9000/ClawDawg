#!/usr/bin/env bash
set -euo pipefail

WS="$HOME/.openclaw/workspace"
RT="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
HB="$RT/logs/heartbeat"
REPORT="$HB/ledger_report_accounting_latest.html"

# Accounting renderer disabled: only open pre-existing report.
if [ ! -f "$REPORT" ]; then
  echo "Accounting report renderer is disabled and no report exists at: $REPORT"
  exit 0
fi

# Open it (WSL-friendly)
if command -v wslview >/dev/null 2>&1; then
  wslview "$REPORT" >/dev/null 2>&1 &
elif command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$REPORT" >/dev/null 2>&1 &
else
  echo "Report generated at: $REPORT"
  echo "No opener found (wslview/xdg-open missing)."
fi

echo "Opened: $REPORT"
