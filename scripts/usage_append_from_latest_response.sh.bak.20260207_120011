#!/usr/bin/env bash
# usage_append_from_latest_response.sh
# Appends usage stats from a given OpenAI Responses API JSON file to an append-only usage log.
# Idempotency: checks for existing 'source' (response file path) in ledger before appending.
#
# Usage:
#   scripts/usage_append_from_latest_response.sh /path/to/llm_response.json
#
set -euo pipefail

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
HB_DIR="$RUNTIME_DIR/logs/heartbeat"
OUT="$HB_DIR/llm_usage.jsonl"
RATES_FILE="$RUNTIME_DIR/config/model_rates.json"
FAIL_LOG="$HB_DIR/usage_append_failures.log"

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

# Basic existence checks
if not os.path.exists(src):
    print(f"Missing response file: {src}", file=sys.stderr)
    sys.exit(2)

if not os.path.exists(rates_file):
    print(f"Missing rates file: {rates_file}", file=sys.stderr)
    sys.exit(2)

# Idempotency check: exact source-match scan in ledger before any append work.
if os.path.exists(out):
    try:
        needle = f'"source": {json.dumps(src)}'
        with open(out,'r',encoding='utf-8') as fh:
            for line in fh:
                if needle in line:
                    print('usage_already_recorded')
                    sys.exit(0)
    except Exception as e:
        # If ledger unreadable, fail loudly
        print(f"Unable to read ledger for idempotency check: {e}", file=sys.stderr)
        sys.exit(2)

# Load response and rates
try:
    with open(src, "r", encoding="utf-8") as sf:
        obj = json.load(sf)
except Exception as e:
    print(f"Failed to parse response JSON: {e}", file=sys.stderr)
    sys.exit(2)

try:
    with open(rates_file, "r", encoding="utf-8") as rf:
        rates = json.load(rf)
except Exception as e:
    print(f"Failed to parse rates JSON: {e}", file=sys.stderr)
    sys.exit(2)

# Build record
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

# Append (write) with simple error handling
try:
    with open(out, "a", encoding='utf-8') as f:
        f.write(json.dumps(rec) + "\n")
    print("usage_appended")
    sys.exit(0)
except Exception as e:
    # Write failure details for repair
    try:
        with open(os.path.expanduser("$FAIL_LOG"), "a", encoding='utf-8') as lf:
            lf.write(json.dumps({"time": int(datetime.datetime.utcnow().timestamp()), "source": src, "error": str(e)}) + "\n")
    except Exception:
        pass
    print(f"usage_append_failed: {e}", file=sys.stderr)
    sys.exit(3)
PY
