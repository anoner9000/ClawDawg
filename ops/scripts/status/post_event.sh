#!/usr/bin/env bash
set -euo pipefail

BUS_PATH="${BUS_PATH:-$HOME/.openclaw/runtime/logs/team_bus.jsonl}"
PERSIST_SCRIPT="${PERSIST_SCRIPT:-$HOME/.openclaw/workspace/ops/scripts/agents/persist_status.sh}"
SCHEMA_VERSION="${SCHEMA_VERSION:-team_bus.v1.1}"

RAW="$(cat)"
if [[ -z "$RAW" ]]; then
  echo "ERROR: expected JSON event on stdin" >&2
  exit 2
fi

EVENT_JSON="$(RAW="$RAW" SCHEMA_VERSION="$SCHEMA_VERSION" python3 - <<'PY'
import json
import os
import sys
from datetime import datetime, timezone

raw = os.environ["RAW"]
schema_version = os.environ.get("SCHEMA_VERSION", "team_bus.v1.1")

try:
    event = json.loads(raw)
except json.JSONDecodeError as exc:
    print(f"ERROR: invalid JSON: {exc}", file=sys.stderr)
    raise SystemExit(2)

if not isinstance(event, dict):
    print("ERROR: event must be a JSON object", file=sys.stderr)
    raise SystemExit(2)

if "type" not in event:
    print("ERROR: missing required field: type", file=sys.stderr)
    raise SystemExit(2)

if "actor" not in event and "agent" not in event:
    print("ERROR: missing required field: actor or agent", file=sys.stderr)
    raise SystemExit(2)

if "agent" not in event and "actor" in event:
    event["agent"] = event["actor"]
if "actor" not in event and "agent" in event:
    event["actor"] = event["agent"]

if "schema_version" not in event:
    event["schema_version"] = schema_version

if "ts" not in event:
    event["ts"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

if "task_id" not in event:
    event["task_id"] = None

if "dry_run" not in event:
    event["dry_run"] = True

print(json.dumps(event, ensure_ascii=False))
PY
)"

mkdir -p "$(dirname "$BUS_PATH")"
printf '%s\n' "$EVENT_JSON" >> "$BUS_PATH"

echo "$EVENT_JSON"

if [[ -x "$PERSIST_SCRIPT" ]]; then
  "$PERSIST_SCRIPT" --event-json "$EVENT_JSON" >/dev/null || true
fi
