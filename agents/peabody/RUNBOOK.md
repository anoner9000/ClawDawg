# Peabody — RUNBOOK (L2)

## Purpose
This runbook defines **how Peabody operates** when assigned a task by Deiphobe.

Peabody is a **developer-reviewer**, not an autonomous builder.
All actions are **task-driven, deterministic, and auditable**.

This document is descriptive and procedural only.  
Authoritative routing and execution are defined elsewhere.

---

## When Peabody Acts

Peabody acts **only** when a task exists in the task queue:

## Status Protocol (Required)

Every agent must support:

1) STATUS_CHECK responses
2) TASK_ACK on assignment
3) Task state answers: in_process | error | complete
4) Written status reports that are saved

### Where records live
- Bus (append-only): ~/.openclaw/runtime/logs/team_bus.jsonl
- Per-task/per-agent: ~/.openclaw/runtime/logs/status/tasks/<task_id>/<agent>.jsonl
- Latest per agent: ~/.openclaw/runtime/logs/status/agents/<agent>.latest.json

### Commands (post + persist)
These events must be appended to the bus AND persisted.

STATUS_CHECK is issued by Deiphobe/operator (example):
```bash
printf '%s' '{"actor":"deiphobe","type":"STATUS_CHECK","scope":"all","details":"manual poll"}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
```

```bash
printf '%s' '{"actor":"AGENT_NAME","type":"TASK_ACK","task_id":"TASK_ID","assigned_by":"deiphobe","owner":"AGENT_NAME","summary":"ACK; starting"}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
```

```bash
printf '%s' '{"actor":"AGENT_NAME","type":"TASK_UPDATE","task_id":"TASK_ID","state":"in_process","summary":"Working..."}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
```

```bash
printf '%s' '{"actor":"AGENT_NAME","type":"TASK_UPDATE","task_id":"TASK_ID","state":"complete","summary":"Done"}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
printf '%s' '{"actor":"AGENT_NAME","type":"STATUS_REPORT","task_id":"TASK_ID","report_path":"~/.openclaw/runtime/logs/status/tasks/TASK_ID/AGENT_NAME-report.md","summary":"Final report"}' | ~/.openclaw/workspace/ops/scripts/status/post_event.sh
```

Query status
~/.openclaw/workspace/ops/scripts/status/query_status.py --agent AGENT_NAME
~/.openclaw/workspace/ops/scripts/status/query_status.py --task TASK_ID

