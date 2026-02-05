#!/usr/bin/env bash
# token_monthly_rollup.sh
# Read-only monthly rollup from token_daily_snapshots.jsonl
# Usage:
#   scripts/token_monthly_rollup.sh            # defaults to current month (local time)
#   scripts/token_monthly_rollup.sh 2026-02    # explicit YYYY-MM

set -euo pipefail

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
SNAP="$RUNTIME_DIR/logs/token_daily_snapshots.jsonl"
MONTH="${1:-$(date +%Y-%m)}"

export SNAP MONTH

python3 - <<'PY'
import json, os

snap = os.path.expanduser(os.environ["SNAP"])
month = os.environ["MONTH"]

tokens_in = tokens_out = tokens_total = 0
cost = 0.0
days = 0

if os.path.exists(snap):
    for line in open(snap, "r"):
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue

        d = r.get("date", "")
        if not d.startswith(month + "-"):
            continue

        days += 1
        tokens_in    += int(r.get("tokens_input", 0) or 0)
        tokens_out   += int(r.get("tokens_output", 0) or 0)
        tokens_total += int(r.get("tokens_total", 0) or 0)
        cost         += float(r.get("cost_usd", 0) or 0)

out = {
    "month": month,
    "days": days,
    "tokens_input": tokens_in,
    "tokens_output": tokens_out,
    "tokens_total": tokens_total,
    "cost_usd": round(cost, 6),
}
print(json.dumps(out))
PY
