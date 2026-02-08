#!/usr/bin/env bash
# ledger_view.sh — start a local viewer for the latest ledger HTML, then stop on keypress.
# Binds to 127.0.0.1 only (local machine).
set -euo pipefail

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
HB_DIR="$RUNTIME_DIR/logs/heartbeat"
FILE="${1:-ledger_report_accounting_deco_latest.html}"
PORT="${PORT:-8000}"

cd "$HB_DIR"

if [ ! -f "$FILE" ]; then
  echo "Missing report: $HB_DIR/$FILE" >&2
  echo "Tip: list reports with: ls -1 $HB_DIR/*.html" >&2
  exit 2
fi

# Ensure tmux exists
if ! command -v tmux >/dev/null 2>&1; then
  echo "tmux not found. Install it or run: python3 -m http.server $PORT --bind 127.0.0.1" >&2
  exit 2
fi

SESSION="ledger_server"
URL="http://127.0.0.1:${PORT}/${FILE}"

# Kill any prior session with same name (clean slate)
tmux kill-session -t "$SESSION" >/dev/null 2>&1 || true

# Start server detached
tmux new -s "$SESSION" -d "cd '$HB_DIR' && python3 -m http.server '$PORT' --bind 127.0.0.1"

echo
echo "Ledger viewer running in tmux session: $SESSION"
echo "Open this URL:"
echo "  $URL"
echo
echo "Press ENTER to stop the server..."
read -r _

tmux kill-session -t "$SESSION" >/dev/null 2>&1 || true
echo "Stopped."
