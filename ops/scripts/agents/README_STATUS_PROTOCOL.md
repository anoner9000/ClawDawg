# Agent Status Protocol (Dry-Run Default)

Scripts:
- bus_status_check.py: emit STATUS_CHECK and optionally collect STATUS replies.
- agent_status_responder.py: emit STATUS/TASK_ACK/TASK_UPDATE/STATUS_REPORT events.
- persist_status.sh: persist status events to per-task and per-agent files.
- query_status.py: query status summaries by task or agent.

Storage:
- Bus: ~/.openclaw/runtime/logs/team_bus.jsonl
- Per-task: ~/.openclaw/runtime/logs/status/tasks/<task_id>/<agent>.jsonl
- Agent latest: ~/.openclaw/runtime/logs/status/agents/<agent>.latest.json

Quick test:
1. `bus_status_check.py --scope all`
2. `agent_status_responder.py respond-check --agent peabody --status idle --summary "No active tasks"`
3. `query_status.py --agent peabody`
