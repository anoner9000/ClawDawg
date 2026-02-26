#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional, Tuple
from zoneinfo import ZoneInfo

LEDGER_PATH = Path(os.environ.get("OPENCLAW_REMINDER_LEDGER", "memory/reminders.jsonl"))
DEFAULT_TZ = os.environ.get("OPENCLAW_TZ", "America/Chicago")

# ----------------------------
# Utilities
# ----------------------------
def _ensure_parent(p: Path) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)

def _now_utc() -> datetime:
    return datetime.now(timezone.utc)

def _utc_iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()

def _parse_iso(s: str) -> datetime:
    s = s.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    dt = datetime.fromisoformat(s)
    return dt

def _parse_duration(s: str) -> timedelta:
    s = s.strip().lower().replace(" ", "")
    if not s:
        raise ValueError("empty duration")
    parts = re.findall(r"(\d+)([smhd])", s)
    if not parts:
        raise ValueError(f"invalid duration: {s}")
    total = timedelta()
    for n, unit in parts:
        n_i = int(n)
        if unit == "s":
            total += timedelta(seconds=n_i)
        elif unit == "m":
            total += timedelta(minutes=n_i)
        elif unit == "h":
            total += timedelta(hours=n_i)
        elif unit == "d":
            total += timedelta(days=n_i)
        else:
            raise ValueError(f"unknown unit: {unit}")
    return total

def append_event(event: Dict[str, Any]) -> None:
    _ensure_parent(LEDGER_PATH)
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, separators=(",", ":"), ensure_ascii=False) + "\n")

def iter_events() -> Iterator[Dict[str, Any]]:
    if not LEDGER_PATH.exists():
        return iter(())  # always iterator
    def _gen() -> Iterator[Dict[str, Any]]:
        with LEDGER_PATH.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    yield json.loads(line)
                except json.JSONDecodeError:
                    continue
    return _gen()

# ----------------------------
# State from receipts
# ----------------------------
@dataclass
class ReminderState:
    id: str
    tz: str
    target_agent: str
    content: str
    created_at_utc: str
    scheduled_for_utc: str
    status: str  # pending|delivered|missed|canceled
    attempts: int = 0
    last_attempt_at_utc: Optional[str] = None
    delivered_at_utc: Optional[str] = None
    missed_at_utc: Optional[str] = None
    canceled_at_utc: Optional[str] = None
    last_error: Optional[str] = None

def replay_state() -> Dict[str, ReminderState]:
    state: Dict[str, ReminderState] = {}
    for ev in iter_events():
        et = ev.get("event")
        rid = ev.get("id")
        if not et or not rid:
            continue

        if et == "created":
            try:
                state[rid] = ReminderState(
                    id=rid,
                    tz=ev["tz"],
                    target_agent=ev["target_agent"],
                    content=ev["content"],
                    created_at_utc=ev["created_at_utc"],
                    scheduled_for_utc=ev["scheduled_for_utc"],
                    status="pending",
                )
            except KeyError:
                continue

        r = state.get(rid)
        if not r:
            continue

        if et == "attempted":
            r.attempts += 1
            r.last_attempt_at_utc = ev.get("at_utc")
            r.last_error = ev.get("error")

        elif et == "delivered":
            r.status = "delivered"
            r.delivered_at_utc = ev.get("at_utc")
            r.last_error = None

        elif et == "missed":
            r.status = "missed"
            r.missed_at_utc = ev.get("at_utc")
            r.last_error = ev.get("error")

        elif et == "canceled":
            r.status = "canceled"
            r.canceled_at_utc = ev.get("at_utc")
    return state

# ----------------------------
# Delivery backend
# ----------------------------
def _deliver_via_mc(target_agent: str, content: str) -> Tuple[bool, Optional[str]]:
    mc = Path("scripts/mc")
    if mc.exists() and mc.is_file():
        try:
            subprocess.run(
                [str(mc), "notify", "--agent", target_agent, "--content", content],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            return True, None
        except subprocess.CalledProcessError as e:
            return False, (e.stderr or e.stdout or str(e)).strip()
    # Fallback: stdout (still ledgered as delivered)
    print(f"[reminder -> {target_agent}] {content}")
    return True, None

# ----------------------------
# Public commands
# ----------------------------
def create_reminder(*, target_agent: str, content: str, tz: str, in_duration: Optional[str], at_local_iso: Optional[str]) -> Dict[str, Any]:
    now = _now_utc()
    rid = str(uuid.uuid4())

    if in_duration:
        dt_utc = now + _parse_duration(in_duration)
    elif at_local_iso:
        parsed = _parse_iso(at_local_iso)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=ZoneInfo(tz))
        dt_utc = parsed.astimezone(timezone.utc)
    else:
        raise ValueError("must specify --in or --at")

    ev = {
        "event": "created",
        "id": rid,
        "created_at_utc": _utc_iso(now),
        "scheduled_for_utc": _utc_iso(dt_utc),
        "tz": tz,
        "target_agent": target_agent,
        "content": content,
        "source": "scribe",
    }
    append_event(ev)
    return ev

def pulse(*, grace_seconds: int) -> Dict[str, int]:
    now = _now_utc()
    now_iso = _utc_iso(now)
    st = replay_state()

    delivered = 0
    missed = 0
    pending_seen = 0

    for r in st.values():
        if r.status != "pending":
            continue

        pending_seen += 1

        try:
            sched = _parse_iso(r.scheduled_for_utc)
            if sched.tzinfo is None:
                sched = sched.replace(tzinfo=timezone.utc)
        except Exception:
            append_event({"event":"missed","id":r.id,"at_utc":now_iso,"error":"invalid scheduled_for_utc"})
            missed += 1
            continue

        if sched > now:
            continue

        ok, err = _deliver_via_mc(r.target_agent, r.content)
        append_event({"event":"attempted","id":r.id,"at_utc":now_iso,"error":err})

        if ok:
            append_event({"event":"delivered","id":r.id,"at_utc":now_iso})
            delivered += 1
        else:
            overdue = (now - sched).total_seconds()
            if overdue >= grace_seconds:
                append_event({"event":"missed","id":r.id,"at_utc":now_iso,"error":err})
                missed += 1

    return {"delivered": delivered, "missed": missed, "pending_seen": pending_seen}

def list_pending() -> list[Dict[str, Any]]:
    out: list[Dict[str, Any]] = []
    for r in replay_state().values():
        if r.status != "pending":
            continue
        out.append(
            {
                "id": r.id,
                "created_at_utc": r.created_at_utc,
                "scheduled_for_utc": r.scheduled_for_utc,
                "tz": r.tz,
                "target_agent": r.target_agent,
                "content": r.content,
                "status": r.status,
                "attempts": r.attempts,
                "last_attempt_at_utc": r.last_attempt_at_utc,
                "last_error": r.last_error,
            }
        )
    return out

def explain_reminder(reminder_id: str) -> Optional[Dict[str, Any]]:
    r = replay_state().get(reminder_id)
    if not r:
        return None
    return {
        "id": r.id,
        "created_at_utc": r.created_at_utc,
        "scheduled_for_utc": r.scheduled_for_utc,
        "tz": r.tz,
        "target_agent": r.target_agent,
        "content": r.content,
        "status": r.status,
        "attempts": r.attempts,
        "last_attempt_at_utc": r.last_attempt_at_utc,
        "delivered_at_utc": r.delivered_at_utc,
        "missed_at_utc": r.missed_at_utc,
        "canceled_at_utc": r.canceled_at_utc,
        "last_error": r.last_error,
    }

def main(argv: list[str]) -> int:
    import argparse
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("create")
    c.add_argument("--agent", required=True)
    c.add_argument("--content", required=True)
    c.add_argument("--tz", default=DEFAULT_TZ)
    grp = c.add_mutually_exclusive_group(required=True)
    grp.add_argument("--in", dest="in_duration")
    grp.add_argument("--at", dest="at_local_iso")
    c.add_argument("--json", action="store_true")

    p = sub.add_parser("pulse")
    p.add_argument("--grace-seconds", type=int, default=120)
    p.add_argument("--json", action="store_true")

    l = sub.add_parser("list")
    l.add_argument("--json", action="store_true")

    x = sub.add_parser("explain")
    x.add_argument("id")
    x.add_argument("--json", action="store_true")

    args = ap.parse_args(argv)

    if args.cmd == "create":
        ev = create_reminder(
            target_agent=args.agent,
            content=args.content,
            tz=args.tz,
            in_duration=args.in_duration,
            at_local_iso=args.at_local_iso,
        )
        if args.json:
            print(json.dumps(ev, indent=2, ensure_ascii=False))
        else:
            sched_local = _parse_iso(ev["scheduled_for_utc"]).astimezone(ZoneInfo(ev["tz"]))
            hh = sched_local.strftime("%I").lstrip("0") or "12"
            mm = sched_local.strftime("%M")
            tzab = sched_local.tzname() or ev["tz"]
            ampm = sched_local.strftime("%p")
            print(f"OK (Scribe): reminder scheduled for {hh}:{mm} {ampm} {tzab} — {ev['content']}")
        return 0

    if args.cmd == "pulse":
        out = pulse(grace_seconds=args.grace_seconds)
        if args.json:
            print(json.dumps(out, indent=2))
        else:
            print(f"pulse: delivered={out['delivered']} missed={out['missed']} pending_seen={out['pending_seen']}")
        return 0

    if args.cmd == "list":
        out = list_pending()
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "explain":
        out = explain_reminder(args.id)
        if out is None:
            print(json.dumps({"error": "not_found", "id": args.id}, indent=2))
            return 1
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0

    return 2

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
