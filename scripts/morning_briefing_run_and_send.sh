#!/usr/bin/env bash
set -euo pipefail

WS="$HOME/.openclaw/workspace"
LOG_DIR="$HOME/.openclaw/runtime/logs/heartbeat"
mkdir -p "$LOG_DIR"

# 1) Run aggregator to process queued briefing
"$WS/scripts/heartbeat_aggregator.sh"

# 2) Send the latest response to Telegram
"$WS/modules/briefings/scripts/telegram_send_latest_briefing.sh"
