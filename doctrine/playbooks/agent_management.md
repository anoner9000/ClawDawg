# OpenClaw Agent Team Management Playbook

## Core principle
Agents don’t “chat”. They publish structured state. Deiphobe routes work and is the only approval authority.

## Team roles
- Deiphobe (Manager): assigns tasks, approves/unblocks, closes tasks.
- Planner: writes plans, decomposes tasks, identifies risks. No execution.
- Executor: runs approved actions. No improvisation.
- Auditor: verifies outcomes, updates ledgers/manifests, produces summaries.
- Watcher: monitors and emits RISK; auto-blocks high/critical.

## Canonical communication layer
Append-only event bus: ~/.openclaw/runtime/logs/team_bus.jsonl

If it isn’t on the bus, it didn’t happen.

## Task lifecycle
1) INTENT (Deiphobe)
2) PLAN (Planner)
3) REVIEW (Auditor)
4) APPROVAL (Deiphobe, time-bounded via expires_at)
5) RESULT (Executor)
6) VERIFIED (Auditor)
7) CLOSED (Deiphobe)

## Safety invariants
- Execution requires Deiphobe APPROVAL + unexpired expires_at.
- RISK with severity high/critical triggers BLOCKED automatically.
- BLOCKED persists until Deiphobe UNBLOCKED + fresh APPROVAL.
- Executor re-checks gate before every state-changing step.

## Shared context structure (per project)
project/<name>/
- ACCESS.md (who can read/write)
- CONTEXT.md (current working context)
- research/ (supporting docs)

Context = current truth. Bus = audit history.

## Leveling and permissions
L1 Observer: may PLAN/REVIEW/RISK only. No tools that change state.
L2 Advisor: may suggest commands + do dry-runs (read-only or non-destructive).
L3 Operator: may execute only with gate + scoped permissions.
L4 Autonomous: domain-limited autonomy; still logs everything to bus and is auditable.

## Performance reviews (monthly)
Auditor produces scorecards:
- tasks_closed, verification_pass_rate, rework_count
- risk_catches, policy_violations, cost/rate incidents

Deiphobe adjusts level up/down based on evidence.

Recorded-by: Deiphobe
Timestamp: 2026-02-07T20:04:00-06:00
