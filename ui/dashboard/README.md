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
- Python 3.10+ (your repo is already using Python 3.12)
- OpenClaw runtime present under `~/.openclaw/runtime/`
- `query_status.py` available under workspace:
  `ops/scripts/agents/query_status.py`

## Run (recommended: venv)
From repo root:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn jinja2 python-multipart

uvicorn ui.dashboard.app:app --host 127.0.0.1 --port 8787 --reload
```
