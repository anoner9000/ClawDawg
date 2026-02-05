#!/usr/bin/env bash
# token_today_totals.sh
# Read-only: prints today's totals (tokens + USD) from llm_usage.jsonl

set -euo pipefail

RUNTIME_DIR="${OPENCLAW_RUNTIME_DIR:-$HOME/.openclaw/runtime}"
USAGE="$RUNTIME_DIR/logs/heartbeat/llm_usage.jsonl"

export USAGE

python3 - <<'INNERPY'
import json, os, datetime, pathlib

usage = pathlib.Path(os.path.expanduser(os.environ["USAGE"]))
today = datetime.date.today().isoformat()

tokens_in = tokens_out = tokens_total = 0
cost = 0.0

if usage.exists():
    for line in usage.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except Exception:
            continue
        if r.get("date") != today:
            continue
        tokens_in += int(r.get("input_tokens", 0) or 0)
        tokens_out += int(r.get("output_tokens", 0) or 0)
        tokens_total += int(r.get("total_tokens", 0) or 0)
        cost += float(r.get("cost_usd", 0) or 0)

print(f"Today ({today}) — input: {tokens_in:,}, output: {tokens_out:,}, total: {tokens_total:,} tokens • spend: ${cost:.6f}")
INNERPY
