from __future__ import annotations

import os
from pathlib import Path


def _env_path(name: str, default: str) -> Path:
    return Path(os.environ.get(name, default)).expanduser()


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except ValueError:
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except ValueError:
        return default


WORKSPACE_BASE = _env_path("OPENCLAW_WORKSPACE", "~/.openclaw/workspace")
RUNTIME_BASE = _env_path("OPENCLAW_RUNTIME", "~/.openclaw/runtime")

TEAM_BUS = RUNTIME_BASE / "logs" / "team_bus.jsonl"
STATUS_AGENTS_DIR = RUNTIME_BASE / "logs" / "status" / "agents"
STATUS_TASKS_DIR = RUNTIME_BASE / "logs" / "status" / "tasks"

QUERY_STATUS_CLI = WORKSPACE_BASE / "ops" / "scripts" / "agents" / "query_status.py"

CLI_TIMEOUT_SECS = _env_float("OPENCLAW_UI_CLI_TIMEOUT_S", 3.0)
CLI_MAX_BYTES = _env_int("OPENCLAW_UI_CLI_MAX_BYTES", 256_000)
POLL_AGENTS_SECS = _env_float("OPENCLAW_UI_POLL_AGENTS_S", 5.0)
POLL_TASKS_SECS = _env_float("OPENCLAW_UI_POLL_TASKS_S", 10.0)
ATTENTION_TYPES = {"ERROR", "ESCALATE", "REVIEW_REQUEST", "BLOCKED"}
