#!/usr/bin/env bash
set -euo pipefail

EVENT_JSON=""
EVENT_FILE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --event-json)
      EVENT_JSON="${2:-}"
      shift 2
      ;;
    --event-file)
      EVENT_FILE="${2:-}"
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

if [[ -n "$EVENT_FILE" ]]; then
  EVENT_JSON="$(cat "$EVENT_FILE")"
elif [[ -z "$EVENT_JSON" ]]; then
  EVENT_JSON="$(cat)"
fi

if [[ -z "$EVENT_JSON" ]]; then
  echo "ERROR: empty event json" >&2
  exit 2
fi

python3 - "$EVENT_JSON" <<'PY'
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

raw = sys.argv[1]
try:
    ev = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"ERROR: invalid event json: {exc}", file=sys.stderr)
    raise SystemExit(2)

actor = ev.get("actor") or ev.get("agent")
if not actor:
    print("ERROR: event missing actor/agent", file=sys.stderr)
    raise SystemExit(2)

ev_type = ev.get("type", "")
tracked = {"STATUS", "TASK_ACK", "TASK_UPDATE", "STATUS_REPORT"}
if ev_type not in tracked:
    print(f"SKIP: type '{ev_type}' not persisted")
    raise SystemExit(0)

rt = Path.home() / ".openclaw" / "runtime" / "logs" / "status"
agent_dir = rt / "agents"
agent_dir.mkdir(parents=True, exist_ok=True)
os.chmod(agent_dir, 0o750)

task_id = ev.get("task_id")
if task_id:
    task_dir = rt / "tasks" / str(task_id)
    task_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(task_dir, 0o750)
    task_file = task_dir / f"{actor}.jsonl"
    persisted = dict(ev)
    persisted["persisted_ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    with task_file.open("a", encoding="utf-8") as f:
        f.write(json.dumps(persisted, ensure_ascii=False) + "\n")
    os.chmod(task_file, 0o640)

latest = {
    "agent": actor,
    "type": ev_type,
    "status": ev.get("status") or ev.get("state") or "unknown",
    "task_id": task_id,
    "summary": ev.get("summary", ""),
    "ts": ev.get("ts"),
    "persisted_ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    "dry_run": ev.get("dry_run", False),
}
latest_file = agent_dir / f"{actor}.latest.json"
latest_file.write_text(json.dumps(latest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
os.chmod(latest_file, 0o640)

print("OK: persisted status event")
PY
