#!/usr/bin/env python3
"""Query status by task or agent from bus + persisted status logs."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

BUS_DEFAULT = Path("~/.openclaw/runtime/logs/team_bus.jsonl").expanduser()
STATUS_ROOT = Path("~/.openclaw/runtime/logs/status").expanduser()


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    with path.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def query_task(task_id: str, bus: Path) -> int:
    bus_events = [ev for ev in load_jsonl(bus) if ev.get("task_id") == task_id]
    task_dir = STATUS_ROOT / "tasks" / task_id
    persisted = {}
    if task_dir.exists():
        for p in sorted(task_dir.glob("*.jsonl")):
            rows = load_jsonl(p)
            if rows:
                persisted[p.stem] = rows[-1]

    state = "in_process"
    for ev in reversed(bus_events):
        if ev.get("type") == "TASK_UPDATE":
            state = ev.get("state", "in_process")
            break
    else:
        for ev in reversed(bus_events):
            if ev.get("type") == "STATUS" and ev.get("status") in {"error", "complete", "in_process"}:
                state = ev.get("status")
                break

    print(f"TASK: {task_id}")
    print(f"STATE: {state}")
    print(f"BUS_EVENTS: {len(bus_events)}")
    print("LATEST_BY_AGENT:")
    if not persisted:
        print("  (none)")
    else:
        for agent, ev in persisted.items():
            status = ev.get("state") or ev.get("status") or ev.get("type")
            print(f"  - {agent}: {status} | {ev.get('summary', '')}")
    return 0


def query_agent(agent: str, bus: Path) -> int:
    latest = STATUS_ROOT / "agents" / f"{agent}.latest.json"
    print(f"AGENT: {agent}")
    if latest.exists():
        print(latest.read_text(encoding="utf-8").rstrip())
    else:
        print("LATEST: none")

    events = [ev for ev in load_jsonl(bus) if (ev.get("agent") == agent or ev.get("actor") == agent)]
    print(f"BUS_EVENTS: {len(events)}")
    if events:
        tail = events[-5:]
        print("RECENT:")
        for ev in tail:
            task = ev.get("task_id") or "-"
            print(f"  - {ev.get('ts')} {ev.get('type')} task={task} {ev.get('summary', '')}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", type=Path, default=BUS_DEFAULT)
    ap.add_argument("--task-id")
    ap.add_argument("--agent")
    args = ap.parse_args()
    args.bus = args.bus.expanduser()

    if not args.task_id and not args.agent:
        raise SystemExit("Provide --task-id or --agent")
    if args.task_id:
        return query_task(args.task_id, args.bus)
    return query_agent(args.agent, args.bus)


if __name__ == "__main__":
    raise SystemExit(main())
