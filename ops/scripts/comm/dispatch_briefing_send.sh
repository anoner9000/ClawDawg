#!/usr/bin/env bash
set -euo pipefail

ROOT="${ROOT:-$HOME/.openclaw/workspace}"
WS="${WS:-$ROOT}"

# Task id is required for receipts. If not provided, we generate one with timestamp.
TASK_ID="${TASK_ID:-${OPENCLAW_TASK_ID:-briefing-send-$(date -u +%Y%m%dT%H%M%SZ)}}"
export TASK_ID

# Identify the actor for enforcement
export OPENCLAW_ACTOR="executor-comm"

# Where the existing module script lives (as referenced in your repo)
MOD_SCRIPT="$WS/modules/briefings/scripts/telegram_send_latest_briefing.sh"

if [[ ! -x "$MOD_SCRIPT" ]]; then
  echo "FAIL: module script not found or not executable: $MOD_SCRIPT" >&2
  exit 2
fi

# The module script may already send Telegram today.
# Best-quality migration: run it in a mode that prints text only if supported.
# If not supported, we fall back to capturing its output as TEXT, and we will
# later refactor the module in a dedicated PR.
echo "== build TEXT from latest briefing =="
TEXT="$("$MOD_SCRIPT" --print-text)"

# Guardrails: refuse to send empty messages
if [[ -z "${TEXT// }" ]]; then
  echo "FAIL: briefing TEXT was empty. Migration requires module script to support print-text mode." >&2
  echo "HINT: update $MOD_SCRIPT to support --print-text and not send directly." >&2
  exit 3
fi

# Required env for telegram_send.sh
export TEXT

echo "== dispatch through enforced executor-comm telegram_send.sh =="
"$ROOT/ops/scripts/comm/telegram_send.sh"

echo "OK: dispatched briefing send under TASK_ID=$TASK_ID"
