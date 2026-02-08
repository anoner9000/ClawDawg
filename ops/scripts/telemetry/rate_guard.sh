#!/usr/bin/env bash
# rate_guard.sh - simple rate-guard circuit breaker for heartbeat LLM runner
# Usage: ./rate_guard.sh --record --code 429  (records an event with HTTP code)
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
  code=${1:-0}
  ts=$(date +%s)
  # Ensure COUNTER_FILE exists and is valid JSON
  if [ -f "$COUNTER_FILE" ]; then
    tmp=$(mktemp)
    jq --argjson ts "$ts" --argjson code "$code" '.events += [{"ts": $ts, "code": $code}]' "$COUNTER_FILE" > "$tmp" 2>/dev/null || echo '{"events": [{"ts": '"$ts"', "code": '"$code"'}]}' > "$tmp"
    mv "$tmp" "$COUNTER_FILE"
  else
    echo "{\"events\":[{\"ts\":$ts,\"code\":$code}]}" > "$COUNTER_FILE" || true
  fi

  # prune old events outside WINDOW
  now=$(date +%s)
  tmp=$(mktemp)
  jq --argjson now "$now" --argjson w $WINDOW '.events = (.events | map(select((($now) - .ts) < $w)))' "$COUNTER_FILE" > "$tmp" 2>/dev/null || true
  mv "$tmp" "$COUNTER_FILE" 2>/dev/null || true

  count=$(jq '.events|length' "$COUNTER_FILE" 2>/dev/null || echo 0)
  echo "Recorded event. Count in window: $count" >> "$LOG_DIR/ratelimit.log"
  if [ "$count" -ge $THRESHOLD ]; then
    touch "$PAUSE_FLAG"
    echo "Circuit opened at $(date -Is) due to $count events." >> "$LOG_DIR/ratelimit.log"
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
    # usage: rate_guard.sh --record --code 429
    if [ "${2:-}" = "--code" ] && [ -n "${3:-}" ]; then
      record_event "${3}"
    else
      record_event 0
    fi
    ;;
  --check)
    check_circuit
    ;;
  --reset)
    reset
    ;;
  *)
    echo "Usage: $0 [--record --code <http_code> | --check | --reset]"
    exit 2
    ;;
esac
