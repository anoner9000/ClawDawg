#!/usr/bin/env python3
"""
task_state.py

Read-only task state inspector for OpenClaw team_bus.jsonl.

Usage:
  task_state.py --task-id TASK --bus /path/to/team_bus.jsonl
"""

import argparse, json
from datetime import datetime, timezone
from pathlib import Path


DENY_RISK_SEVERITY = {"high", "critical"}


def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def load_events(bus_path: Path, task_id: str):
    events = []
    with bus_path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            ev = json.loads(line)
            if ev.get("task_id") == task_id:
                events.append(ev)
    return events


def main():
    ap = argparse.ArgumentParser(description="Inspect task state from team bus")
    ap.add_argument("--task-id", required=True)
    ap.add_argument("--bus", default="~/.openclaw/runtime/logs/team_bus.jsonl")
    args = ap.parse_args()

    bus = Path(args.bus).expanduser()
    events = load_events(bus, args.task_id)

    if not events:
        print("STATE: UNKNOWN (no events for task)")
        return 1

    block_state = None           # None | BLOCKED | UNBLOCKED
    last_unblocked_index = -1
    approval = None
    blocking_risk = None

    for i, ev in enumerate(events):
        t = ev.get("type")

        if t == "BLOCKED":
            block_state = "BLOCKED"

        elif t == "UNBLOCKED":
            block_state = "UNBLOCKED"
            last_unblocked_index = i

        elif t == "APPROVAL" and ev.get("agent") == "deiphobe":
            approval = ev  # newest wins

    # Check for blocking risks after last UNBLOCKED
    for ev in events[last_unblocked_index + 1:]:
        if ev.get("type") == "RISK":
            sev = (ev.get("severity") or "").strip()
            if sev in DENY_RISK_SEVERITY:
                blocking_risk = ev
                break

    now = utc_now()

    # Approval status
    approval_status = "NONE"
    if approval:
        exp = approval.get("expires_at")
        if not exp:
            approval_status = "INVALID (missing expires_at)"
        else:
            expiry = parse_ts(exp)
            approval_status = "VALID" if now <= expiry else "EXPIRED"

    # Final state computation
    if block_state == "BLOCKED":
        state = "BLOCKED"
    elif blocking_risk:
        state = "BLOCKED (risk)"
    elif approval_status == "VALID":
        state = "APPROVED"
    elif approval_status == "EXPIRED":
        state = "APPROVAL EXPIRED"
    else:
        state = "PENDING"

    last_event = events[-1]

    # Output (intentionally boring and clear)
    print(f"TASK: {args.task_id}")
    print(f"STATE: {state}")
    print(f"BLOCK STATE: {block_state or 'never blocked'}")
    print(f"APPROVAL: {approval_status}")

    if approval and approval.get("expires_at"):
        print(f"APPROVAL EXPIRES: {approval['expires_at']}")

    if blocking_risk:
        print(f"BLOCKING RISK: severity={blocking_risk.get('severity')}")
        print(f"  summary: {blocking_risk.get('summary')}")

    print("LAST EVENT:")
    print(f"  ts: {last_event.get('ts')}")
    print(f"  agent: {last_event.get('agent')}")
    print(f"  type: {last_event.get('type')}")
    print(f"  summary: {last_event.get('summary')}")


if __name__ == "__main__":
    main()
