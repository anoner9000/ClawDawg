#!/usr/bin/env bash
# heartbeat_aggregator.sh - hardened aggregator for LLM queue
# Usage: ./heartbeat_aggregator.sh [--dry-run]

set -euo pipefail

# Runtime/log paths (initialized early so LOG is always defined)
RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
LOG_DIR="$RUNTIME_DIR/logs/heartbeat"
mkdir -p "$LOG_DIR" 2>/dev/null || true
STAMP="$(date -u +'%Y-%m-%dT%H:%M:%SZ')"
LOG="$LOG_DIR/heartbeat_aggregator_${STAMP}.log"

# Probe log writability without triggering noisy redirect errors
if ! touch "$LOG" 2>/dev/null; then
  LOG="/tmp/openclaw_heartbeat_aggregator_${STAMP}.log"
  mkdir -p /tmp 2>/dev/null || true
  touch "$LOG"
  echo "WARN: using fallback log path: $LOG" >&2
fi

# Resolve script directory (cron-safe)
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Load env if present
if [ -f "$HOME/.openclaw/workspace/.env" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.openclaw/workspace/.env"
fi

DRY_RUN=false
if [ "${1:-}" = "--dry-run" ]; then
  DRY_RUN=true
fi

# Runtime paths
QUEUE_DIR="$RUNTIME_DIR/queues"
QUEUE_FILE="$QUEUE_DIR/llm_queue.jsonl"

mkdir -p "$QUEUE_DIR" "$LOG_DIR"
touch "$QUEUE_FILE"

# Load OpenAI API key from runtime secrets
SECRET_KEY_FILE="$RUNTIME_DIR/credentials/openai_api_key"
if [ -z "${OPENAI_API_KEY:-}" ] && [ -f "$SECRET_KEY_FILE" ]; then
  OPENAI_API_KEY="$(tr -d '\r\n' < "$SECRET_KEY_FILE")"
  export OPENAI_API_KEY
fi
: "${OPENAI_API_KEY:?OPENAI_API_KEY not set}"

# Rate guard
if "$SCRIPT_DIR/rate_guard.sh" --check >/dev/null 2>&1; then
  echo "Rate guard: circuit closed" >> "$LOG"
else
  echo "Rate guard: circuit open - aborting run" | tee -a "$LOG"
  exit 0
fi

# Load queue
mapfile -t entries < "$QUEUE_FILE"
if [ "${#entries[@]}" -eq 0 ]; then
  echo "Queue empty. Nothing to do." >> "$LOG"
  exit 0
fi

# ------------------------------------------------------------------
# CONTEXT INJECTION: Gmail cleanup last run (quarantine/trash counts)
# ------------------------------------------------------------------
GMAIL_SUMMARY_FILE="$RUNTIME_DIR/logs/gmail_cleanup_last_summary.json"
GMAIL_CONTEXT="$(
python3 - <<PY
import json, os
path = os.path.expanduser("$GMAIL_SUMMARY_FILE")
if not os.path.exists(path):
    print("")  # no context if not present
    raise SystemExit(0)

try:
    obj = json.load(open(path, "r", encoding="utf-8"))
except Exception:
    print("")
    raise SystemExit(0)

q = obj.get("quarantined_count", 0)
t = obj.get("trashed_count", 0)
ts = obj.get("ts_utc") or obj.get("date") or ""
line = f"Gmail cleanup (last run): quarantined {q}, trashed {t}"
if ts:
    line += f" | {ts}"
print("---- CONTEXT ----\\n" + line + "\\n")
PY
)"
if [ -n "$GMAIL_CONTEXT" ]; then
  echo "Included Gmail cleanup context from: $GMAIL_SUMMARY_FILE" >> "$LOG"
else
  echo "No Gmail cleanup context (missing/unreadable): $GMAIL_SUMMARY_FILE" >> "$LOG"
fi

# Batch prompts
batch_prompt=""
ids=()

# Prepend context so every briefing job can reference it
if [ -n "$GMAIL_CONTEXT" ]; then
  batch_prompt+="$GMAIL_CONTEXT"$'\n'
fi

for e in "${entries[@]}"; do
  id=$(printf '%s' "$e" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())["id"])')
  prompt=$(printf '%s' "$e" | python3 -c 'import sys,json; print(json.loads(sys.stdin.read())["prompt"])')
  ids+=("$id")
  batch_prompt+=$'\n---- JOB: '"$id"$' ----\n'"$prompt"$'\n'
done

# Cost estimate (rough)
chars=$(printf '%s' "$batch_prompt" | wc -c)
est_tokens=$(( (chars + 3) / 4 ))
resp_budget=250
input_cost_per_token=0.25e-6
output_cost_per_token=2.0e-6
est_cost=$(awk -v i=$est_tokens -v r=$resp_budget -v ip=$input_cost_per_token -v op=$output_cost_per_token \
  'BEGIN{print (i*ip + r*op)}')

printf \
  "Batched jobs: %s\nEstimated chars: %s\nEstimated tokens: %s\nEstimated response tokens: %s\nEstimated cost (USD): %.6f\n" \
  "${#ids[@]}" "$chars" "$est_tokens" "$resp_budget" "$est_cost" >> "$LOG"

# Hard cost cap
if awk "BEGIN{exit !($est_cost > 0.5)}"; then
  echo "Estimated cost > $0.50; aborting." >> "$LOG"
  exit 0
fi

if $DRY_RUN; then
  echo "DRY RUN enabled; exiting." >> "$LOG"
  exit 0
fi

# ------------------------------------------------------------------
# HARDENING: Build canonical instructions (model-agnostic memory)
# ------------------------------------------------------------------
INSTR_FILE="$LOG_DIR/instructions_$(date -Iseconds).txt"

python3 - <<'PY' > "$INSTR_FILE"
import os

files = [
  os.path.expanduser("~/.openclaw/workspace/AGENTS.md"),
  os.path.expanduser("~/.openclaw/workspace/Atlas/Deiphobe.md"),
  os.path.expanduser("~/.openclaw/workspace/playbooks/ADVISOR_MODE_PROTOCOL.md"),
  os.path.expanduser("~/.openclaw/workspace/IDENTITY.md"),
  os.path.expanduser("~/.openclaw/workspace/SOUL.md"),
]

parts = []
missing = []

for p in files:
  if os.path.exists(p):
    with open(p, "r", encoding="utf-8", errors="replace") as f:
      parts.append(f"\n\n===== FILE: {p} =====\n{f.read().strip()}\n")
  else:
    missing.append(p)

header = (
  "SYSTEM BOOTSTRAP (CANONICAL)\n"
  "These instructions are authoritative and override model defaults.\n"
  "If conflicts exist, follow AGENTS.md and ADVISOR_MODE_PROTOCOL.md first.\n"
)

if missing:
  parts.append("\n\n[WARN] Missing files:\n" + "\n".join(missing))

print(header + "".join(parts))
PY

instr_bytes=$(wc -c < "$INSTR_FILE")
echo "Instructions bytes: $instr_bytes" >> "$LOG"
if [ "$instr_bytes" -gt 60000 ]; then
  echo "ERROR: instructions too large (>60KB)" | tee -a "$LOG"
  exit 1
fi

# Build request JSON
REQ_FILE="$LOG_DIR/request_$(date -Iseconds).json"
python3 - <<PY > "$REQ_FILE"
import json

with open("$INSTR_FILE","r",encoding="utf-8") as f:
    instructions = f.read()

payload = {
  "model": "gpt-5-mini",
  "instructions": instructions,
  "input": """$batch_prompt"""
}

print(json.dumps(payload))
PY

# Call OpenAI
RESP_FILE="$LOG_DIR/llm_response_$(date -Iseconds).json"
HTTP_CODE="$(curl -sS -o "$RESP_FILE" -w "%{http_code}" \
  -H "Authorization: Bearer $OPENAI_API_KEY" \
  -H "Content-Type: application/json" \
  https://api.openai.com/v1/responses \
  --data @"$REQ_FILE" || true)"

echo "HTTP status: $HTTP_CODE" >> "$LOG"
echo "Response saved: $RESP_FILE" >> "$LOG"

if ! [[ "$HTTP_CODE" =~ ^2 ]]; then
  if [ "$HTTP_CODE" = "429" ]; then
    "$SCRIPT_DIR/rate_guard.sh" --record --code 429 >/dev/null 2>&1 || true
  fi
  echo "ERROR: Non-2xx response. Queue NOT cleared." | tee -a "$LOG"
  python3 - <<PY >> "$LOG"
print(open("$RESP_FILE","r",errors="replace").read()[:2000])
PY
  exit 1
fi

# Append usage if available
if [ -x "$SCRIPT_DIR/usage_append_from_latest_response.sh" ]; then
  APPEND_ERR_FILE="$(mktemp)"
  echo "runner: uid=$(id -u) gid=$(id -g) user=$(id -un) group=$(id -gn) umask=$(umask) pwd=$(pwd)"
  if "$SCRIPT_DIR/usage_append_from_latest_response.sh" "$RESP_FILE" 2>"$APPEND_ERR_FILE"; then
    :
  else
    APPEND_RC=$?
    echo "!!! WARNING: usage append failed (exit $APPEND_RC). API delivery succeeded, accounting incomplete." | tee -a "$LOG"
    sed 's/^/usage_append_stderr: /' "$APPEND_ERR_FILE" >> "$LOG"
    {
      echo "response_path=$RESP_FILE"
      sed 's/^/stderr: /' "$APPEND_ERR_FILE"
      echo "---"
    } >> "$LOG_DIR/usage_append_failures.log"
    FLAG_TS="$(date +%s)"
    touch "$LOG_DIR/accounting_incomplete_${FLAG_TS}.flag"
    echo "Repair command: $SCRIPT_DIR/usage_append_from_latest_response.sh $RESP_FILE" >> "$LOG"
  fi
  rm -f "$APPEND_ERR_FILE"
fi

# Mark delivered
PROCESSED="$LOG_DIR/processed_$(date -Iseconds).jsonl"
NOW=$(date -Iseconds)
for id in "${ids[@]}"; do
  printf '{"id":"%s","status":"delivered","delivered_at":"%s","response_path":"%s"}\n' \
    "$id" "$NOW" "$RESP_FILE" >> "$PROCESSED"
done

# Clear queue ONLY after success
> "$QUEUE_FILE"

echo "Run complete. Log: $LOG" | tee -a "$LOG"
exit 0
