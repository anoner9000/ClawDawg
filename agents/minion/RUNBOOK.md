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
{
  "ts": "2026-02-08T22:00:00-06:00",
  "actor": "minion",
  "task_id": "<task-id>",
  "action": "ack|route|escalate|close",
  "owner": "<agent>",
  "summary": "one-line",
  "details_path": "optional path to artifact",
  "escalated_to": ["deiphobe","custodian"]
}

Audit
- All events are append-only and must not modify existing entries.
- Keep a local backup of team_bus.jsonl before bulk operations: ~/.openclaw/runtime/logs/team_bus.jsonl.bak

Dry-run mode
- Minion must default to dry-run for any action that would change files under other projects unless operator approves.

Operator tokens
- Respect operator tokens (e.g., TrashApply, DeployApply). Minion may only record intention without executing when token is absent.

Maintenance
- Periodically verify ACCESS.md files for projects and report mismatches to Deiphobe.
