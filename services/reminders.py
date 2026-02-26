#!/usr/bin/env python3
from __future__ import annotations
import argparse, json, uuid
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

LEDGER = Path("memory/reminders.jsonl")


def now_utc():
    return datetime.now(timezone.utc).isoformat()


def append_event(event: dict):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event) + "\n")


def load_events():
    if not LEDGER.exists():
        return []
    return [json.loads(line) for line in LEDGER.read_text().splitlines() if line.strip()]


def rebuild_state():
    events = load_events()
    state = defaultdict(dict)
    for e in events:
        rid = e["id"]
        if e["event"] == "created":
            state[rid] = {
                "id": rid,
                "created_at_utc": e["created_at_utc"],
                "scheduled_for_utc": e["scheduled_for_utc"],
                "tz": e["tz"],
                "target_agent": e["target_agent"],
                "content": e["content"],
                "status": "pending",
            }
        elif e["event"] == "delivered":
            if rid in state:
                state[rid]["status"] = "delivered"
                state[rid]["delivered_at_utc"] = e["at_utc"]
        elif e["event"] == "attempted":
            if rid in state:
                state[rid]["last_attempt_at_utc"] = e["at_utc"]
    return state


def cmd_list(args):
    state = rebuild_state()
    pending = [v for v in state.values() if v.get("status") == "pending"]
    print(json.dumps(pending, indent=2))


def cmd_explain(args):
    state = rebuild_state()
    if args.id not in state:
        print(json.dumps({"error": "not_found"}, indent=2))
        return
    print(json.dumps(state[args.id], indent=2))


def cmd_create(args):
    rid = str(uuid.uuid4())
    created = now_utc()
    scheduled = args.scheduled_for
    append_event({
        "event": "created",
        "id": rid,
        "created_at_utc": created,
        "scheduled_for_utc": scheduled,
        "tz": args.tz,
        "target_agent": args.agent,
        "content": args.content,
        "source": "scribe"
    })
    print(json.dumps({"event": "created", "id": rid}, indent=2))


def cmd_pulse(args):
    state = rebuild_state()
    delivered = 0
    for rid, data in state.items():
        if data["status"] != "pending":
            continue
        if data["scheduled_for_utc"] <= now_utc():
            append_event({"event": "attempted", "id": rid, "at_utc": now_utc(), "error": None})
            append_event({"event": "delivered", "id": rid, "at_utc": now_utc()})
            delivered += 1
    print(json.dumps({"delivered": delivered}, indent=2))


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_create = sub.add_parser("create")
    p_create.add_argument("--agent", required=True)
    p_create.add_argument("--content", required=True)
    p_create.add_argument("--scheduled-for", required=True)
    p_create.add_argument("--tz", default="America/Chicago")
    p_create.set_defaults(func=cmd_create)

    p_pulse = sub.add_parser("pulse")
    p_pulse.set_defaults(func=cmd_pulse)

    p_list = sub.add_parser("list")
    p_list.set_defaults(func=cmd_list)

    p_explain = sub.add_parser("explain")
    p_explain.add_argument("id")
    p_explain.set_defaults(func=cmd_explain)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
