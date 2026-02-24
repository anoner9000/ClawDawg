#!/usr/bin/env bash
# Producer for latest briefing text (canonical).
# Default behavior is SAFE: print text only (no send) unless --send is explicitly requested.
set -euo pipefail

MODE="print"
DEBUG=0
if [[ "${1:-}" == "--debug" ]]; then
  DEBUG=1
  shift
fi
if [[ "${1:-}" == "--send" ]]; then
  MODE="send"
  shift
elif [[ "${1:-}" == "--print-text" ]]; then
  MODE="print"
  shift
elif [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage:
  telegram_send_latest_briefing.sh --debug --print-text
  telegram_send_latest_briefing.sh --print-text
  telegram_send_latest_briefing.sh --send

Modes:
  --print-text   Print the latest briefing message to stdout (default safe mode).
  --send         Send via ops/scripts/comm/telegram_send.sh (executor-comm only).

Notes:
  --send requires:
    OPENCLAW_ACTOR=executor-comm
    TASK_ID (or OPENCLAW_TASK_ID)
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID available (env or runtime creds)
EOF
  exit 0
fi

ROOT="${ROOT:-$HOME/.openclaw/workspace}"
RUNTIME_DIR="${RUNTIME_DIR:-$HOME/.openclaw/runtime}"
CRED_DIR="${CRED_DIR:-$RUNTIME_DIR/credentials}"
LOG_DIR="$RUNTIME_DIR/logs/heartbeat"

TOKEN_FILE="$CRED_DIR/telegram_bot_token"
CHAT_FILE="$CRED_DIR/telegram_chat_id"

# Load runtime config if present (optional)
if [[ -f "$ROOT/.env" ]]; then
  # shellcheck disable=SC1090
  source "$ROOT/.env"
fi

# Load creds if env not set
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" && -f "$TOKEN_FILE" ]]; then
  TELEGRAM_BOT_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
  export TELEGRAM_BOT_TOKEN
fi
if [[ -z "${TELEGRAM_CHAT_ID:-}" && -f "$CHAT_FILE" ]]; then
  TELEGRAM_CHAT_ID="$(tr -d '\r\n' < "$CHAT_FILE")"
  export TELEGRAM_CHAT_ID
fi

: "${TELEGRAM_BOT_TOKEN:?Missing TELEGRAM_BOT_TOKEN (set env or create $TOKEN_FILE)}"
: "${TELEGRAM_CHAT_ID:?Missing TELEGRAM_CHAT_ID (set env or create $CHAT_FILE)}"

# Fail fast if placeholders remain
if [[ "$TELEGRAM_BOT_TOKEN" == *PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE* ]] || [[ "$TELEGRAM_CHAT_ID" == *PASTE_YOUR_TELEGRAM_CHAT_ID_HERE* ]]; then
  echo "Update these files with real values:" >&2
  echo "  $TOKEN_FILE" >&2
  echo "  $CHAT_FILE" >&2
  exit 1
fi

# Find latest response file
latest="$(ls -t "$LOG_DIR"/llm_response_*.json 2>/dev/null | head -n 1 || true)"
if [[ -z "$latest" ]]; then
  echo "ERROR: No llm_response_*.json found in $LOG_DIR" >&2
  exit 1
fi

# Extract deduped output_text blocks from the response JSON
TEXT="$(python3 - <<PY
import json
p="$latest"
obj=json.load(open(p, "r", encoding="utf-8"))

texts=[]
seen=set()

def add(t):
    if not isinstance(t, str):
        return
    t=t.strip()
    if not t:
        return
    if t in seen:
        return
    seen.add(t)
    texts.append(t)

def walk_output(x):
    if isinstance(x, dict):
        c = x.get("content")
        if isinstance(c, list):
            for part in c:
                if isinstance(part, dict):
                    if "text" in part:
                        add(part.get("text"))
                    for v in part.values():
                        walk_output(v)
        if x.get("type") in ("output_text","text") and "text" in x:
            add(x.get("text"))
        for v in x.values():
            walk_output(v)
    elif isinstance(x, list):
        for v in x:
            walk_output(v)

walk_output(obj.get("output", []))
add(obj.get("output_text"))
if isinstance(obj.get("response"), dict):
    add(obj["response"].get("output_text"))
choices = obj.get("choices")
if isinstance(choices, list):
    for ch in choices:
        if isinstance(ch, dict):
            msg = ch.get("message")
            if isinstance(msg, dict):
                add(msg.get("content"))
print("\\n\\n".join(texts).strip())
PY
)"

if [[ -z "${TEXT// }" ]]; then
  echo "ERROR: extracted TEXT was empty from $latest" >&2
  if [[ "${DEBUG:-0}" -eq 1 ]]; then
    echo "DEBUG: showing top-level keys and sample structure:" >&2
    python3 - <<PY
import json
p="$latest"
obj=json.load(open(p,"r",encoding="utf-8"))
print("keys:", sorted(list(obj.keys())))
for k in ("output","response","output_text","choices"):
    v=obj.get(k)
    print(f"{k}: type={type(v).__name__}")
    if isinstance(v, list):
      print(f"{k}: len={len(v)}; first_type={type(v[0]).__name__ if v else 'n/a'}")
    if isinstance(v, dict):
      print(f"{k}: keys={sorted(list(v.keys()))[:40]}")
PY
  fi
  exit 2
fi

if [[ "$MODE" == "print" ]]; then
  printf "%s\n" "$TEXT"
  exit 0
fi

# MODE=send: enforce boundary + dispatch through executor-comm wrapper
: "${OPENCLAW_ACTOR:=${OPENCLAW_AGENT:-}}"
if [[ "${OPENCLAW_ACTOR:-}" != "executor-comm" ]]; then
  echo "FAIL: --send requires OPENCLAW_ACTOR=executor-comm" >&2
  exit 3
fi

TASK_ID="${TASK_ID:-${OPENCLAW_TASK_ID:-}}"
if [[ -z "${TASK_ID:-}" ]]; then
  echo "FAIL: --send requires TASK_ID (or OPENCLAW_TASK_ID) for receipts" >&2
  exit 4
fi
export TASK_ID
export TEXT

exec "$ROOT/ops/scripts/comm/telegram_send.sh"
