#!/usr/bin/env python3
"""
agent_compliance_check.py

Fails if:
1) Any agent directory lacks SOUL.md or RUNBOOK.md
2) Any agent has not posted STATUS within the last N minutes
"""

from pathlib import Path
import json
import sys
from datetime import datetime, timezone

# ---- CONFIG ----
MAX_AGE_MINUTES = int(sys.argv[1]) if len(sys.argv) > 1 else 10

WS = Path.home() / ".openclaw" / "workspace"
AGENTS_DIR = WS / "agents"
STATUS_DIR = Path.home() / ".openclaw" / "runtime" / "logs" / "status" / "agents"
BUS_PATH = Path.home() / ".openclaw" / "runtime" / "logs" / "team_bus.jsonl"

now = datetime.now(timezone.utc)

errors = []


def fail(msg):
    errors.append(msg)


def load_latest_status(agent):
    p = STATUS_DIR / f"{agent}.latest.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def emit_compliance_fail(details):
    event = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "actor": "compliance",
        "type": "COMPLIANCE_FAIL",
        "scope": "agents",
        "summary": "Agent compliance failed",
        "details": details,
        "schema_version": "team_bus.v1.1",
    }
    BUS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with BUS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(event, ensure_ascii=False) + "\n")


# ---- CHECK STRUCTURE ----
for p in sorted(AGENTS_DIR.iterdir()):
    if not p.is_dir():
        continue

    agent = p.name
    soul = p / "SOUL.md"
    runbook = p / "RUNBOOK.md"

    if not soul.exists():
        fail(f"[STRUCTURE] {agent}: missing SOUL.md")
    if not runbook.exists():
        fail(f"[STRUCTURE] {agent}: missing RUNBOOK.md")

# ---- CHECK LIVENESS ----
for p in sorted(AGENTS_DIR.iterdir()):
    if not p.is_dir():
        continue

    agent = p.name
    status = load_latest_status(agent)

    if not status:
        fail(f"[LIVENESS] {agent}: no latest status snapshot")
        continue

    ts = status.get("ts")
    if not ts:
        fail(f"[LIVENESS] {agent}: status missing ts")
        continue

    try:
        ts_dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except Exception:
        fail(f"[LIVENESS] {agent}: invalid timestamp format ({ts})")
        continue

    age_min = (now - ts_dt).total_seconds() / 60.0
    if age_min > MAX_AGE_MINUTES:
        fail(f"[LIVENESS] {agent}: last STATUS {age_min:.1f} min ago (> {MAX_AGE_MINUTES})")

# ---- REPORT ----
if errors:
    print("❌ AGENT COMPLIANCE FAILED")
    for e in errors:
        print(" -", e)
    emit_compliance_fail(errors)
    sys.exit(1)

print(f"✅ AGENT COMPLIANCE OK (all agents healthy within {MAX_AGE_MINUTES} min)")
