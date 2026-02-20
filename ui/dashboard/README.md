# OpenClaw Dashboard (Read-Only MVP)

Local, deterministic observability UI for OpenClaw’s control-plane lanes.

## Guarantees (MVP)
- **Read-only**: no writes to `team_bus.jsonl` and no agent execution.
- **Deterministic**: renders from runtime files + `query_status.py` output only.
- **Zero token usage**.
- **CLI-first**: Agent/Task views are derived from `ops/scripts/agents/query_status.py`.

## What it shows
- **Home**: system banner + agent cards + recent receipts
- **Agents**: per-agent latest snapshot + recent bus entries (via `query_status.py`)
- **Tasks**: per-task state + latest-by-agent (via `query_status.py`)
- **Receipts**: scans `status/tasks/*/*-report.md` and renders previews

## Requirements
- Python 3.10+ (repo currently uses Python 3.12 fine)
- OpenClaw runtime present under `~/.openclaw/runtime/`
- `query_status.py` available under workspace:
  `ops/scripts/agents/query_status.py`

## Configuration (Environment Variables)

### Paths
- `OPENCLAW_WORKSPACE`
  - Default: `~/.openclaw/workspace`
- `OPENCLAW_RUNTIME`
  - Default: `~/.openclaw/runtime`

### CLI Guards (locked)
- `OPENCLAW_UI_CLI_TIMEOUT_S`
  - Default: `3.0` seconds (hard timeout)
- `OPENCLAW_UI_CLI_MAX_BYTES`
  - Default: `256000` (256 KB) per stdout/stderr stream; output is truncated if exceeded

### Polling
- `OPENCLAW_UI_POLL_AGENTS_S`
  - Default: `5` seconds
- `OPENCLAW_UI_POLL_TASKS_S`
  - Default: `10` seconds

## Run (recommended: venv)
From repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn jinja2 python-multipart

uvicorn ui.dashboard.app:app --host 127.0.0.1 --port 8787 --reload
```

Open: `http://127.0.0.1:8787`

## Troubleshooting

### `CLI ERROR` badge
The `query_status.py` subprocess returned non-zero.
Open agent/task detail and inspect `stderr`.

### `TIMEOUT` badge
The CLI call exceeded `OPENCLAW_UI_CLI_TIMEOUT_S` (default `3s`).
Increase timeout temporarily:

```bash
OPENCLAW_UI_CLI_TIMEOUT_S=6 uvicorn ui.dashboard.app:app --host 127.0.0.1 --port 8787 --reload
```

### `TRUNC` badge
Output exceeded `OPENCLAW_UI_CLI_MAX_BYTES`.
Raise max bytes for debugging:

```bash
OPENCLAW_UI_CLI_MAX_BYTES=800000 uvicorn ui.dashboard.app:app --host 127.0.0.1 --port 8787 --reload
```

### Missing agents/tasks
Ensure runtime status lanes exist:
- `~/.openclaw/runtime/logs/status/agents/*.latest.json`
- `~/.openclaw/runtime/logs/status/tasks/*/`

### Notes on parsing
All parsing is centralized in `ui/dashboard/parsers.py`.
If parsing fails, the UI falls back to raw CLI output.
