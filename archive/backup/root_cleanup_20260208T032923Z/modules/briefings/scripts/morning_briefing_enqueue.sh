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

# Gmail cleanup summary (written by gmail_nightly_cleanup.sh)
GMAIL_SUMMARY_JSON="$RUNTIME_DIR/logs/gmail_cleanup_last_summary.json"

# Ledger accounting report (written by ledger_render_report_accounting.py)
LEDGER_REPORT_TXT="$RUNTIME_DIR/logs/heartbeat/ledger_report_accounting_latest.txt"

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

# Build a REQUIRED Gmail cleanup line from last summary (or a clear fallback)
GMAIL_LINE="$(python3 - <<PY_GMAIL
import json, os
from datetime import datetime

p = os.path.expanduser("$GMAIL_SUMMARY_JSON")
if not os.path.exists(p):
    print("Gmail cleanup (last run): no data yet.")
    raise SystemExit(0)

try:
    obj = json.load(open(p, "r", encoding="utf-8"))
except Exception:
    print("Gmail cleanup (last run): summary unreadable.")
    raise SystemExit(0)

q = obj.get("quarantined_count", 0)
t = obj.get("trashed_count", 0)
ts = (obj.get("ts_utc") or "").strip()

def ordinal(n: int) -> str:
    if 11 <= (n % 100) <= 13:
        return f"{n}th"
    last = n % 10
    if last == 1:
        return f"{n}st"
    if last == 2:
        return f"{n}nd"
    if last == 3:
        return f"{n}rd"
    return f"{n}th"

pretty = ""
if ts:
    try:
        # parse ISO; treat Z as UTC offset
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        # try to convert to America/Chicago for human-friendly time
        try:
            from zoneinfo import ZoneInfo
            dt = dt.astimezone(ZoneInfo("America/Chicago"))
            tz_label = " CT"
        except Exception:
            tz_label = ""

        month = dt.strftime("%B")
        day = ordinal(dt.day)
        year = dt.year
        # 5:09AM style (no space)
        try:
            tstr = dt.strftime("%-I:%M%p")
        except Exception:
            tstr = dt.strftime("%I:%M%p").lstrip("0")

        pretty = f"{month} {day}, {year} ({tstr}{tz_label})"
    except Exception:
        pretty = ts

if pretty:
    print(f"Gmail cleanup (last run {pretty}): quarantined {q}, trashed {t}.")
else:
    print(f"Gmail cleanup (last run): quarantined {q}, trashed {t}.")
PY_GMAIL
)"

# Append hard requirement so it shows up every day
PROMPT="$PROMPT

---
REQUIRED: Include this exact line in the briefing (verbatim):
$GMAIL_LINE
---"

# Build a REQUIRED Ledger section from latest accounting report (or fallback)
LEDGER_BLOCK="$(python3 - <<PY_LEDGER
import os

p = os.path.expanduser("$LEDGER_REPORT_TXT")
if not os.path.exists(p):
    print("OPENCLAW HEARTBEAT LEDGER: report missing.")
    raise SystemExit(0)

try:
    txt = open(p, "r", encoding="utf-8", errors="replace").read()
except Exception:
    print("OPENCLAW HEARTBEAT LEDGER: report unreadable.")
    raise SystemExit(0)

rows = txt.splitlines()
cut = None
for i, line in enumerate(rows):
    if line.strip().startswith("ENTRIES (audit fields)"):
        cut = i
        break

if cut is not None:
    rows = rows[:cut]

while rows and not rows[-1].strip():
    rows.pop()

print("\n".join(rows).rstrip())
PY_LEDGER
)"
PROMPT="$PROMPT

---
REQUIRED: Include this ledger section in the briefing (verbatim):
$LEDGER_BLOCK
---"

# Guard: don’t enqueue duplicates for same day (by id)
if grep -q "\"id\":\"$JOB_ID\"" "$QUEUE_FILE" 2>/dev/null; then
  echo "$STAMP already queued: $JOB_ID" >> "$LOG_DIR/morning_enqueue.log"
  exit 0
fi

# Append JSONL job
python3 - <<PY >> "$QUEUE_FILE"
import json
job = {
  "id": "$JOB_ID",
  "prompt": """$PROMPT"""
}
print(json.dumps(job, ensure_ascii=False))
PY

echo "$STAMP queued: $JOB_ID -> $QUEUE_FILE" >> "$LOG_DIR/morning_enqueue.log"
