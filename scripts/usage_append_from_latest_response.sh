#!/usr/bin/env bash
set -euo pipefail

RESP="${1:-}"
if [[ -z "$RESP" || ! -f "$RESP" ]]; then
  echo "Usage: $0 /path/to/llm_response_*.json" >&2
  exit 2
fi

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
OUT_JSONL="$RUNTIME_DIR/logs/heartbeat/llm_usage.jsonl"
RATES_FILE="$RUNTIME_DIR/config.known-good/model_rates.json"

mkdir -p "$(dirname "$OUT_JSONL")"
touch "$OUT_JSONL"

python3 - "$RESP" "$OUT_JSONL" "$RATES_FILE" <<'PY'
import json, sys, os, time, datetime

resp_path, out_jsonl, rates_path = sys.argv[1], sys.argv[2], sys.argv[3]
obj = json.load(open(resp_path, "r", encoding="utf-8"))

resp_id = obj.get("id") or os.path.abspath(resp_path)

# Idempotency: skip if already recorded (by response_id or by source path)
needle_src = f'"source":"{os.path.abspath(resp_path)}"'
needle_id  = f'"response_id":"{resp_id}"'
try:
    with open(out_jsonl, "r", encoding="utf-8", errors="ignore") as f:
        data = f.read()
        if needle_src in data or needle_id in data:
            print("usage_already_recorded")
            raise SystemExit(0)
except FileNotFoundError:
    pass

usage = obj.get("usage") or {}
it = usage.get("input_tokens")
ot = usage.get("output_tokens")
tt = usage.get("total_tokens")

if it is None or ot is None:
    print("ERROR: usage missing input_tokens/output_tokens", file=sys.stderr)
    raise SystemExit(3)

it = int(it); ot = int(ot)
if tt is None:
    tt = it + ot
else:
    tt = int(tt)

model = obj.get("model") or "unknown"

created_at = obj.get("created_at")
if not isinstance(created_at, int):
    created_at = int(time.time())

date_str = datetime.datetime.fromtimestamp(created_at).strftime("%Y-%m-%d")

# ---- cost calc using pinned rates file (your file uses per-1m keys) ----
cost = None
rate_res = "missing"
try:
    rates = json.load(open(rates_path, "r", encoding="utf-8"))
    r = rates.get(model) if isinstance(rates, dict) else None
    if isinstance(r, dict):
        in1m = r.get("input_per_1m")
        out1m = r.get("output_per_1m")
        if in1m is not None and out1m is not None:
            cost = (it/1_000_000.0)*float(in1m) + (ot/1_000_000.0)*float(out1m)
            cost = round(cost, 6)
            rate_res = "exact"
except Exception:
    pass

rec = {
    "created_at": created_at,
    "date": date_str,
    "model": model,
    "input_tokens": it,
    "output_tokens": ot,
    "total_tokens": tt,
    "cost_usd": cost,
    "rate_res": rate_res,
    "response_id": resp_id,
    "source": os.path.abspath(resp_path),
}

with open(out_jsonl, "a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")

print("usage_appended")
PY
