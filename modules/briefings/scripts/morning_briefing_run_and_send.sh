#!/usr/bin/env bash
# telegram_send_latest_briefing.sh
# Sends the latest llm_response_*.json briefing to Telegram (robust, quoting-safe).
set -euo pipefail

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
LOG_DIR="$RUNTIME_DIR/logs/heartbeat"
CRED_DIR="$RUNTIME_DIR/credentials"

TOKEN_FILE="$CRED_DIR/telegram_bot_token"
CHATID_FILE="$CRED_DIR/telegram_chat_id"

python3 - <<PY
import os, sys, json, glob, urllib.request, urllib.parse

runtime_dir = os.path.expanduser("$RUNTIME_DIR")
log_dir = os.path.expanduser("$LOG_DIR")
token_file = os.path.expanduser("$TOKEN_FILE")
chatid_file = os.path.expanduser("$CHATID_FILE")

def die(msg, code=1):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)

if not os.path.exists(token_file):
    die(f"Missing {token_file} (put bot token on ONE line)")
if not os.path.exists(chatid_file):
    die(f"Missing {chatid_file} (put chat id on ONE line)")

bot_token = open(token_file, "r", encoding="utf-8", errors="replace").read().strip()
chat_id = open(chatid_file, "r", encoding="utf-8", errors="replace").read().strip()

if not bot_token or bot_token == "PASTE_YOUR_TELEGRAM_BOT_TOKEN_HERE":
    die("telegram_bot_token is empty/placeholder")
if not chat_id or chat_id == "PASTE_YOUR_TELEGRAM_CHAT_ID_HERE":
    die("telegram_chat_id is empty/placeholder")

files = sorted(glob.glob(os.path.join(log_dir, "llm_response_*.json")), key=os.path.getmtime, reverse=True)
if not files:
    die(f"No llm_response_*.json found in {log_dir}")

latest = files[0]
print(f"From file: {latest}")

try:
    obj = json.load(open(latest, "r", encoding="utf-8"))
except Exception as e:
    die(f"Could not parse JSON: {e}", 2)

resp_id = obj.get("id", "(no id)")
print(f"Sending response id: {resp_id}")

# Extract response text robustly
for key in ("output_text", "text"):
    v = obj.get(key)
    if isinstance(v, str) and v.strip():
        text = v.strip()
        break
else:
    texts = []
    def walk(x):
        if isinstance(x, dict):
            if x.get("type") == "output_text" and isinstance(x.get("text"), str):
                t = x["text"].strip()
                if t:
                    texts.append(t)
            if x.get("type") == "message" and isinstance(x.get("content"), list):
                for item in x["content"]:
                    walk(item)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)

    walk(obj.get("output", []))

    # de-dup preserving order
    seen = set()
    uniq = []
    for t in texts:
        if t not in seen:
            seen.add(t)
            uniq.append(t)

    text = "\n\n".join(uniq).strip()
    if not text:
        die("No output text found in response JSON", 3)

# Telegram message limit ~4096 chars; keep margin
if len(text) > 3800:
    text = text[:3800] + "\n\n[truncated]"

url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
payload = {"chat_id": chat_id, "text": text}
data = json.dumps(payload).encode("utf-8")

req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        body = r.read().decode("utf-8", "replace")
        if r.status < 200 or r.status >= 300:
            die(f"Telegram HTTP {r.status}: {body[:2000]}", 4)
except Exception as e:
    die(f"Telegram send failed: {e}", 4)

print(f"Sent briefing from: {latest}")
PY
