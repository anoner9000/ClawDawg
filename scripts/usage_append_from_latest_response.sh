#!/usr/bin/env bash
# usage_append_from_latest_response.sh
# Appends usage stats from a given OpenAI Responses API JSON file to an append-only usage log.
#
# Usage:
#   scripts/usage_append_from_latest_response.sh /path/to/llm_response.json
#
set -euo pipefail

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
HB_DIR="$RUNTIME_DIR/logs/heartbeat"
OUT="$HB_DIR/llm_usage.jsonl"
RATES_FILE="$RUNTIME_DIR/config/model_rates.json"

if [ "${1:-}" = "" ]; then
  echo "Usage: $0 /path/to/llm_response.json" >&2
  exit 2
fi

SRC="$1"

mkdir -p "$HB_DIR"

python3 - <<PY
import json, os, datetime, sys

src = os.path.expanduser("$SRC")
out = os.path.expanduser("$OUT")
rates_file = os.path.expanduser("$RATES_FILE")

if not os.path.exists(src):
    print(f"Missing response file: {src}", file=sys.stderr)
    sys.exit(2)

if not os.path.exists(rates_file):
    print(f"Missing rates file: {rates_file}", file=sys.stderr)
    sys.exit(2)

obj = json.load(open(src))
rates = json.load(open(rates_file))

ts = obj.get("created_at") or obj.get("created")
if not ts:
    print("No created_at/created in response JSON", file=sys.stderr)
    sys.exit(2)

dt = datetime.datetime.fromtimestamp(ts)
day = dt.date().isoformat()

usage = obj.get("usage", {}) or {}
inp = int(usage.get("input_tokens", 0) or 0)
outp = int(usage.get("output_tokens", 0) or 0)
total = int(usage.get("total_tokens", inp + outp) or (inp + outp))
model = obj.get("model") or "unknown"

rate = rates.get(model) or rates.get("gpt-5-mini") or {}
in_rate = float(rate.get("input_per_1m", 0) or 0)
out_rate = float(rate.get("output_per_1m", 0) or 0)

cost = (inp/1_000_000.0)*in_rate + (outp/1_000_000.0)*out_rate

rec = {
    "created_at": int(ts),
    "date": day,
    "model": model,
    "input_tokens": inp,
    "output_tokens": outp,
    "total_tokens": total,
    "cost_usd": round(cost, 6),
    "source": src
}

with open(out, "a") as f:
    f.write(json.dumps(rec) + "\\n")

print("usage_appended")
PY
