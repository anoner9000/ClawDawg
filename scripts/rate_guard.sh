#!/usr/bin/env bash
# rate_guard.sh - simple rate-guard circuit breaker for heartbeat LLM runner
# Usage: ./rate_guard.sh --record 429  (records a 429 event)
#        ./rate_guard.sh --check         (returns nonzero if circuit open)
#        ./rate_guard.sh --reset         (clear counters)

if [ -f "$HOME/.openclaw/workspace/.env" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.openclaw/workspace/.env"
fi
RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
LOG_DIR="$RUNTIME_DIR/logs/heartbeat"
COUNTER_FILE="$LOG_DIR/ratelimit_counter.json"
PAUSE_FLAG="$RUNTIME_DIR/var/heartbeat.paused"
THRESHOLD=5       # number of 429s in WINDOW to trip
WINDOW=300        # seconds window to count (5 minutes)

mkdir -p "$LOG_DIR" "$(dirname "$PAUSE_FLAG")"

cmd=${1:---check}

record_event(){
  ts=$(date +%s)
  jq --arg time "$ts" '.events += [$time|tonumber]' "$COUNTER_FILE" 2>/dev/null || echo '{"events":['$ts']}' > "$COUNTER_FILE"
  # prune old
  jq --arg now "$ts" --argjson w $WINDOW '.events = (.events|map(select((($now|tonumber)-.|tonumber) < $w)))' "$COUNTER_FILE" > "$COUNTER_FILE.tmp" && mv "$COUNTER_FILE.tmp" "$COUNTER_FILE"
  count=$(jq '.events|length' "$COUNTER_FILE")
  echo "Recorded event. Count in window: $count" >> "$LOG_DIR/ratelimit.log"
  if [ "$count" -ge $THRESHOLD ]; then
    touch "$PAUSE_FLAG"
    echo "Circuit opened at $(date -Is) due to $count 429s." >> "$LOG_DIR/ratelimit.log"
  fi
}

check_circuit(){
  if [ -f "$PAUSE_FLAG" ]; then
    echo "CIRCUIT_OPEN"
    return 1
  fi
  echo "CIRCUIT_CLOSED"
  return 0
}

reset(){
  rm -f "$PAUSE_FLAG" "$COUNTER_FILE"
  echo "Circuit reset at $(date -Is)" >> "$LOG_DIR/ratelimit.log"
}

case "$cmd" in
  --record)
    record_event
    ;;
  --check)
    check_circuit
    ;;
  --reset)
    reset
    ;;
  *)
    echo "Usage: $0 [--record | --check | --reset]"
    exit 2
    ;;
esac
