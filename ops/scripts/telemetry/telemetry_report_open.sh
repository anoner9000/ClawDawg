#!/usr/bin/env bash
set -euo pipefail

# Open the latest telemetry HTML report in the Windows default browser
# using wslview (avoids VS Code UNC host restrictions).

REPORT="${1:-$HOME/.openclaw/runtime/logs/heartbeat/ledger_report_accounting_latest.html}"

if [[ ! -f "$REPORT" ]]; then
  echo "ERROR: report not found: $REPORT" >&2
  exit 1
fi

if command -v wslview >/dev/null 2>&1; then
  # Opens using Windows default browser
  exec wslview "$REPORT"
elif command -v xdg-open >/dev/null 2>&1; then
  # Linux desktop fallback
  exec xdg-open "$REPORT"
else
  echo "OK: report path is: $REPORT"
  echo "No opener found (wslview/xdg-open). Open it manually."
fi
