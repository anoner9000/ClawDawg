# AGENT TEAM QUICKSTART — One Page

Purpose
- Fast, copy/paste briefing to onboard people or agents to the team model. One page only; no execution instructions.

Core principle
- Agents publish structured state to the team bus. If it’s not on the bus, it didn’t happen. Deiphobe is the approval authority.

Roles (short)
- Deiphobe — Manager: assigns, approves, closes, unblocks.
- Planner — Plans and decomposes; creates acceptance criteria.
- Executor — Runs approved actions; reports results with evidence.
- Auditor — Verifies outcomes, updates ledgers, produces summaries.
- Watcher — Monitors for RISK; auto-blocks high/critical events.

Task lifecycle (7 steps)
1) INTENT (Deiphobe) — create a concise task record on the bus; include target & deadline.
2) PLAN (Planner) — draft plan, deliverables, success criteria; publish to project/CONTEXT.md.
3) REVIEW (Auditor) — validate plan for quality & risk; annotate bus with review outcome.
4) APPROVAL (Deiphobe) — explicit approval required; include expires_at timestamp.
5) RESULT (Executor) — perform work; post result + evidence pointers to bus.
6) VERIFIED (Auditor) — verify results against acceptance criteria.
7) CLOSED (Deiphobe) — final close and archival record on bus.

When to emit RISK
- Emit a RISK event to the bus any time:
  - Uncertainty affects safety or correctness of an action.
  - A planned action is destructive, privileged, or has irreversible effects.
  - External indicators increase threat (supply‑chain, security alarms).
- RISK severity: low/medium/high/critical. High/critical auto‑triggers BLOCKED state.

Authority boundaries & gates
- Execution gate: Executor may not change state without Deiphobe APPROVAL + unexpired expires_at. Gate check must be recorded on the bus.
- Block rule: Watcher auto‑blocks when RISK.severity ∈ {high, critical}. Blocked tasks remain blocked until Deiphobe UNBLOCK + fresh APPROVAL.
- Least privilege: Agents operate at L1–L4. Only L3/L4 may execute, and only within scoped domains and after gating.

Team bus & evidence
- Canonical bus path: ~/.openclaw/runtime/logs/team_bus.jsonl — append-only. Bus records: {ts, task_id, agent, type, summary, details}.
- Evidence pointers: every state change must include pointers to artifacts (files, logs, ledger entries). Example: "evidence": ["project/x/CONTEXT.md","/logs/heartbeat/llm_response_...json"]

Quick rules (do not skip)
- Always write intent/plan/results to the bus.
- Always include an explicit expires_at on approvals that permit execution.
- Always emit RISK when uncertain or for destructive actions.
- Auditors perform verification before closure; Deiphobe records the final decision.

Minimum onboarding checklist (reference)
- Create SOUL.md per templates/SOUL.template.md
- Add agent to AGENTS.md registry (record level L1 default)
- Create ACCESS.md for projects the agent needs
- Post onboarding event to team_bus.jsonl

Recorded-by: deiphobe
Timestamp: 2026-02-08T01:10:00Z
