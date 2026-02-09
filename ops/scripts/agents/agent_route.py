#!/usr/bin/env python3
"""
agent_route.py

Deterministic handoff: writes a task JSON into:
  ~/.openclaw/workspace/archive/memory/agent_tasks/

Uses canonical registry:
  ~/.openclaw/workspace/ops/schemas/agents.json
"""
import json
import sys
import time
import uuid
from pathlib import Path

WS = Path.home() / ".openclaw" / "workspace"
REG = WS / "ops" / "schemas" / "agents.json"
OUTDIR = WS / "archive" / "memory" / "agent_tasks"

def die(msg: str, code: int = 2):
    print(msg, file=sys.stderr)
    sys.exit(code)

def load_registry():
    if not REG.exists():
        die(f"Missing registry: {REG}")
    try:
        return json.loads(REG.read_text())
    except Exception as e:
        die(f"Failed to parse registry JSON at {REG}: {e}")

def main():
    reg = load_registry()
    agents = reg.get("agents", {})

    if len(sys.argv) < 4:
        die("Usage: agent_route.py <from_agent> <to_agent> <title>\n"
            "Reads request text from stdin.")

    from_agent = sys.argv[1].strip()
    to_agent = sys.argv[2].strip()
    title = sys.argv[3].strip()

    if from_agent not in agents:
        die(f"Unknown from_agent '{from_agent}'. Known: {', '.join(sorted(agents.keys()))}")
    if to_agent not in agents:
        die(f"Unknown to_agent '{to_agent}'. Known: {', '.join(sorted(agents.keys()))}")

    request = sys.stdin.read().strip()
    if not request:
        die("Empty request: provide request text via stdin.")

    OUTDIR.mkdir(parents=True, exist_ok=True)

    task_id = f"{int(time.time())}_{uuid.uuid4().hex[:8]}"
    task = {
        "id": task_id,
        "from_agent": from_agent,
        "to_agent": to_agent,
        "title": title,
        "request": request,
        "context_paths": [],
        "created_at": int(time.time()),
        "registry_version": reg.get("version", None),
    }

    outpath = OUTDIR / f"task_{task_id}.json"
    outpath.write_text(json.dumps(task, indent=2))
    print(outpath)

if __name__ == "__main__":
    main()
