# ops/scripts/

Operational tooling. Convention: scripts are grouped by domain.

## Top commands
- Dashboard: ./dash tasks --interval 5 --sort state --color
- Task detail: ./dash task --task-id <TASK_ID> --tail 10 --since 30m --color
- Validate bus: python3 validate/validate_team_bus.py --schema ../schemas/team_bus.v1.json
- Validate bus jsonl: python3 validate/validate_team_bus_jsonl.py --schema ../schemas/team_bus.v1.json --bus ~/.openclaw/runtime/logs/team_bus.jsonl
- Deiphobe approve: bus/deiphobe approve --task-id <TASK_ID> --summary "..." --expires-minutes 10
- Deiphobe unblock: bus/deiphobe unblock --task-id <TASK_ID> --summary "..."

## Quick commands
- Dashboard:  ops/scripts/dash tasks --interval 5 --sort state --color
- Task view:  ops/scripts/dash task --task-id <TASK_ID>
- Gate check: python3 ops/scripts/gates/gate_require_approval.py --task-id <TASK_ID> --bus ~/.openclaw/runtime/logs/team_bus.jsonl
- Deiphobe:   ops/scripts/bus/deiphobe approve|unblock ...

## Key entrypoints
- deiphobe                 : emit APPROVAL / UNBLOCKED (authority wrapper)
- dashboards/task_dashboard.py : read-only mission control (CLI)
- dashboards/task_state.py     : read-only single-task inspector

## Layout
- bus/        : event bus helpers (writers, watchers)
- gates/      : execution gates (approval checks)
- dashboards/ : read-only status views
- ledger/     : heartbeat / accounting / reports
- gmail/      : gmail cleanup pipeline
- cron/       : scheduled runners and enqueue scripts
- backups/    : backup + rotation tools
- validate/   : schema and jsonl validators
- legacy/     : deprecated scripts (kept for reference)
- utils/      : tiny helpers

Rule: ops scripts may read/write logs; they should not change doctrine.
