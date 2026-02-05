#!/usr/bin/env bash
# morning_briefing_enqueue.sh - enqueue a daily morning briefing job into llm_queue.jsonl
# Intended to be run by cron at 7:59am local time (or whatever you choose).
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Load runtime config (default runtime dir)
if [ -f "$HOME/.openclaw/workspace/.env" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.openclaw/workspace/.env"
fi

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
QUEUE_DIR="$RUNTIME_DIR/queues"
QUEUE_FILE="$QUEUE_DIR/llm_queue.jsonl"
LOG_DIR="$RUNTIME_DIR/logs/heartbeat"
BRIEFINGS_DIR="$HOME/.openclaw/workspace/briefings"
TEMPLATE="$BRIEFINGS_DIR/morning_8am_template.md"

mkdir -p "$QUEUE_DIR" "$LOG_DIR"
touch "$QUEUE_FILE"

STAMP="$(date -Iseconds)"
JOB_ID="morning-briefing-$(date +%Y-%m-%d)"

# Use template if present; otherwise generate a minimal prompt
if [ -f "$TEMPLATE" ]; then
  PROMPT="$(cat "$TEMPLATE")"
else
  PROMPT="Write my morning briefing. Include: priorities for today, reminders, and a short motivational note."
fi

# Guard: don’t enqueue duplicates for same day (by id)
if grep -q "\"id\":\"$JOB_ID\"" "$QUEUE_FILE" 2>/dev/null; then
  echo "$STAMP already queued: $JOB_ID" >> "$LOG_DIR/morning_enqueue.log"
  exit 0
fi

# Append JSONL job
python3 - <<PY >> "$QUEUE_FILE"
import json, time
job = {
  "id": "$JOB_ID",
  "prompt": """$PROMPT"""
}
print(json.dumps(job, ensure_ascii=False))
PY

echo "$STAMP queued: $JOB_ID -> $QUEUE_FILE" >> "$LOG_DIR/morning_enqueue.log"
