#!/usr/bin/env python3
"""
task_dashboard.py

Read-only CLI dashboard for OpenClaw team bus.

Modes:
1) Dashboard table:
   TASK_ID | STATE | APPROVAL | LAST EVENT

2) Detail view:
   --show TASK_ID  (prints a detailed view akin to task_state.py)

State logic (v1.1-aware):
- BLOCKED if latest {BLOCKED, UNBLOCKED} is BLOCKED
- BLOCKED (risk) if any RISK with severity in deny set occurs after last UNBLOCKED
- APPROVED if latest Deiphobe APPROVAL exists and is unexpired
- APPROVAL EXPIRED if approval exists but expired
- PENDING otherwise

Usage examples:
  task_dashboard.py
  task_dashboard.py --interval 5
  task_dashboard.py --all
  task_dashboard.py --filter gmail-
  task_dashboard.py --sort state
  task_dashboard.py --show gmail-2026-02-07-01
  task_dashboard.py --color
  NO_CLEAR=1 task_dashboard.py --interval 5

Notes:
- Read-only: never writes to bus.
- Colors are optional and dependency-free.
"""

import argparse
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple


DEFAULT_DENY = {"high", "critical"}

STATE_ORDER = {
    "BLOCKED": 0,
    "BLOCKED (risk)": 1,
    "APPROVED": 2,
    "APPROVAL EXPIRED": 3,
    "PENDING": 4,
    "UNKNOWN": 5,
}

# --- ANSI color helpers (no deps) ---

class Ansi:
    RESET = "\033[0m"
    DIM = "\033[2m"
    BOLD = "\033[1m"

    RED = "\033[31m"
    YELLOW = "\033[33m"
    GREEN = "\033[32m"
    CYAN = "\033[36m"
    MAGENTA = "\033[35m"

def is_tty() -> bool:
    try:
        return sys.stdout.isatty()
    except Exception:
        return False

def colorize(text: str, color_code: str, enable: bool) -> str:
    if not enable:
        return text
    return f"{color_code}{text}{Ansi.RESET}"

def state_color(state: str, enable: bool) -> str:
    if not enable:
        return state
    if state.startswith("BLOCKED"):
        return colorize(state, Ansi.RED + Ansi.BOLD, True)
    if state == "APPROVED":
        return colorize(state, Ansi.GREEN + Ansi.BOLD, True)
    if state == "APPROVAL EXPIRED":
        return colorize(state, Ansi.YELLOW + Ansi.BOLD, True)
    if state == "PENDING":
        return colorize(state, Ansi.CYAN, True)
    return state

def approval_color(approval: str, enable: bool) -> str:
    if not enable:
        return approval
    if approval.startswith("valid"):
        return colorize(approval, Ansi.GREEN, True)
    if approval == "expired":
        return colorize(approval, Ansi.YELLOW, True)
    if approval in ("invalid", "none"):
        return colorize(approval, Ansi.DIM, True)
    return approval

# --- core parsing/state ---

def parse_ts(ts: str) -> datetime:
    try:
        return datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except Exception:
        return datetime.fromtimestamp(0, tz=timezone.utc)

def now_utc() -> datetime:
    return datetime.now(timezone.utc)

def clear_screen():
    if os.environ.get("NO_CLEAR") == "1":
        return
    sys.stdout.write("\033[2J\033[H")
    sys.stdout.flush()

@dataclass
class TaskRow:
    task_id: str
    state: str
    approval: str
    approval_expires_at: Optional[str]
    last_ts: str
    last_agent: str
    last_type: str
    last_summary: str

@dataclass
class TaskDetail:
    task_id: str
    state: str
    block_state: str
    approval_status: str
    approval_expires_at: Optional[str]
    blocking_risk: Optional[dict]
    last_event: dict
    counts: Dict[str, int]

def load_events(bus_path: Path) -> List[dict]:
    events: List[dict] = []
    with bus_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except Exception as e:
                print(f"[warn] bus parse error line {line_no}: {e}", file=sys.stderr)
    return events

def truncate(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    if width <= 1:
        return s[:width]
    return s[: max(0, width - 1)] + "…"

def compute_task_detail(task_id: str, evs: List[dict], deny_set: set) -> TaskDetail:
    block_state: Optional[str] = None  # None | "BLOCKED" | "UNBLOCKED"
    last_unblocked_index = -1
    approval_ev: Optional[dict] = None

    counts: Dict[str, int] = {}
    for ev in evs:
        t = ev.get("type", "<?>")
        counts[t] = counts.get(t, 0) + 1

    for i, ev in enumerate(evs):
        t = ev.get("type")
        if t == "BLOCKED":
            block_state = "BLOCKED"
        elif t == "UNBLOCKED":
            block_state = "UNBLOCKED"
            last_unblocked_index = i
        elif t == "APPROVAL" and ev.get("agent") == "deiphobe":
            approval_ev = ev  # newest wins

    blocking_risk = None
    for ev in evs[last_unblocked_index + 1:]:
        if ev.get("type") == "RISK":
            sev = (ev.get("severity") or "").strip()
            if sev in deny_set:
                blocking_risk = ev
                break

    approval_status = "none"
    approval_expires_at = None
    if approval_ev:
        exp = approval_ev.get("expires_at")
        approval_expires_at = exp
        if not exp:
            approval_status = "invalid"
        else:
            approval_status = "valid" if now_utc() <= parse_ts(exp) else "expired"

    if block_state == "BLOCKED":
        state = "BLOCKED"
    elif blocking_risk:
        state = "BLOCKED (risk)"
    elif approval_status == "valid":
        state = "APPROVED"
    elif approval_status == "expired":
        state = "APPROVAL EXPIRED"
    else:
        state = "PENDING"

    last = evs[-1]
    return TaskDetail(
        task_id=task_id,
        state=state,
        block_state=block_state or "never blocked",
        approval_status=approval_status,
        approval_expires_at=approval_expires_at,
        blocking_risk=blocking_risk,
        last_event=last,
        counts=counts,
    )

def compute_task_row(task_id: str, evs: List[dict], deny_set: set) -> TaskRow:
    d = compute_task_detail(task_id, evs, deny_set)

    approval = d.approval_status
    if approval == "valid" and d.approval_expires_at:
        remaining = int((parse_ts(d.approval_expires_at) - now_utc()).total_seconds() // 60)
        approval = f"valid ({max(0, remaining)}m)"
    elif approval == "expired":
        approval = "expired"

    last = d.last_event
    return TaskRow(
        task_id=task_id,
        state=d.state,
        approval=approval,
        approval_expires_at=d.approval_expires_at,
        last_ts=last.get("ts", ""),
        last_agent=last.get("agent", ""),
        last_type=last.get("type", ""),
        last_summary=(last.get("summary", "") or "")[:80],
    )

def render_table(rows: List[TaskRow], width: int, color: bool):
    col_task = 26
    col_state = 16
    col_appr = 14
    col_last = max(20, width - (col_task + col_state + col_appr + 3 * 3))

    header = (
        f"{'TASK ID'.ljust(col_task)}   "
        f"{'STATE'.ljust(col_state)}   "
        f"{'APPROVAL'.ljust(col_appr)}   "
        f"{'LAST EVENT'.ljust(col_last)}"
    )
    sep = "-" * min(width, len(header))
    print(header)
    print(sep)

    for r in rows:
        last_evt = f"{r.last_type}({r.last_agent}) {r.last_ts} — {r.last_summary}"
        state_txt = state_color(truncate(r.state, col_state), color)
        appr_txt = approval_color(truncate(r.approval, col_appr), color)
        print(
            f"{truncate(r.task_id, col_task).ljust(col_task)}   "
            f"{state_txt.ljust(col_state + (0 if not color else 0))}   "
            f"{appr_txt.ljust(col_appr + (0 if not color else 0))}   "
            f"{truncate(last_evt, col_last)}"
        )

def render_detail(d: TaskDetail, color: bool):
    def k(label: str) -> str:
        return colorize(label, Ansi.MAGENTA + Ansi.BOLD, color)

    print(f"{k('TASK')}: {d.task_id}")
    print(f"{k('STATE')}: {state_color(d.state, color)}")
    print(f"{k('BLOCK STATE')}: {d.block_state}")

    appr = d.approval_status
    if appr == "valid" and d.approval_expires_at:
        remaining = int((parse_ts(d.approval_expires_at) - now_utc()).total_seconds() // 60)
        appr = f"valid ({max(0, remaining)}m)"
    print(f"{k('APPROVAL')}: {approval_color(appr, color)}")
    if d.approval_expires_at:
        print(f"{k('APPROVAL EXPIRES')}: {d.approval_expires_at}")

    if d.blocking_risk:
        sev = d.blocking_risk.get("severity")
        summ = d.blocking_risk.get("summary", "")
        print(f"{k('BLOCKING RISK')}: severity={sev}")
        print(f"  summary: {summ}")

    le = d.last_event
    print(f"{k('LAST EVENT')}:")
    print(f"  ts: {le.get('ts')}")
    print(f"  agent: {le.get('agent')}")
    print(f"  type: {le.get('type')}")
    print(f"  summary: {le.get('summary')}")
    print(f"{k('COUNTS')}: " + ", ".join([f"{t}={n}" for t, n in sorted(d.counts.items())]))

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus", default="~/.openclaw/runtime/logs/team_bus.jsonl")
    ap.add_argument("--interval", type=int, default=0, help="Refresh every N seconds (0 = once)")
    ap.add_argument("--limit", type=int, default=30, help="Show top N tasks")
    ap.add_argument("--all", action="store_true", help="Show all tasks (ignores --limit)")
    ap.add_argument("--filter", default="", help="Substring filter for task_id")
    ap.add_argument("--sort", default="last_ts", choices=["last_ts", "task_id", "state"])
    ap.add_argument("--deny-risk-severity", default="high,critical")
    ap.add_argument("--width", type=int, default=120, help="Render width (characters)")
    ap.add_argument("--show", default="", help="Show detailed view for a specific task_id")
    ap.add_argument("--color", action="store_true", help="Enable ANSI color output (TTY recommended)")
    ap.add_argument("--force-color", action="store_true", help="Force color even if not a TTY")
    args = ap.parse_args()

    deny_set = {s.strip() for s in args.deny_risk_severity.split(",") if s.strip()}
    if not deny_set:
        deny_set = DEFAULT_DENY

    bus_path = Path(args.bus).expanduser()
    if not bus_path.exists():
        print(f"ERROR: bus not found: {bus_path}", file=sys.stderr)
        return 2

    color_enabled = (args.color and is_tty()) or args.force_color

    def run_once():
        events = load_events(bus_path)

        by_task: Dict[str, List[dict]] = {}
        for ev in events:
            tid = ev.get("task_id")
            if not tid:
                continue
            if args.filter and args.filter not in tid:
                continue
            by_task.setdefault(tid, []).append(ev)

        if args.show:
            evs = by_task.get(args.show)
            clear_screen()
            print(f"OpenClaw Task Detail  |  bus={bus_path}  |  now={now_utc().strftime('%Y-%m-%dT%H:%M:%SZ')}\n")
            if not evs:
                print(f"STATE: UNKNOWN (no events found for task_id={args.show})")
                return
            d = compute_task_detail(args.show, evs, deny_set)
            render_detail(d, color_enabled)
            return

        rows: List[TaskRow] = []
        for tid, evs in by_task.items():
            rows.append(compute_task_row(tid, evs, deny_set))

        if args.sort == "last_ts":
            rows.sort(key=lambda r: parse_ts(r.last_ts), reverse=True)
        elif args.sort == "task_id":
            rows.sort(key=lambda r: r.task_id)
        else:
            rows.sort(key=lambda r: (STATE_ORDER.get(r.state, 999), parse_ts(r.last_ts)))

        if not args.all:
            rows = rows[: max(0, args.limit)]

        clear_screen()
        print(
            f"OpenClaw Task Dashboard  |  bus={bus_path}  |  now={now_utc().strftime('%Y-%m-%dT%H:%M:%SZ')}"
            + (f"  |  filter={args.filter}" if args.filter else "")
        )
        print()
        render_table(rows, width=args.width, color=color_enabled)

        print("\nLegend:")
        print("  BLOCKED = last block state is BLOCKED")
        print("  BLOCKED (risk) = high/critical RISK after last UNBLOCKED")
        print("Tips:")
        print("  - Set NO_CLEAR=1 to disable screen clearing")
        print("  - Use --show TASK_ID for a detailed per-task view")
        print("  - Use --all to show all tasks (no limit)")

    if args.interval <= 0:
        run_once()
        return 0

    try:
        while True:
            run_once()
            sys.stdout.flush()
            import time
            time.sleep(args.interval)
    except KeyboardInterrupt:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
