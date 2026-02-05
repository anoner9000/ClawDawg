#!/usr/bin/env bash
# token_daily_snapshot.sh
# Sums yesterday's usage from the append-only heartbeat usage log and writes ONE ledger line per day.

set -euo pipefail

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
HB_DIR="$RUNTIME_DIR/logs/heartbeat"
USAGE_LOG="$HB_DIR/llm_usage.jsonl"
LEDGER="$RUNTIME_DIR/logs/token_daily_snapshots.jsonl"

mkdir -p "$(dirname "$LEDGER")"

python3 - <<'PY'
import json, os, datetime

runtime = os.path.expanduser("~/.openclaw/runtime")
usage_log = os.path.join(runtime, "logs/heartbeat/llm_usage.jsonl")
ledger = os.path.join(runtime, "logs/token_daily_snapshots.jsonl")

if not os.path.exists(usage_log):
    raise SystemExit(f"Missing usage log: {usage_log}")

yesterday = (datetime.date.today() - datetime.timedelta(days=1)).isoformat()

tokens_in = 0
tokens_out = 0
tokens_total = 0
cost = 0.0
model_counts = {}

with open(usage_log, "r") as f:
    for line in f:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except Exception:
            continue

        if rec.get("date") != yesterday:
            continue

        inp = int(rec.get("input_tokens", 0) or 0)
        outp = int(rec.get("output_tokens", 0) or 0)
        tot = int(rec.get("total_tokens", inp + outp) or (inp + outp))
        c = float(rec.get("cost_usd", 0) or 0)
        m = rec.get("model") or "unknown"

        tokens_in += inp
        tokens_out += outp
        tokens_total += tot
        cost += c
        model_counts[m] = model_counts.get(m, 0) + 1

model = "unknown"
if model_counts:
    model = max(model_counts.items(), key=lambda kv: kv[1])[0]

entry = {
    "date": yesterday,
    "model": model,
    "tokens_input": tokens_in,
    "tokens_output": tokens_out,
    "tokens_total": tokens_total,
    "cost_usd": round(cost, 6),
}

# Idempotent write: rewrite ledger excluding yesterday, then append yesterday entry at end.
existing = []
if os.path.exists(ledger):
    with open(ledger, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                r = json.loads(line)
            except Exception:
                continue
            if r.get("date") == yesterday:
                continue
            existing.append(r)

with open(ledger, "w") as f:
    for r in existing:
        f.write(json.dumps(r) + "\n")
    f.write(json.dumps(entry) + "\n")

print("snapshot_done")
PY
