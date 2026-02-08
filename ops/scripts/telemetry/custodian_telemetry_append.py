#!/usr/bin/env python3
import json, os, sys
from datetime import datetime, timezone

def iso_utc_now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def date_utc_now():
    return datetime.now(timezone.utc).date().isoformat()

def extract_usage(obj: dict) -> dict:
    # common OpenAI shapes
    u = obj.get("usage") or {}
    if not u and isinstance(obj.get("response"), dict):
        u = obj["response"].get("usage") or {}
    return u if isinstance(u, dict) else {}

def safe_int(x, default=0):
    try:
        return int(x)
    except Exception:
        return default

def extract_response_id(obj: dict):
    # common keys
    for k in ("id", "response_id"):
        v = obj.get(k)
        if isinstance(v, str) and v:
            return v
    r = obj.get("response")
    if isinstance(r, dict):
        v = r.get("id")
        if isinstance(v, str) and v:
            return v
    return None

def extract_model(obj: dict):
    for k in ("model",):
        v = obj.get(k)
        if isinstance(v, str) and v:
            return v
    r = obj.get("response")
    if isinstance(r, dict):
        v = r.get("model")
        if isinstance(v, str) and v:
            return v
    return None

def main():
    if len(sys.argv) != 3:
        print("Usage: custodian_telemetry_append.py /path/to/llm_response.json /path/to/llm_usage.jsonl", file=sys.stderr)
        return 2

    resp_path = sys.argv[1]
    ledger_path = sys.argv[2]

    if not os.path.exists(resp_path):
        print(f"missing response file: {resp_path}", file=sys.stderr)
        return 2

    with open(resp_path, "r", encoding="utf-8", errors="replace") as f:
        obj = json.load(f)

    # Skip error-only responses (they are not "usage")
    if isinstance(obj.get("error"), dict):
        # record nothing; Custodian can track failures elsewhere if desired
        print("skip_error_response")
        return 0

    usage = extract_usage(obj)
    inp = usage.get("input_tokens") or usage.get("prompt_tokens")
    out = usage.get("output_tokens") or usage.get("completion_tokens")
    tot = usage.get("total_tokens")

    input_tokens = safe_int(inp, 0)
    output_tokens = safe_int(out, 0)
    total_tokens = safe_int(tot, input_tokens + output_tokens)

    model = extract_model(obj) or "unknown"
    response_id = extract_response_id(obj)

    entry = {
        "ts": iso_utc_now(),
        "date": date_utc_now(),
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
        "response_id": response_id,
        "http_status": 200,
        "source": resp_path,
    }

    os.makedirs(os.path.dirname(ledger_path), exist_ok=True)
    with open(ledger_path, "a", encoding="utf-8") as out_f:
        out_f.write(json.dumps(entry, separators=(",", ":"), ensure_ascii=False) + "\n")

    print("appended")

if __name__ == "__main__":
    raise SystemExit(main())
