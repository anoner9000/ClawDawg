#!/usr/bin/env python3
"""Compatibility wrapper for status query CLI."""

from __future__ import annotations

import argparse
import subprocess
from pathlib import Path

TARGET = Path("~/.openclaw/workspace/ops/scripts/agents/query_status.py").expanduser()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--agent")
    ap.add_argument("--task")
    ap.add_argument("--task-id")
    ap.add_argument("--bus", default="~/.openclaw/runtime/logs/team_bus.jsonl")
    args = ap.parse_args()

    if not TARGET.exists():
        raise SystemExit(f"Missing target script: {TARGET}")

    task_id = args.task_id or args.task
    cmd = [str(TARGET), "--bus", args.bus]
    if args.agent:
        cmd.extend(["--agent", args.agent])
    if task_id:
        cmd.extend(["--task-id", task_id])

    if not args.agent and not task_id:
        raise SystemExit("Provide --agent or --task/--task-id")

    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
