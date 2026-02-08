#!/usr/bin/env bash
set -euo pipefail
export TZ="${TZ:-America/Chicago}"

# token_today_totals.sh
# Sums today's usage from ~/.openclaw/runtime/logs/heartbeat/llm_usage.jsonl
# Outputs: date, calls, tokens (in/out/total), cost_usd

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
USAGE_JSONL="$RUNTIME_DIR/logs/heartbeat/llm_usage.jsonl"

if [[ ! -f "$USAGE_JSONL" ]]; then
  echo "ERROR: usage log not found: $USAGE_JSONL" >&2
  exit 1
fi

# Use local date to match your "date" field usage (America/Chicago in your setup).
TODAY="$(date +%F)"

python3 - "$USAGE_JSONL" "$TODAY" <<'PY'
import json, sys
path, today = sys.argv[1], sys.argv[2]

calls = 0
in_tok = 0
out_tok = 0
total_tok = 0
cost = 0.0
models = {}

with open(path, "r", encoding="utf-8") as f:
  for line in f:
    line = line.strip()
    if not line:
      continue
    try:
      r = json.loads(line)
    except Exception:
      continue
    if r.get("date") != today:
      continue
    calls += 1
    in_tok += int(r.get("input_tokens") or 0)
    out_tok += int(r.get("output_tokens") or 0)
    total_tok += int(r.get("total_tokens") or 0)
    cost += float(r.get("cost_usd") or 0.0)
    m = r.get("model") or "unknown"
    models[m] = models.get(m, 0) + 1

# Print a stable, greppable summary
print(f"date={today}")
print(f"calls={calls}")
print(f"input_tokens={in_tok}")
print(f"output_tokens={out_tok}")
print(f"total_tokens={total_tok}")
print(f"cost_usd={cost:.6f}")
if models:
  # sort by descending count then name
  items = sorted(models.items(), key=lambda x: (-x[1], x[0]))
  print("models=" + ", ".join([f"{m}:{c}" for m,c in items]))
PY
