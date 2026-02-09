INTERNAL — Orchestration from Team Bus (one-page)

Purpose
- Allow agents to coordinate and be orchestrated via append-only team_bus.jsonl events while preserving auditability and operator control.

Event types
- ORCHESTRATE / ORCHESTRATE_REQUEST: request to orchestrate an action.
  Required fields: ts, actor (must be deiphobe for orchestration), type, action, target_agent, task_id, dry_run (bool), artifacts (optional), required_tokens (optional list)
- ORCHESTRATION_NOTICE: appended by orchestrator in dry-run to indicate suggested actions.
- ACCESS_CHECK: result of check_access.sh when an orchestration would change project files (fields: allowed: true/false, details)
- ROUTE / ESCALATE / ACK / REVIEW_OK / REVIEW_REJECT: existing event types for coordination

Rules
- Deiphobe is allowed to post ORCHESTRATE events. Other agents may post ORCHESTRATE_REQUEST but only Deiphobe can approve (post ORCHESTRATE). Orchestrator will ignore non-Deiphobe ORCHESTRATE events in dry-run mode.
- Any orchestration that would write project files must be pre-checked with check_access.sh by the recipient agent; recipient must append ACCESS_CHECK before applying.
- Any live operation that requires operator token must include required_tokens and be blocked if token absent.

Operational controls
- Default mode: dry-run. bus_orchestrator.py runs in dry-run and appends ORCHESTRATION_NOTICE + suggested ROUTE events.
- To enable live mode: require explicit Deiphobe signoff and Operator token documented in playbooks/token_rotation_playbook.md.

Audit
- All orchestration attempts and checks are append-only in team_bus.jsonl. Keep backups of the bus file before bulk operations.

Testing
- Use minion_route.sh and bus_orchestrator.py --once to simulate orchestration and verify ACCESS_CHECK and ROUTE events.

Signoff flow
- Any change to this playbook must be approved by Custodian and Deiphobe (post REVIEW_OK on team_bus.jsonl).
