#!/usr/bin/env python3
"""Emit STATUS_CHECK and optionally collect replies."""

from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path

BUS_DEFAULT = Path("~/.openclaw/runtime/logs/team_bus.jsonl").expanduser()
REG_DEFAULT = Path("~/.openclaw/workspace/ops/schemas/agents.json").expanduser()


def ts_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_ts(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)


def append(bus: Path, event: dict) -> None:
    bus.parent.mkdir(parents=True, exist_ok=True)
    with bus.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


def load_events(bus: Path) -> list[dict]:
    if not bus.exists():
        return []
    out: list[dict] = []
    with bus.open("r", encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def expected_agents(scope: str, registry_path: Path) -> list[str]:
    if scope.startswith("agent:"):
        return [scope.split(":", 1)[1]]
    if scope.startswith("task:"):
        return []
    if not registry_path.exists():
        return []
    reg = json.loads(registry_path.read_text(encoding="utf-8"))
    return sorted(reg.get("agents", {}).keys())


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--actor", default="deiphobe")
    ap.add_argument("--scope", default="all")
    ap.add_argument("--details", default="")
    ap.add_argument("--bus", type=Path, default=BUS_DEFAULT)
    ap.add_argument("--registry", type=Path, default=REG_DEFAULT)
    ap.add_argument("--wait-seconds", type=int, default=0)
    args = ap.parse_args()

    args.bus = args.bus.expanduser()
    args.registry = args.registry.expanduser()

    event = {
        "schema_version": "team_bus.v1.1",
        "ts": ts_utc(),
        "task_id": None,
        "agent": args.actor,
        "actor": args.actor,
        "type": "STATUS_CHECK",
        "scope": args.scope,
        "summary": f"Status check scope={args.scope}",
        "details": args.details,
    }
    append(args.bus, event)
    print(json.dumps({"posted": event}, ensure_ascii=False))

    if args.wait_seconds <= 0:
        return 0

    cutoff = parse_ts(event["ts"])
    time.sleep(args.wait_seconds)
    events = load_events(args.bus)

    replies = {}
    for ev in events:
        if ev.get("type") != "STATUS":
            continue
        ts = ev.get("ts")
        if not ts:
            continue
        try:
            if parse_ts(ts) < cutoff:
                continue
        except ValueError:
            continue
        agent = ev.get("agent") or ev.get("actor")
        if agent:
            replies[agent] = ev

    expected = expected_agents(args.scope, args.registry)
    no_reply = [a for a in expected if a not in replies]

    summary = {
        "scope": args.scope,
        "expected_agents": expected,
        "reply_count": len(replies),
        "replies": replies,
        "no_reply": no_reply,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
