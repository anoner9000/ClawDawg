#!/usr/bin/env bash
set -euo pipefail

DEBUG=0
if [[ "${1:-}" == "--debug" ]]; then DEBUG=1; shift; fi

ROOT="${ROOT:-$HOME/.openclaw/workspace}"
RUNTIME_DIR="${RUNTIME_DIR:-$HOME/.openclaw/runtime}"
CRED_DIR="${CRED_DIR:-$RUNTIME_DIR/credentials}"

TOKEN_FILE="$CRED_DIR/telegram_bot_token"
CHAT_FILE="$CRED_DIR/telegram_chat_id"

if [[ "${DEBUG:-0}" -eq 1 ]]; then
  echo "DEBUG: CRED_DIR=$CRED_DIR" >&2
  echo "DEBUG: TOKEN_FILE=$TOKEN_FILE exists=$([[ -f "$TOKEN_FILE" ]] && echo yes || echo no)" >&2
  echo "DEBUG: CHAT_FILE=$CHAT_FILE exists=$([[ -f "$CHAT_FILE" ]] && echo yes || echo no)" >&2
fi

# Load creds from files if env is not set
if [[ -z "${TELEGRAM_BOT_TOKEN:-}" && -f "$TOKEN_FILE" ]]; then
  TELEGRAM_BOT_TOKEN="$(tr -d '\r\n' < "$TOKEN_FILE")"
  export TELEGRAM_BOT_TOKEN
fi
if [[ -z "${TELEGRAM_CHAT_ID:-}" && -f "$CHAT_FILE" ]]; then
  TELEGRAM_CHAT_ID="$(tr -d '\r\n' < "$CHAT_FILE")"
  export TELEGRAM_CHAT_ID
fi


# Enforced boundary: ONLY executor-comm may send Telegram.
: "${OPENCLAW_ACTOR:=${OPENCLAW_AGENT:-}}"
if [[ "${OPENCLAW_ACTOR:-}" != "executor-comm" ]]; then
  echo "FAIL: telegram_send.sh may only be called by executor-comm (OPENCLAW_ACTOR=executor-comm required)" >&2
  exit 2
fi

TASK_ID="${TASK_ID:-${OPENCLAW_TASK_ID:-}}"
if [[ -z "${TASK_ID:-}" ]]; then
  echo "FAIL: TASK_ID (or OPENCLAW_TASK_ID) is required for telegram sends (receipt linkage)" >&2
  exit 2
fi

# Required inputs:
#   TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, TEXT
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN required}"
: "${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID required}"
: "${TEXT:?TEXT required}"




REC_DIR="$ROOT/tasks/$TASK_ID/receipts"
mkdir -p "$REC_DIR"

OUT_JSON="$REC_DIR/telegram_send_result.json"
RECEIPT_JSON="$REC_DIR/EXECUTION_RECEIPT.json"


echo "== validating bot token via getMe =="
python3 - <<'PY2'
import json, os, urllib.request
token=os.environ["TELEGRAM_BOT_TOKEN"]
url=f"https://api.telegram.org/bot{token}/getMe"
try:
    with urllib.request.urlopen(url, timeout=10) as r:
        body=r.read().decode("utf-8", errors="replace")
        obj=json.loads(body)
        if not obj.get("ok"):
            print("FAIL: invalid bot token:", body)
            raise SystemExit(4)
        print("OK: bot identity:", obj.get("result",{}).get("username"))
except Exception as e:
    print("FAIL: token validation error:", e)
    raise SystemExit(4)
PY2

echo "== sending telegram message =="
python3 - <<'PY' > "$OUT_JSON"
import json, os, sys, urllib.parse, urllib.request
token=os.environ["TELEGRAM_BOT_TOKEN"]
chat=os.environ["TELEGRAM_CHAT_ID"]
text=os.environ["TEXT"]

url=f"https://api.telegram.org/bot{token}/sendMessage"
data=urllib.parse.urlencode({"chat_id": chat, "text": text}).encode("utf-8")
req=urllib.request.Request(url, data=data, method="POST")
try:
    with urllib.request.urlopen(req, timeout=20) as r:
        body=r.read().decode("utf-8", errors="replace")
        print(body)
        sys.exit(0)
except Exception as e:
    print(json.dumps({"ok": False, "error": str(e)}))
    sys.exit(3)
PY

echo "== build execution receipt (v2) =="
python3 - <<'PY'
from __future__ import annotations
import json, os
from pathlib import Path
import hashlib

from ops.governance.receipts import build_execution_receipt_v2, ArtifactRef

root = Path(os.environ.get("ROOT") or (Path.home() / ".openclaw/workspace"))
task_id = os.environ["TASK_ID"]
out_json = root / "tasks" / task_id / "receipts" / "telegram_send_result.json"
receipt_json = root / "tasks" / task_id / "receipts" / "EXECUTION_RECEIPT.json"

b = out_json.read_bytes()
h = hashlib.sha256(b).hexdigest()

receipt = build_execution_receipt_v2(
    task_id=task_id,
    executor="executor-comm",
    intent="Send Telegram message",
    paths_touched=[str(out_json.relative_to(root))],
    notes="Outbound comm is executor-comm only; result artifact recorded.",
    actions=[{
        "kind":"telegram_send",
        "summary":"Called Telegram sendMessage API",
        "evidence":[{"path": str(out_json.relative_to(root)), "sha256": h}],
    }],
    artifacts=[ArtifactRef(path=str(out_json.relative_to(root)), sha256=h)],
    claims=[{
        "claim":"Telegram send attempted; see result artifact for ok=true and message id.",
        "evidence_paths":[str(out_json.relative_to(root))]
    }],
)

receipt_json.write_text(json.dumps(receipt, indent=2, sort_keys=True), encoding="utf-8")
print(f"OK: wrote {receipt_json}")
PY

echo "OK: telegram_send complete; artifacts:"
echo "  $OUT_JSON"
echo "  $RECEIPT_JSON"
