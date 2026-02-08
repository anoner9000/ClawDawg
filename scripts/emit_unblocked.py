#!/usr/bin/env python3
"""
emit_unblocked.py

Append a schema-compliant UNBLOCKED event (Deiphobe-only).

Usage:
  emit_unblocked.py --task-id TASK --summary "..." \
    [--bus /path/to/team_bus.jsonl] \
    [--detail key=value ...]
"""

import argparse, json
from datetime import datetime, timezone

def ts_now():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--bus", default="~/.openclaw/runtime/logs/team_bus.jsonl")
    ap.add_argument("--detail", action="append", default=[], help="key=value pairs")
    args = ap.parse_args()

    details = {}
    for kv in args.detail:
        if "=" not in kv:
            raise SystemExit(f"Invalid --detail '{kv}', expected key=value")
        k, v = kv.split("=", 1)
        details[k] = v

    event = {
        "schema_version": "team_bus.v1.1",
        "ts": ts_now(),
        "task_id": args.task_id,
        "agent": "deiphobe",
        "type": "UNBLOCKED",
        "summary": args.summary,
        "details": details,
        "next": "New approval required before execution"
    }

    bus = args.bus.replace("~", str(__import__("pathlib").Path.home()))
    with open(bus, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    print("UNBLOCKED written")

if __name__ == "__main__":
    main()
