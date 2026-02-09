# Minion RUNBOOK (minimal)

Purpose
- Operational playbook for routing, acknowledgements, handoffs, and escalations.

Onboarding
1. Read AGENTS.md and Deiphobe's SOUL.md for authority boundaries.
2. Ensure write access to ~/.openclaw/runtime/logs/team_bus.jsonl and follow JSONL event format.

Task intake
- Accept tasks via: team_bus.jsonl events, manual assignment, or HTTP endpoints (future).
- On receipt: emit an ACK event with timestamp, assign a task_id if absent, propose owner, and set an ETA.

Routing policy (default)
- If task is documentation or small ops (non-production): assign to Scribe or Peabody as applicable.
- If task involves canonical facts, audits, or infra hygiene: assign to Custodian.
- If task requires strategic framing or ambiguous policy choices: assign to Deiphobe.
- Low-risk automation may be approved by Minion if ACCESS.md and playbooks permit; otherwise escalate.

Escalation
- For anything marked medium/high risk, token-required, or ambiguous policy: escalate to Deiphobe and Custodian with full context.

Event format (append to team_bus.jsonl)

Minion must use the canonical status protocol event types.

Examples:

TASK_ACK (acknowledge assignment)
```json
{"ts":"2026-02-09T00:31:10-06:00","actor":"minion","type":"TASK_ACK","task_id":"TASK_ID","assigned_by":"deiphobe","owner":"minion","ETA":"2026-02-09T02:00:00-06:00","summary":"ACK; routing/coordination started"}
```

TASK_UPDATE (state: in_process | error | complete)
```json
{"ts":"2026-02-09T01:10:00-06:00","actor":"minion","type":"TASK_UPDATE","task_id":"TASK_ID","state":"in_process","summary":"Routed to Peabody; awaiting review","details_path":"~/.openclaw/runtime/logs/status/tasks/TASK_ID/minion-notes.md"}
```

STATUS (agent self-report; optional task_id)
```json
{"ts":"2026-02-09T00:30:05-06:00","actor":"minion","type":"STATUS","task_id":null,"status":"idle","progress":0,"summary":"No active routing tasks","dry_run":true}
```

STATUS_REPORT (final written report artifact)
```json
{"ts":"2026-02-09T03:05:00-06:00","actor":"minion","type":"STATUS_REPORT","task_id":"TASK_ID","report_path":"~/.openclaw/runtime/logs/status/tasks/TASK_ID/minion-report.md","summary":"Routing complete; next owner assigned"}
```

Audit
- All events are append-only and must not modify existing entries.
- Keep a local backup of team_bus.jsonl before bulk operations: ~/.openclaw/runtime/logs/team_bus.jsonl.bak

Dry-run mode
- Minion must default to dry-run for any action that would change files under other projects unless operator approves.

Operator tokens
- Respect operator tokens (e.g., TrashApply, DeployApply). Minion may only record intention without executing when token is absent.

Maintenance
- Periodically verify ACCESS.md files for projects and report mismatches to Deiphobe.

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

