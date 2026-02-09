#!/usr/bin/env python3
"""
peabody_run.py

Deterministic Peabody task runner.

Task queue:
  ~/.openclaw/workspace/archive/memory/agent_tasks/task_*.json

A task is "pending" if:
  - task_*.response.md does NOT exist
  - task_*.done does NOT exist
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

WS = Path.home() / ".openclaw" / "workspace"
TASKDIR = WS / "archive" / "memory" / "agent_tasks"


def die(msg: str, code: int = 2) -> None:
    print(msg, file=sys.stderr)
    raise SystemExit(code)


def load_task(path: Path) -> dict:
    try:
        return json.loads(path.read_text())
    except Exception as exc:  # noqa: BLE001
        die(f"Failed to parse JSON: {path} ({exc})")


def response_path(task_path: Path) -> Path:
    return task_path.with_suffix(task_path.suffix + ".response.md")


def diff_path(task_path: Path) -> Path:
    return task_path.with_suffix(task_path.suffix + ".diff")


def done_path(task_path: Path) -> Path:
    return task_path.with_suffix(task_path.suffix + ".done")


def is_pending(task_path: Path) -> bool:
    return (
        task_path.name.startswith("task_")
        and task_path.suffix == ".json"
        and not response_path(task_path).exists()
        and not done_path(task_path).exists()
    )


def list_pending() -> list[Path]:
    if not TASKDIR.exists():
        return []
    tasks = sorted(
        TASKDIR.glob("task_*.json"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    return [task for task in tasks if is_pending(task)]


def format_task_summary(task_path: Path, task: dict) -> str:
    created_at = task.get("created_at")
    created_s = ""
    if isinstance(created_at, int):
        created_s = datetime.fromtimestamp(created_at).isoformat()

    return (
        f"FILE: {task_path}\n"
        f"id: {task.get('id')}\n"
        f"from: {task.get('from_agent')}  to: {task.get('to_agent')}\n"
        f"title: {task.get('title')}\n"
        f"created_at: {created_at} {created_s}\n"
        f"context_paths: {task.get('context_paths', [])}\n"
    )


def write_stub(task_path: Path, task: dict, force: bool = False) -> Path:
    rp = response_path(task_path)
    dp = diff_path(task_path)

    if rp.exists() and not force:
        return rp

    ctx = task.get("context_paths") or []
    ctx_block = "\n".join(f"- {path}" for path in ctx) if ctx else "- (none provided)"

    stub = f"""# Peabody Response

## Task metadata
- id: {task.get('id')}
- from: {task.get('from_agent')}
- to: {task.get('to_agent')}
- title: {task.get('title')}
- task_file: {task_path}

## Request
{task.get('request')}

## Context paths
{ctx_block}

## Summary
-

## Risks / gotchas
-

## Proposed patch / diff
- Attach unified diff in: `{dp.name}`
- Or paste diff below.

## Verification commands
```bash
set -euo pipefail
# add the exact commands you ran / recommend
```
"""

    rp.write_text(stub)
    if not dp.exists():
        dp.write_text("")
    return rp


def mark_done(task_path: Path) -> Path:
    dp = done_path(task_path)
    stamp = datetime.utcnow().isoformat() + "Z\n"
    dp.write_text(stamp)
    return dp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--next", action="store_true")
    ap.add_argument("--pick", type=str, default="")
    ap.add_argument("--stub", action="store_true")
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--done", action="store_true")
    args = ap.parse_args()

    if args.list:
        pending = list_pending()
        if not pending:
            print("(no pending tasks)")
            return 0
        for path in pending:
            task = load_task(path)
            print(f"{path.name}\t{task.get('title')}")
        return 0

    if args.pick:
        task_path = Path(args.pick).expanduser()
        if not task_path.exists():
            die(f"--pick path does not exist: {task_path}")
    else:
        pending = list_pending()
        if not pending:
            print("(no pending tasks)")
            return 0
        task_path = pending[0]

    task = load_task(task_path)
    print(format_task_summary(task_path, task))
    print("\n--- REQUEST ---\n")
    print(task.get("request", "").rstrip())
    print("\n--------------\n")

    if args.stub:
        rp = write_stub(task_path, task, force=args.force)
        print(f"wrote: {rp}")
        print(f"diff placeholder: {diff_path(task_path)}")

    if args.done:
        done = mark_done(task_path)
        print(f"marked done: {done}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
