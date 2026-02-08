#!/usr/bin/env python3
"""
gate_require_approval.py (v1.1-aware)

Allows execution ONLY if:
- Latest block state is UNBLOCKED (or never blocked)
- No high/critical RISK exists after last UNBLOCKED
- Latest Deiphobe APPROVAL exists and is unexpired
"""

import argparse, json, sys
from datetime import datetime, timezone

def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)

def utc_now() -> datetime:
    return datetime.now(timezone.utc)

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--bus", required=True)
    ap.add_argument("--deny-risk-severity", default="high,critical")
    args = ap.parse_args()

    deny_set = {s.strip() for s in args.deny_risk_severity.split(",") if s.strip()}
    if not deny_set:
        print("GATE ERROR: empty deny set", file=sys.stderr)
        return 14

    events = []
    try:
        with open(args.bus, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                ev = json.loads(line)
                if ev.get("task_id") == args.task_id:
                    events.append(ev)
    except Exception as e:
        print(f"GATE ERROR: cannot read bus: {e}", file=sys.stderr)
        return 14

    if not events:
        print("GATE DENY: no events for task", file=sys.stderr)
        return 10

    # Track last UNBLOCKED position and current block state
    block_state = None  # None | "BLOCKED" | "UNBLOCKED"
    last_unblocked_index = -1
    approval = None

    for i, ev in enumerate(events):
        t = ev.get("type")

        if t == "UNBLOCKED":
            if ev.get("agent") != "deiphobe":
                print("GATE DENY: UNBLOCKED not from Deiphobe", file=sys.stderr)
                return 13
            block_state = "UNBLOCKED"
            last_unblocked_index = i

        elif t == "BLOCKED":
            block_state = "BLOCKED"

        elif t == "APPROVAL" and ev.get("agent") == "deiphobe":
            approval = ev  # newest wins

    if block_state == "BLOCKED":
        print("GATE DENY: BLOCKED present (not cleared)", file=sys.stderr)
        return 13

    # Deny if any high/critical RISK exists after last UNBLOCKED
    start_i = last_unblocked_index + 1
    for ev in events[start_i:]:
        if ev.get("type") != "RISK":
            continue
        sev = (ev.get("severity") or "").strip()
        if sev in deny_set:
            print(f"GATE DENY: RISK severity={sev} present", file=sys.stderr)
            return 12

    if not approval:
        print("GATE DENY: no Deiphobe APPROVAL", file=sys.stderr)
        return 10

    expires_at = approval.get("expires_at")
    if not expires_at:
        print("GATE DENY: APPROVAL missing expires_at", file=sys.stderr)
        return 11

    try:
        expiry = parse_ts(expires_at)
    except Exception:
        print("GATE DENY: invalid expires_at format", file=sys.stderr)
        return 11

    if utc_now() > expiry:
        print(f"GATE DENY: approval expired at {expires_at}", file=sys.stderr)
        return 11

    print("GATE OK: unblocked, no blocking risks, approval valid")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
