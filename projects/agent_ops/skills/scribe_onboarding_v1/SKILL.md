---
name: scribe_onboarding_v1
version: 1.0.0
description: |
  Use when: explicitly governed onboarding execution for the Scribe trial and gate/evidence validation.
  Don't use when: general engineering implementation, refactoring, or standalone document drafting.
  Outputs: completed checklist, evidence record, acceptance decision, and referenced bus events.
  Success criteria: guardrails satisfied, evidence complete, and acceptance decision recorded.
---

# scribe_onboarding_v1

## Use When vs Don't Use When

### Use when
- You are executing or reviewing the Scribe onboarding trial workflow.
- You need a deterministic run through runbook, checklist, acceptance, and evidence artifacts.
- You need onboarding output that is compatible with scorecard and bus references.

### Don't use when
- You are creating net-new policy outside existing `agent_ops` source documents.
- You are performing unrelated engineering changes without onboarding governance requirements.
- You are running a retrospective report without an onboarding execution context.

### Negative examples (do not route here)
- "Draft a product roadmap" -> not onboarding governance.
- "Refactor a service module" -> software implementation task, not trial governance.
- "Ad-hoc incident note with no onboarding trial" -> outside this skill's scope.

## Inputs Required
- Trial scope: [Placeholder]
- Operator/reviewer identities: [Placeholder]
- Approval context (`approval_id`, `expires_at`) when applicable: [Placeholder]
- Risk assessment input: [Placeholder]
- Artifact destination paths: [Placeholder]

## Preconditions
- `projects/agent_ops/onboarding/scribe_trial_runbook.md` exists and is current.
- `projects/agent_ops/onboarding/scribe_trial_checklist.md` exists and is current.
- `projects/agent_ops/onboarding/scribe_trial_acceptance.md` exists and is current.
- `projects/agent_ops/onboarding/scribe_trial_evidence_template.md` exists and is current.
- `projects/agent_ops/bus/event_types.md` exists and defines required event fields.
- `projects/agent_ops/scorecards/schema.md` and `projects/agent_ops/scorecards/scorecard_template.md` exist for downstream reporting.

## Outputs
- Completed checklist record (from `projects/agent_ops/onboarding/scribe_trial_checklist.md` structure).
- Acceptance decision record (from `projects/agent_ops/onboarding/scribe_trial_acceptance.md` structure).
- Evidence record mapped to acceptance criteria (from `projects/agent_ops/onboarding/scribe_trial_evidence_template.md`).
- Bus event references aligned to `projects/agent_ops/bus/event_types.md`.
- Scorecard-compatible references aligned to `projects/agent_ops/scorecards/schema.md`.

## Success Criteria
- All required gates evaluated and documented.
- Required approval linkage present when applicable (`approval_id`, `expires_at`).
- High/Critical risk handling recorded with stop behavior.
- Evidence maps 1:1 to acceptance criteria.
- Final pass/fail decision recorded with references.

## Mandatory Guardrails
- Approval gate: `approval_id` and `expires_at` are required when approval is applicable.
- Risk gate: if risk is High/Critical, emit/record `RISK_BLOCKED` and stop execution.
- Unblock rule: only Deiphobe can authorize unblock; `UNBLOCKED` event plus approval linkage is required.
- Evidence mapping: every acceptance criterion must have corresponding evidence (1:1 mapping).
- Bus truth rule: `team_bus.jsonl` is append-only truth per `projects/agent_ops/CONTEXT.md`.

## Stop Conditions
- Missing approval or expired approval when approval is required -> stop.
- High/Critical risk detected -> record `RISK_BLOCKED` and stop.
- Unblock required but not Deiphobe-authorized -> stop.

## Procedure
1. Load canonical onboarding docs:
   - `projects/agent_ops/onboarding/scribe_trial_runbook.md`
   - `projects/agent_ops/onboarding/scribe_trial_checklist.md`
   - `projects/agent_ops/onboarding/scribe_trial_acceptance.md`
   - `projects/agent_ops/onboarding/scribe_trial_evidence_template.md`
2. Load event taxonomy and required fields from `projects/agent_ops/bus/event_types.md`.
3. Validate preconditions and run gates in runbook/checklist order.
4. For approval-gated scopes, verify `APPROVAL_GRANTED`, `approval_id`, and valid `expires_at`.
5. For High/Critical risk, record `RISK_BLOCKED` and stop; only continue after authorized `UNBLOCKED` linkage.
6. Record evidence directly in the evidence template and map each entry to acceptance criteria.
7. Record final decision in acceptance document structure.
8. Prepare scorecard-compatible output using:
   - `projects/agent_ops/scorecards/schema.md`
   - `projects/agent_ops/scorecards/scorecard_template.md`

## Deterministic invocation
Use the `scribe_onboarding_v1` skill.
