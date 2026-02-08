#!/usr/bin/env python3
"""
emit_approval.py

Append a schema-compliant Deiphobe APPROVAL event to team_bus.jsonl.

Usage:
  emit_approval.py --task-id TASK --summary "..." \
    --expires-minutes 15 \
    [--bus /path/to/team_bus.jsonl] \
    [--detail key=value ...]
"""

import argparse, json
from datetime import datetime, timezone, timedelta

def utc_now():
    return datetime.now(timezone.utc)

def ts(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--summary", required=True)
    ap.add_argument("--expires-minutes", type=int, required=True)
    ap.add_argument("--bus", default="~/.openclaw/runtime/logs/team_bus.jsonl")
    ap.add_argument("--detail", action="append", default=[], help="key=value pairs")
    args = ap.parse_args()

    details = {}
    for kv in args.detail:
        if "=" not in kv:
            raise SystemExit(f"Invalid --detail '{kv}', expected key=value")
        k, v = kv.split("=", 1)
        details[k] = v

    now = utc_now()
    event = {
        "schema_version": "team_bus.v1.1",
        "ts": ts(now),
        "task_id": args.task_id,
        "agent": "deiphobe",
        "type": "APPROVAL",
        "summary": args.summary,
        "details": details,
        "expires_at": ts(now + timedelta(minutes=args.expires_minutes)),
        "next": "Executor may proceed before approval expiry"
    }

    bus = args.bus.replace("~", str(__import__("pathlib").Path.home()))
    with open(bus, "a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")

    print(f"APPROVAL written (expires in {args.expires_minutes} minutes)")

if __name__ == "__main__":
    main()
