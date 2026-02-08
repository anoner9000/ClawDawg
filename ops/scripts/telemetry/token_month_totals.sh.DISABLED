#!/usr/bin/env bash
set -euo pipefail

# token_month_totals.sh
# Sums this month's usage from ~/.openclaw/runtime/logs/heartbeat/llm_usage.jsonl
# Outputs: month, calls, tokens (in/out/total), cost_usd, models breakdown.
# Optional: --daily to include per-day totals.

export TZ="${TZ:-America/Chicago}"

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
USAGE_JSONL="$RUNTIME_DIR/logs/heartbeat/llm_usage.jsonl"

if [[ ! -f "$USAGE_JSONL" ]]; then
  echo "ERROR: usage log not found: $USAGE_JSONL" >&2
  exit 1
fi

MONTH="$(date +%Y-%m)"
DAILY=0
if [[ "${1:-}" == "--daily" ]]; then
  DAILY=1
fi

python3 - "$USAGE_JSONL" "$MONTH" "$DAILY" <<'PY'
import json, sys
path, month, daily_flag = sys.argv[1], sys.argv[2], int(sys.argv[3])

calls = 0
in_tok = 0
out_tok = 0
total_tok = 0
cost = 0.0
models = {}
by_day = {}  # date -> [calls, in, out, total, cost]

def add_day(d, it, ot, tt, c):
  row = by_day.get(d)
  if row is None:
    row = [0,0,0,0,0.0]
    by_day[d] = row
  row[0] += 1
  row[1] += it
  row[2] += ot
  row[3] += tt
  row[4] += c

with open(path, "r", encoding="utf-8") as f:
  for line in f:
    line = line.strip()
    if not line:
      continue
    try:
      r = json.loads(line)
    except Exception:
      continue

    d = r.get("date")
    if not isinstance(d, str) or not d.startswith(month):
      continue

    it = int(r.get("input_tokens") or 0)
    ot = int(r.get("output_tokens") or 0)
    tt = int(r.get("total_tokens") or 0)
    c  = float(r.get("cost_usd") or 0.0)

    calls += 1
    in_tok += it
    out_tok += ot
    total_tok += tt
    cost += c

    m = r.get("model") or "unknown"
    models[m] = models.get(m, 0) + 1

    add_day(d, it, ot, tt, c)

print(f"month={month}")
print(f"calls={calls}")
print(f"input_tokens={in_tok}")
print(f"output_tokens={out_tok}")
print(f"total_tokens={total_tok}")
print(f"cost_usd={cost:.6f}")

if models:
  items = sorted(models.items(), key=lambda x: (-x[1], x[0]))
  print("models=" + ", ".join([f"{m}:{c}" for m,c in items]))

if daily_flag:
  print("\n# daily")
  for d in sorted(by_day.keys()):
    c,in_t,out_t,tot_t,cost_d = by_day[d]
    print(f"{d} calls={c} input={in_t} output={out_t} total={tot_t} cost_usd={cost_d:.6f}")
PY
