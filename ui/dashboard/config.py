from __future__ import annotations

from pathlib import Path

RUNTIME_BASE = Path("~/.openclaw/runtime").expanduser()
WORKSPACE_BASE = Path("~/.openclaw/workspace").expanduser()

TEAM_BUS = RUNTIME_BASE / "logs" / "team_bus.jsonl"
STATUS_AGENTS_DIR = RUNTIME_BASE / "logs" / "status" / "agents"
STATUS_TASKS_DIR = RUNTIME_BASE / "logs" / "status" / "tasks"

QUERY_STATUS_CLI = WORKSPACE_BASE / "ops" / "scripts" / "agents" / "query_status.py"

CLI_TIMEOUT_SECS = 3
CLI_MAX_CHARS = 200_000
ATTENTION_TYPES = {"ERROR", "ESCALATE", "REVIEW_REQUEST", "BLOCKED"}
