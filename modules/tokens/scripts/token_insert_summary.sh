#!/usr/bin/env bash
# token_insert_summary.sh
# Prepend OpenAI usage summary (yesterday + 7-day avg + month-to-date) to today's morning briefing.
# Rules:
# - Prepend only (no overwrite of existing content)
# - No secrets
# - No network calls
# - Idempotent via marker

set -euo pipefail

if [ -f "$HOME/.openclaw/workspace/.env" ]; then
  source "$HOME/.openclaw/workspace/.env"
fi

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
SNAP="$RUNTIME_DIR/logs/token_daily_snapshots.jsonl"
BRIEFING="$RUNTIME_DIR/briefings/morning_8am_filled_$(date +%F).md"

# If today's briefing doesn't exist, bail quietly (no mutation elsewhere).
if [ ! -f "$BRIEFING" ]; then
  echo "no_briefing"
  exit 0
fi

MARKER="<!-- OPENCLAW_LEDGER_SUMMARY v1 -->"

# Idempotence: if marker already present near top, do nothing.
if head -n 8 "$BRIEFING" | grep -qF "$MARKER"; then
  echo "already_inserted"
  exit 0
fi

export SNAP BRIEFING MARKER

SUMMARY_TEXT="$(python3 - <<'PY'
import json, os, datetime

snap = os.path.expanduser(os.environ["SNAP"])
marker = os.environ["MARKER"]

today = datetime.date.today()
yesterday = (today - datetime.timedelta(days=1)).isoformat()
month_prefix = yesterday[:7]  # YYYY-MM

rows = []
if os.path.exists(snap):
    with open(snap, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except Exception:
                continue

bydate = {r.get("date"): r for r in rows if r.get("date")}

# Yesterday
yrow = bydate.get(yesterday, {}) or {}
y_in   = int(yrow.get("tokens_input", 0) or 0)
y_out  = int(yrow.get("tokens_output", 0) or 0)
y_tot  = int(yrow.get("tokens_total", 0) or 0)
y_cost = float(yrow.get("cost_usd", 0) or 0)
y_model = (yrow.get("model") or "unknown")

# 7-day avg (excluding today, using available days)
vals_tokens = []
vals_cost = []
for i in range(1, 8):
    d = (today - datetime.timedelta(days=i)).isoformat()
    r = bydate.get(d)
    if not r:
        continue
    vals_tokens.append(int(r.get("tokens_total", 0) or 0))
    vals_cost.append(float(r.get("cost_usd", 0) or 0))

avg_tokens = int(sum(vals_tokens) / len(vals_tokens)) if vals_tokens else 0
avg_cost = (sum(vals_cost) / len(vals_cost)) if vals_cost else 0.0

# Month-to-date totals (from 1st through yesterday)
mtd_in = mtd_out = mtd_tot = 0
mtd_cost = 0.0
mtd_days = 0
for r in rows:
    d = r.get("date", "")
    if not d.startswith(month_prefix + "-"):
        continue
    if d > yesterday:
        continue
    mtd_days += 1
    mtd_in   += int(r.get("tokens_input", 0) or 0)
    mtd_out  += int(r.get("tokens_output", 0) or 0)
    mtd_tot  += int(r.get("tokens_total", 0) or 0)
    mtd_cost += float(r.get("cost_usd", 0) or 0)

lines = []
lines.append(marker)
lines.append("## OpenAI usage summary")
lines.append(f"- **Yesterday ({yesterday})** — input: **{y_in:,}**, output: **{y_out:,}**, total: **{y_tot:,}** tokens • spend: **${y_cost:0.6f}** • model: **{y_model}**")
lines.append(f"- **7-day avg** — **{avg_tokens:,}** tokens/day • **${avg_cost:0.6f}** /day (based on {len(vals_tokens)} day(s) in ledger)")
lines.append(f"- **Month-to-date ({month_prefix})** — input: **{mtd_in:,}**, output: **{mtd_out:,}**, total: **{mtd_tot:,}** tokens • spend: **${mtd_cost:0.6f}** (days counted: {mtd_days})")
print("\\n".join(lines))
PY
)"

tmp="$(mktemp)"
{
   printf "%b\n\n" "$SUMMARY_TEXT"
  cat "$BRIEFING"
  
} > "$tmp"
mv "$tmp" "$BRIEFING"

echo "inserted"
