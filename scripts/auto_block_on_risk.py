#!/usr/bin/env python3
"""
auto_block_on_risk.py (v1.1-aware)

Auto-appends BLOCKED when a high/critical RISK is present *after the last UNBLOCKED*,
and the task is not currently blocked.

Policy:
- BLOCKED state = last of {BLOCKED, UNBLOCKED}
- Only consider RISK events that occur after the last UNBLOCKED (or from beginning if none)
"""

import argparse, json, sys
from datetime import datetime, timezone
from collections import defaultdict

def utc_now_str() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", required=True)
    ap.add_argument("--block-severity", default="high,critical")
    args = ap.parse_args()

    block_set = {s.strip() for s in args.block_severity.split(",") if s.strip()}
    if not block_set:
        print("AUTO-BLOCK ERROR: empty --block-severity", file=sys.stderr)
        return 2

    events_by_task = defaultdict(list)
    try:
        with open(args.bus, "r", encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                ev = json.loads(line)
                tid = ev.get("task_id")
                if tid:
                    events_by_task[tid].append(ev)
    except Exception as e:
        print(f"AUTO-BLOCK ERROR: cannot read bus: {e}", file=sys.stderr)
        return 1

    to_block = []  # (task_id, triggered_sev)
    for task_id, evs in events_by_task.items():
        # Determine current blocked state: last of BLOCKED/UNBLOCKED
        blocked_state = None  # None | "BLOCKED" | "UNBLOCKED"
        last_unblocked_index = -1

        for i, ev in enumerate(evs):
            t = ev.get("type")
            if t in ("BLOCKED", "UNBLOCKED"):
                blocked_state = t
            if t == "UNBLOCKED":
                last_unblocked_index = i

        if blocked_state == "BLOCKED":
            continue  # already blocked

        # Only consider RISK after last UNBLOCKED (or all if none)
        start_i = last_unblocked_index + 1
        for ev in evs[start_i:]:
            if ev.get("type") != "RISK":
                continue
            sev = (ev.get("severity") or "").strip()
            if sev in block_set:
                to_block.append((task_id, sev))
                break

    if not to_block:
        return 0

    try:
        with open(args.bus, "a", encoding="utf-8") as f:
            for task_id, sev in to_block:
                f.write(json.dumps({
                    "schema_version": "team_bus.v1.1",
                    "ts": utc_now_str(),
                    "task_id": task_id,
                    "agent": "watcher",
                    "type": "BLOCKED",
                    "summary": "Task automatically blocked due to high-severity RISK",
                    "details": {
                        "policy": "Auto-block on severity threshold (post-UNBLOCKED aware)",
                        "block_severity": sorted(block_set),
                        "triggered_by_severity": sev,
                        "requires": "Deiphobe UNBLOCKED + APPROVAL to resume"
                    },
                    "next": "Awaiting Deiphobe decision"
                }, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"AUTO-BLOCK ERROR: cannot append BLOCKED: {e}", file=sys.stderr)
        return 3

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
