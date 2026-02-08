#!/usr/bin/env bash
# telegram_send_latest_briefing.sh - extracts text from the latest llm_response_*.json and posts to Telegram
# Requires:
#   TELEGRAM_BOT_TOKEN in env or ~/.openclaw/runtime/credentials/telegram_bot_token
#   TELEGRAM_CHAT_ID in env or ~/.openclaw/runtime/credentials/telegram_chat_id
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

# Load runtime config if present
if [ -f "$HOME/.openclaw/workspace/.env" ]; then
  # shellcheck disable=SC1090
  source "$HOME/.openclaw/workspace/.env"
fi

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
LOG_DIR="$RUNTIME_DIR/logs/heartbeat"
CRED_DIR="$RUNTIME_DIR/credentials"
STATE_DIR="$RUNTIME_DIR/var"
mkdir -p "$STATE_DIR"

TOKEN_FILE="$CRED_DIR/telegram_bot_token"
CHAT_FILE="$CRED_DIR/telegram_chat_id"
SENT_MARKER="$STATE_DIR/telegram_last_sent_response.txt"

if [ -z "${TELEGRAM_BOT_TOKEN:-}" ] && [ -f "$TOKEN_FILE" ]; then
  TELEGRAM_BOT_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
  export TELEGRAM_BOT_TOKEN
fi
if [ -z "${TELEGRAM_CHAT_ID:-}" ] && [ -f "$CHAT_FILE" ]; then
  TELEGRAM_CHAT_ID="$(tr -d '\r\n' < "$CHAT_FILE")"
  export TELEGRAM_CHAT_ID
fi

: "${TELEGRAM_BOT_TOKEN:?Missing TELEGRAM_BOT_TOKEN (set env or create $TOKEN_FILE)}"
: "${TELEGRAM_CHAT_ID:?Missing TELEGRAM_CHAT_ID (set env or create $CHAT_FILE)}"

# Fail fast if user left placeholders
if [[ "$TELEGRAM_BOT_TOKEN" == *PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE* ]] || [[ "$TELEGRAM_CHAT_ID" == *PASTE_YOUR_TELEGRAM_CHAT_ID_HERE* ]]; then
  echo "ERROR: Telegram credentials still contain placeholders." >&2
  echo "Update these files with real values:" >&2
  echo "  $TOKEN_FILE" >&2
  echo "  $CHAT_FILE" >&2
  exit 1
fi

# Find latest response file
latest="$(ls -t "$LOG_DIR"/llm_response_*.json 2>/dev/null | head -n 1 || true)"
if [ -z "$latest" ]; then
  echo "ERROR: No llm_response_*.json found in $LOG_DIR" >&2
  exit 1
fi

# Extract response id + deduped text
python_out="$(python3 - <<PY
import json, os
p="$latest"
obj=json.load(open(p))

rid = obj.get("id","")
texts=[]
seen=set()

def walk(x):
    if isinstance(x, dict):
        if x.get("type")=="output_text" and isinstance(x.get("text"), str):
            t=x["text"].strip()
            if t and t not in seen:
                seen.add(t)
                texts.append(t)
        for v in x.values():
            walk(v)
    elif isinstance(x, list):
        for v in x:
            walk(v)

walk(obj.get("output", []))
text="\\n\\n".join(texts).strip()
print(rid)
print("-----")
print(text if text else "[No output_text blocks found]")
PY
)"

resp_id="${python_out%%$'\n'-----*}"
text="${python_out#*$'\n'-----$'\n'}"

if [ -z "$resp_id" ]; then
  echo "ERROR: Could not find response id in $latest" >&2
  exit 1
fi

# Don't double-send the same response
if [ -f "$SENT_MARKER" ] && [ "$(cat "$SENT_MARKER")" = "$resp_id" ]; then
  echo "Already sent response id: $resp_id"
  exit 0
fi

echo "Sending response id: $resp_id"
echo "From file: $latest"

TEXT_FILE="$(mktemp)"
printf '%s' "$text" > "$TEXT_FILE"

python3 - <<PY
import json
import urllib.request

bot_token = """$TELEGRAM_BOT_TOKEN"""
chat_id = """$TELEGRAM_CHAT_ID"""
text = open("$TEXT_FILE", "r", encoding="utf-8", errors="replace").read()

# Telegram message limit ~4096 chars; keep margin.
# Instead of truncating, send in chunks so ledger always makes it through.
MAX = 3800

def send(msg: str):
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": msg}
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode("utf-8", "replace")
        if r.status < 200 or r.status >= 300:
            raise RuntimeError(f"Telegram HTTP {r.status}: {body[:2000]}")

if len(text) <= MAX:
    send(text)
else:
    parts = []
    s = text
    while len(s) > MAX:
        cut = s.rfind("\\n\\n", 0, MAX)
        if cut < 800:  # fallback if no good paragraph break
            cut = s.rfind("\\n", 0, MAX)
        if cut < 800:
            cut = MAX
        parts.append(s[:cut].rstrip())
        s = s[cut:].lstrip()
    if s.strip():
        parts.append(s.strip())

    for i, p in enumerate(parts, 1):
        header = f"[Part {i}/{len(parts)}]\\n" if len(parts) > 1 else ""
        send(header + p)
PY

rm -f "$TEXT_FILE"

# Mark sent
printf '%s' "$resp_id" > "$SENT_MARKER"
echo "Sent briefing successfully."
